# -*- coding: utf-8 -*-
'''
An engine that reads messages from Hipchat and sends them to the Salt
event bus.  Alternatively Salt commands can be sent to the Salt master
via Hipchat by setting the control parameter to ``True`` and using command
prefaced with a ``!``. Only token key is required, but room and control
keys make the engine interactive.
.. versionadded: Carbon
:configuration: Example configuration
    .. code-block:: yaml
        engines:
            hipchat:
               token: 'XXXXXX'
               room: 'salt'
               control: True
               valid_users:
                   - SomeUser
               valid_commands:
                   - test.ping
                   - cmd.run
               aliases:
                   list_jobs:
                       type: runner
                       cmd: jobs.list_jobs
:depends: hypchat
'''

from __future__ import absolute_import
import logging
import time
import json
import os


try:
    import hypchat
    HAS_HYPCHAT = True
except ImportError:
    HAS_HYPCHAT = False

import salt.utils
import salt.runner
import salt.client
import salt.loader


def __virtual__():
    return HAS_HYPCHAT


COMMAND_NAME = 'salt'
log = logging.getLogger(__name__)


def _parse_message(text):
    ''' return cmd args kwargs target '''

    args = []
    kwargs = {}

    cmdline = salt.utils.shlex_split(text)
    cmd = cmdline[0]

    if len(cmdline) > 1:
        for item in cmdline[1:]:
            if '=' in item:
                (key, value) = item.split('=', 1)
                kwargs[key] = value
            else:
                args.append(item)

    if 'target' not in kwargs:
        target = '*'
    else:
        target = kwargs['target']
        del kwargs['target']

    return cmd, args, kwargs, target


def _publish_file(token, room, filepath, message='', host='api.hipchat.com'):
    """ Send file to a HipChat room via API version 2
    Parameters
    ----------
    token : str
        HipChat API version 2 compatible token - must be token for active user
    room: str
        Name or API ID of the room to notify
    filepath: str
        Full path of file to be sent
    message: str, optional
        Message to send to room
    host: str, optional
        Host to connect to, defaults to api.hipchat.com
    """

    if not os.path.isfile(filepath):
        raise ValueError("File '{0}' does not exist".format(filepath))
    if len(message) > 1000:
        raise ValueError('Message too long')

    url = "https://{0}/v2/room/{1}/share/file".format(host, room)
    headers = {'Content-type': 'multipart/related; boundary=boundary123456'}
    headers['Authorization'] = "Bearer " + token
    msg = json.dumps({'message': message})

    payload = """\
--boundary123456
Content-Type: application/json; charset=UTF-8
Content-Disposition: attachment; name="metadata"

{0}

--boundary123456
Content-Disposition: attachment; name="file"; filename="{1}"

{2}

--boundary123456--\
""".format(msg, os.path.basename(filepath), open(filepath, 'rb').read())

    salt.utils.http.query(url, method='POST', header_dict=headers, data=payload)


def start(token,
          room='salt',
          aliases=None,
          valid_users=None,
          valid_commands=None,
          control=False,
          trigger="!",
          tag='salt/engines/hipchat/incoming'):
    '''
    Listen to Hipchat messages and forward them to Salt
    '''
    target_room = None

    if __opts__.get('__role') == 'master':
        fire_master = salt.utils.event.get_master_event(
            __opts__,
            __opts__['sock_dir']).fire_event
    else:
        fire_master = None

    def fire(tag, msg):
        '''
        fire event to salt bus
        '''

        if fire_master:
            fire_master(msg, tag)
        else:
            __salt__['event.send'](tag, msg)

    def _eval_bot_mentions(all_messages, trigger):
        ''' yield partner message '''
        for message in all_messages:
            message_text = message['message']
            if message_text.startswith(trigger + COMMAND_NAME + ' '):
                fire(tag, message)
                text = message_text.replace(trigger + COMMAND_NAME + ' ', '').strip()
                yield message['from']['mention_name'], text

    if not token:
        raise UserWarning("Hipchat token not found")

    runner_functions = sorted(salt.runner.Runner(__opts__).functions)

    hipc = hypchat.HypChat(token)
    if not hipc:
        raise UserWarning("Unable to connect to hipchat")

    log.debug('Connected to Hipchat')
    all_rooms = hipc.rooms(max_results=1000)['items']
    for a_room in all_rooms:
        if a_room['name'] == room:
            target_room = a_room
    if not target_room:
        log.debug("Unable to connect to room {0}".format(room))
        # wait for a bit as to not burn through api calls
        time.sleep(30)
        raise UserWarning("Unable to connect to room {0}".format(room))

    after_message_id = target_room.latest(maxResults=1)['items'][0]['id']

    while True:
        try:
            new_messages = target_room.latest(
                not_before=after_message_id)['items']
        except hypchat.requests.HttpServiceUnavailable:
            time.sleep(15)
            continue

        after_message_id = new_messages[-1]['id']
        for partner, text in _eval_bot_mentions(new_messages[1:], trigger):
            # bot summoned by partner

            if not control:
                log.debug("Engine not configured for control")
                return

            # Ensure the user is allowed to run commands
            if valid_users:
                if partner not in valid_users:
                    target_room.message('{0} not authorized to run Salt commands'.format(partner))
                    return

            cmd, args, kwargs, target = _parse_message('{0}'.format(text))

            # Ensure the command is allowed
            if valid_commands:
                if cmd not in valid_commands:
                    target_room.message('Using {0} is not allowed.'.format(cmd))
                    return

            ret = {}
            if aliases and isinstance(aliases, dict) and cmd in aliases.keys():
                salt_cmd = aliases[cmd].get('cmd')

                if 'type' in aliases[cmd]:
                    if aliases[cmd]['type'] == 'runner':
                        runner = salt.runner.RunnerClient(__opts__)
                        ret = runner.cmd(salt_cmd, arg=args, kwarg=kwargs)
                    else:
                        local = salt.client.LocalClient()
                        ret = local.cmd('{0}'.format(target), salt_cmd, args, kwargs)

                elif cmd in runner_functions:
                    runner = salt.runner.RunnerClient(__opts__)
                    ret = runner.cmd(cmd, arg=args, kwarg=kwargs)

            elif cmd in runner_functions:
                runner = salt.runner.RunnerClient(__opts__)
                ret = runner.cmd(cmd, arg=args, kwarg=kwargs)

            # default to trying to run as a client module.
            else:
                local = salt.client.LocalClient()
                ret = local.cmd('{0}'.format(target), cmd, args, kwargs)

            tmp_path_fn = salt.utils.mkstemp()
            with salt.utils.fopen(tmp_path_fn, 'w+') as fp_:
                fp_.write(json.dumps(ret, sort_keys=True, indent=4))
            message_string = '@{0} Results for: {1} {2} {3} on {4}'.format(partner, cmd, args, kwargs, target)
            _publish_file(token, room, tmp_path_fn, message=message_string)
            salt.utils.safe_rm(tmp_path_fn)
        time.sleep(5)
