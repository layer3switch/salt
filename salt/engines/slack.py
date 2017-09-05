# -*- coding: utf-8 -*-
'''
An engine that reads messages from Slack and can act on them.

It has two major uses.

1. When the ``control`` parameter is set to ``True`` and a message is prefaced
   with the ``trigger`` (which defaults to ``!``) then the engine will
   validate that the user has permission, and if so will run the command

2. In addition, when the parameter ``fire_all`` is set (defaults to False),
   all other messages (the messages that aren't control messages) will be
   fired off to the salt event bus with the tag prefixed by the string
   provided by the ``tag`` config option (defaults to ``salt/engines/slack``).

This allows for configuration to be gotten from either the engine config, or from
the saltmaster's minion pillar.

.. versionadded: 2016.3.0

:configuration: Example configuration using only a "default" group. The default group is not special.
In addition, other groups are being loaded from pillars.

.. code-block:: yaml

    engines:
      - slack:
          token: 'xoxb-xxxxxxxxxx-xxxxxxxxxxxxxxxxxxxxxxxx'
          control: True
          fire_all: False
          groups_pillar_name: "slack_engine:groups_pillar"
          groups:
            default:
              users:
                - *
            commands:
              - test.ping
              - cmd.run
              - list_jobs
              - list_commands
            aliases:
              list_jobs:
                cmd: jobs.list_jobs
              list_commands:
                cmd: pillar.get salt:engines:slack:valid_commands target=saltmaster tgt_type=list
            default_target:
              target: saltmaster
              tgt_type: glob
            targets:
              test.ping:
                target: '*'
                tgt_type: glob
              cmd.run:
                target: saltmaster
                tgt_type: list

:configuration: Example configuration using the "default" group and a non-default group and a pillar that will be merged in
    If the user is '*' (without the quotes) then the group's users or commands will match all users as appropriate

.. versionadded: 2017.7.0

.. code-block:: yaml

    engines:
      - slack:
          groups_pillar: slack_engine_pillar
          token: 'xoxb-xxxxxxxxxx-xxxxxxxxxxxxxxxxxxxxxxxx'
          control: True
          fire_all: True
          tag: salt/engines/slack
          groups_pillar_name: "slack_engine:groups_pillar"
          groups:
            default:
              valid_users:
                - *
              valid_commands:
                - test.ping
              aliases:
                list_jobs:
                  cmd: jobs.list_jobs
                list_commands:
                  cmd: pillar.get salt:engines:slack:valid_commands target=saltmaster tgt_type=list
            gods:
              users:
                - garethgreenaway
              commands:
                - *

:depends: slackclient

'''

# Import python libraries
from __future__ import absolute_import
import json
import itertools
import logging
import time
import re
import traceback
import yaml

log = logging.getLogger(__name__)

try:
    import slackclient
    HAS_SLACKCLIENT = True
except ImportError:
    HAS_SLACKCLIENT = False

# Import salt libs
import salt.client
import salt.loader
import salt.minion
import salt.runner
import salt.utils
import salt.utils.args
import salt.utils.event
import salt.utils.http
import salt.utils.slack
from salt.utils.yamldumper import OrderedDumper

__virtualname__ = 'slack'


def __virtual__():
    if not HAS_SLACKCLIENT:
        return (False, 'The \'slackclient\' Python module could not be loaded')
    return __virtualname__


def get_slack_users(token):
    '''
    Get all users from Slack
    '''

    ret = salt.utils.slack.query(function='users',
                                 api_key=token,
                                 opts=__opts__)
    users = {}
    if 'message' in ret:
        for item in ret['message']:
            if 'is_bot' in item:
                if not item['is_bot']:
                    users[item['name']] = item['id']
                    users[item['id']] = item['name']
    return users


def get_slack_channels(token):
    '''
    Get all channel names from Slack
    '''

    ret = salt.utils.slack.query(
        function='rooms',
        api_key=token,
        # These won't be honored until https://github.com/saltstack/salt/pull/41187/files is merged
        opts={
            'exclude_archived': True,
            'exclude_members': True
        })
    channels = {}
    if 'message' in ret:
        for item in ret['message']:
            channels[item["id"]] = item["name"]
    return channels


def get_config_groups(groups_conf, groups_pillar_name):
    """
    get info from groups in config, and from the named pillar

    todo: add specification for the minion to use to recover pillar
    """
    # Get groups
    # Default to returning something that'll never match
    ret_groups = {
        "default": {
            "users": set(),
            "commands": set(),
            "aliases": dict(),
            "default_target": dict(),
            "targets": dict()
        }
    }

    # allow for empty groups in the config file, and instead let some/all of this come
    # from pillar data.
    if not groups_conf:
        use_groups = {}
    else:
        use_groups = groups_conf
    # First obtain group lists from pillars, then in case there is any overlap, iterate over the groups
    # that come from pillars.  The configuration in files on disk/from startup
    # will override any configs from pillars.  They are meant to be complementary not to provide overrides.
    try:
        groups_gen = itertools.chain(_groups_from_pillar(groups_pillar_name).items(), use_groups.items())
    except AttributeError:
        log.warn("Failed to get groups from {}: {}".format(groups_pillar_name, _groups_from_pillar(groups_pillar_name)))
        log.warn("or from config: {}".format(use_groups))
        groups_gen = []
    for name, config in groups_gen:
        log.info("Trying to get {} and {} to be useful".format(name, config))
        ret_groups.setdefault(name, {
            "users": set(), "commands": set(), "aliases": dict(), "default_target": dict(), "targets": dict()
        })
        try:
            ret_groups[name]['users'].update(set(config.get('users', [])))
            ret_groups[name]['commands'].update(set(config.get('commands', [])))
            ret_groups[name]['aliases'].update(config.get('aliases', {}))
            ret_groups[name]['default_target'].update(config.get('default_target', {}))
            ret_groups[name]['targets'].update(config.get('targets', {}))
        except IndexError:
            log.warn("Couldn't use group {}. Check that targets is a dict and not a list".format(name))

    log.debug("Got the groups: {}".format(ret_groups))
    return ret_groups


def _groups_from_pillar(pillar_name):
    """pillar_prefix is the pillar.get syntax for the pillar to be queried.
    Group name is gotten via the equivalent of using
    ``salt['pillar.get']('{}:{}'.format(pillar_prefix, group_name))``
    in a jinja template.

    returns a dictionary (unless the pillar is mis-formatted)
    XXX: instead of using Caller, make the minion to use configurable so there could be some
         restrictions placed on what pillars can be used.
    """
    caller = salt.client.Caller()
    pillar_groups = caller.cmd('pillar.get', pillar_name)
    # pillar_groups = __salt__['pillar.get'](pillar_name, {})
    log.info("Got pillar groups {} from pillar {}".format(pillar_groups, pillar_name))
    log.info("pillar groups type is {}".format(type(pillar_groups)))
    return pillar_groups


def fire(tag, msg):
    """
    This replaces a function in main called "fire"

    It fires an event into the salt bus.
    """
    if __opts__.get('__role') == 'master':
        fire_master = salt.utils.event.get_master_event(
            __opts__,
            __opts__['sock_dir']).fire_event
    else:
        fire_master = None

    if fire_master:
        fire_master(msg, tag)
    else:
        __salt__['event.send'](tag, msg)


def can_user_run(user, command, groups):
    """
    Break out the permissions into the folowing:

    Check whether a user is in any group, including whether a group has the '*' membership

    :type user: str
    :param user: The username being checked against

    :type command: str
    :param command: The command that is being invoked (e.g. test.ping)

    :type groups: dict
    :param groups: the dictionary with groups permissions structure.

    :rtype: tuple
    :returns: On a successful permitting match, returns 2-element tuple that contains
        the name of the group that successfuly matched, and a dictionary containing
        the configuration of the group so it can be referenced.

        On failure it returns an empty tuple

    """
    log.info("{} wants to run {} with groups {}".format(user, command, groups))
    for key, val in groups.items():
        if user not in val['users']:
            if '*' not in val['users']:
                continue  # this doesn't grant permissions, pass
        if (command not in val['commands']) and (command not in val.get('aliases', {}).keys()):
            if '*' not in val['commands']:
                continue  # again, pass
        log.info("Slack user {} permitted to run {}".format(user, command))
        return (key, val,)  # matched this group, return the group
    log.info("Slack user {} denied trying to run {}".format(user, command))
    return ()


def commandline_to_list(cmdline_str, trigger_string):
    """
    cmdline_str is the string of the command line
    trigger_string is the trigger string, to be removed
    """
    cmdline = salt.utils.args.shlex_split(cmdline_str[len(trigger_string):])
    # Remove slack url parsing
    #  Translate target=<http://host.domain.net|host.domain.net>
    #  to target=host.domain.net
    cmdlist = []
    for cmditem in cmdline:
        pattern = r'(?P<begin>.*)(<.*\|)(?P<url>.*)(>)(?P<remainder>.*)'
        mtch = re.match(pattern, cmditem)
        if mtch:
            origtext = mtch.group('begin') + mtch.group('url') + mtch.group('remainder')
            cmdlist.append(origtext)
        else:
            cmdlist.append(cmditem)
    return cmdlist


# m_data -> m_data, _text -> test, all_slack_users -> all_slack_users,
def control_message_target(slack_user_name, text, loaded_groups, trigger_string):
    """Returns a tuple of (target, cmdline,) for the response

    Raises IndexError if a user can't be looked up from all_slack_users

    Returns (False, False) if the user doesn't have permission

    These are returned together because the commandline and the targeting
    interact with the group config (specifically aliases and targeting configuration)
    so taking care of them together works out.

    The cmdline that is returned is the actual list that should be
    processed by salt, and not the alias.

    """

    # Trim the trigger string from the front
    # cmdline = _text[1:].split(' ', 1)
    cmdline = commandline_to_list(text, trigger_string)
    permitted_group = can_user_run(slack_user_name, cmdline[0], loaded_groups)
    log.debug("slack_user_name is {} and the permitted group is {}".format(slack_user_name, permitted_group))
    if not permitted_group:
        return (False, False)
    if not slack_user_name:
        return (False, False)

    # maybe there are aliases, so check on that
    if cmdline[0] in permitted_group[1].get('aliases', {}).keys():
        use_cmdline = commandline_to_list(permitted_group[1]['aliases'][cmdline[0]], "")
    else:
        use_cmdline = cmdline
    target = get_target(permitted_group, cmdline, use_cmdline)
    return (target, use_cmdline,)


def message_text(m_data):
    """
    Raises ValueError if a value doesn't work out, and TypeError if
    this isn't a message type
    """
    if m_data.get('type') != 'message':
        raise TypeError("This isn't a message")
    # Edited messages have text in message
    _text = m_data.get('text', None) or m_data.get('message', {}).get('text', None)
    try:
        log.info("Message is {}".format(_text))  # this can violate the ascii codec
    except UnicodeEncodeError as uee:
        log.warn("Got a message that I couldn't log.  The reason is: {}".format(uee))

    # Convert UTF to string
    _text = json.dumps(_text)
    _text = yaml.safe_load(_text)

    if not _text:
        raise ValueError("_text has no value")
    return _text


def generate_triggered_messages(token, trigger_string, groups, groups_pillar_name):
    """slack_token = string
    trigger_string = string
    input_valid_users = set
    input_valid_commands = set

    When the trigger_string prefixes the message text, yields a dictionary of {
        "message_data": m_data,
        "cmdline": cmdline_list, # this is a list
        "channel": channel,
        "user": m_data['user'],
        "slack_client": sc
    }

    else yields {"message_data": m_data} and the caller can handle that

    When encountering an error (e.g. invalid message), yields {}, the caller can proceed to the next message

    When the websocket being read from has given up all its messages, yields {"done": True} to
    indicate that the caller has read all of the relevent data for now, and should continue
    its own processing and check back for more data later.

    This relies on the caller sleeping between checks, otherwise this could flood
    """
    sc = slackclient.SlackClient(token)
    slack_connect = sc.rtm_connect()
    all_slack_users = get_slack_users(token)  # re-checks this if we have an negative lookup result
    all_slack_channels = get_slack_channels(token)  # re-checks this if we have an negative lookup result

    def just_data(m_data):
        """Always try to return the user and channel anyway"""
        user_id = m_data.get('user')
        channel_id = m_data.get('channel')
        if channel_id.startswith('D'):  # private chate with bot user
            channel_name = "private chat"
        else:
            channel_name = all_slack_channels.get(channel_id)
        data = {
            "message_data": m_data,
            "user_name": all_slack_users.get(user_id),
            "channel_name": channel_name
        }
        if not data["user_name"]:
            all_slack_users.clear()
            all_slack_users.update(get_slack_users(token))
            data["user_name"] = all_slack_users.get(user_id)
        if not data["channel_name"]:
            all_slack_channels.clear()
            all_slack_channels.update(get_slack_channels(token))
            data["channel_name"] = all_slack_channels.get(channel_id)
        return data

    for sleeps in (5, 10, 30, 60):
        if slack_connect:
            break
        else:
            # see https://api.slack.com/docs/rate-limits
            log.warning("Slack connection is invalid.  Server: {}, sleeping {}".format(sc.server, sleeps))
            time.sleep(sleeps)  # respawning too fast makes the slack API unhappy about the next reconnection
    else:
        raise UserWarning("Connection to slack is still invalid, giving up: {}".format(slack_connect))  # Boom!
    while True:
        msg = sc.rtm_read()
        for m_data in msg:
            try:
                msg_text = message_text(m_data)
            except (ValueError, TypeError) as msg_err:
                log.debug("Got an error from trying to get the message text {}".format(msg_err))
                yield {"message_data": m_data}  # Not a message type from the API?
                continue

            # Find the channel object from the channel name
            channel = sc.server.channels.find(m_data['channel'])
            data = just_data(m_data)
            if msg_text.startswith(trigger_string):
                loaded_groups = get_config_groups(groups, groups_pillar_name)
                user_id = m_data.get('user')  # slack user ID, e.g. 'U11011'
                if not data.get('user_name'):
                    log.error("The user {} can't be looked up via slack.  What has happened here?".format(
                        m_data.get('user')))
                    channel.send_message("The user {} can't be looked up via slack.  Not running {}".format(
                        user_id, msg_text))
                    yield {"message_data": m_data}
                    continue
                (target, cmdline) = control_message_target(
                        data['user_name'], msg_text, loaded_groups, trigger_string)
                log.debug("Got target: {}, cmdline: {}".format(target, cmdline))
                if target and cmdline:
                    yield {
                        "message_data": m_data,
                        "slack_client": sc,
                        "channel": channel,
                        "user": user_id,
                        "user_name": all_slack_users[user_id],
                        "cmdline": cmdline,
                        "target": target
                    }
                    continue
                else:
                    channel.send_message('{}, {} is not allowed to use command {}.'.format(
                        user_id, all_slack_users[user_id], cmdline))
                    yield data
                    continue
            else:
                yield data
                continue
        yield {"done": True}


def get_target(permitted_group, cmdline, alias_cmdline):
    """When we are permitted to run a command on a target, look to see
    what the default targeting is for that group, and for that specific
    command (if provided).

    It's possible for None or False to be the result of either, which means
    that it's expected that the caller provide a specific target.

    If no configured target is provided, the command line will be parsed
    for target=foo and tgt_type=bar

    Test for this:
    h = {'aliases': {}, 'commands': {'cmd.run', 'pillar.get'},
        'default_target': {'target': '*', 'tgt_type': 'glob'},
        'targets': {'pillar.get': {'target': 'you_momma', 'tgt_type': 'list'}},
        'users': {'dmangot', 'jmickle', 'pcn'}}
    f = {'aliases': {}, 'commands': {'cmd.run', 'pillar.get'},
         'default_target': {}, 'targets': {},'users': {'dmangot', 'jmickle', 'pcn'}}

    g = {'aliases': {}, 'commands': {'cmd.run', 'pillar.get'},
         'default_target': {'target': '*', 'tgt_type': 'glob'},
         'targets': {}, 'users': {'dmangot', 'jmickle', 'pcn'}}

    Run each of them through ``get_configured_target(("foo", f), "pillar.get")`` and confirm a valid target

    """
    null_target = {"target": None, "tgt_type": None}

    def check_cmd_against_group(cmd):
        """Validate cmd against the group to return the target, or a null target"""
        name, group_config = permitted_group
        target = group_config.get('default_target')
        if not target:  # Empty, None, or False
            target = null_target
        if group_config.get('targets'):
            if group_config['targets'].get(cmd):
                target = group_config['targets'][cmd]
        if not target.get("target"):
            log.debug("Group {} is not configured to have a target for cmd {}.".format(name, cmd))
        return target

    for this_cl in cmdline, alias_cmdline:
        _, kwargs = parse_args_and_kwargs(this_cl)
        if 'target' in kwargs:
            log.debug("target is in kwargs {}.".format(kwargs))
            if 'tgt_type' in kwargs:
                log.debug("tgt_type is in kwargs {}.".format(kwargs))
                return {"target": kwargs['target'], "tgt_type": kwargs['tgt_type']}
            return {"target": kwargs['target'], "tgt_type": 'glob'}

    for this_cl in cmdline, alias_cmdline:
        checked = check_cmd_against_group(this_cl[0])
        log.debug("this cmdline has target {}.".format(this_cl))
        if checked.get("target"):
            return checked
    return null_target


# emulate the yaml_out output formatter.  It relies on a global __opts__ object which we can't
# obviously pass in

def format_return_text(data, **kwargs):  # pylint: disable=unused-argument
    '''
    Print out YAML using the block mode
    '''
    params = dict(Dumper=OrderedDumper)
    if 'output_indent' not in __opts__:
        # default indentation
        params.update(default_flow_style=False)
    elif __opts__['output_indent'] >= 0:
        # custom indent
        params.update(default_flow_style=False,
                      indent=__opts__['output_indent'])
    else:  # no indentation
        params.update(default_flow_style=True,
                      indent=0)
    try:
        return yaml.dump(data, **params).replace("\n\n", "\n")
    # pylint: disable=broad-except
    except Exception as exc:
        import pprint
        log.exception('Exception {0} encountered when trying to serialize {1}'.format(
            exc, pprint.pformat(data)))
        return "Got an error trying to serialze/clean up the response"


def parse_args_and_kwargs(cmdline):
    """
    cmdline: list

    returns tuple of: args (list), kwargs (dict)
    """
    # Parse args and kwargs
    args = []
    kwargs = {}

    if len(cmdline) > 1:
        for item in cmdline[1:]:
            if '=' in item:
                (key, value) = item.split('=', 1)
                kwargs[key] = value
            else:
                args.append(item)
    return (args, kwargs)


def get_jobs_from_runner(outstanding_jids):
    """
    Given a list of job_ids, return a dictionary of those job_ids that have completed and their results.

    Query the salt event bus via the jobs runner.  jobs.list_job will show a job in progress,
    jobs.lookup_jid will return a job that has completed.

    returns a dictionary of job id: result
    """
    # Can't use the runner because of https://github.com/saltstack/salt/issues/40671
    runner = salt.runner.RunnerClient(__opts__)
    # log.debug("Getting job IDs {} will run via runner jobs.lookup_jid".format(outstanding_jids))
    mm = salt.minion.MasterMinion(__opts__)
    source = __opts__.get('ext_job_cache')
    if not source:
        source = __opts__.get('master_job_cache')

    results = dict()
    for jid in outstanding_jids:
        # results[jid] = runner.cmd('jobs.lookup_jid', [jid])
        if mm.returners['{}.get_jid'.format(source)](jid):
            jid_result = runner.cmd('jobs.list_job', [jid]).get('Result', {})
            # emulate lookup_jid's return, which is just minion:return
            # pylint is tripping
            # pylint: disable=missing-whitespace-after-comma
            job_data = json.dumps({key:val['return'] for key, val in jid_result.items()})
            results[jid] = yaml.load(job_data)

    return results


def run_commands_from_slack_async(message_generator, fire_all, tag, control, interval=1):
    """Pull any pending messages from the message_generator, sending each
    one to either the event bus, the command_async or both, depending on
    the values of fire_all and command
    """

    outstanding = dict()  # set of job_id that we need to check for

    while True:
        log.debug("Sleeping for interval of {}".format(interval))
        time.sleep(interval)
        # Drain the slack messages, up to 10 messages at a clip
        count = 0
        for msg in message_generator:
            # The message_generator yields dicts.  Leave this loop
            # on a dict that looks like {"done": True} or when we've done it
            # 10 times without taking a break.
            log.debug("Got a message from the generator: {}".format(msg.keys()))
            if count > 10:
                log.warn("Breaking in getting messages because count is exceeded")
                break
            if len(msg) == 0:
                count += 1
                log.warn("len(msg) is zero")
                continue  # This one is a dud, get the next message
            if msg.get("done"):
                log.debug("msg is done")
                break
            if fire_all:
                log.debug("Firing message to the bus with tag: {}".format(tag))
                fire('{0}/{1}'.format(tag, msg['message_data'].get('type')), msg)
            if control and (len(msg) > 1) and msg.get('cmdline'):
                jid = run_command_async(msg)
                log.debug("Submitted a job and got jid: {}".format(jid))
                outstanding[jid] = msg  # record so we can return messages to the caller
                msg['channel'].send_message("@{}'s job is submitted as salt jid {}".format(msg['user_name'], jid))
            count += 1
        start_time = time.time()
        job_status = get_jobs_from_runner(outstanding.keys())  # dict of job_ids:results are returned
        log.debug("Getting {} jobs status took {} seconds".format(len(job_status), time.time() - start_time))
        for jid, result in job_status.items():
            if result:
                log.debug("ret to send back is {}".format(result))
                # formatting function?
                this_job = outstanding[jid]
                return_text = format_return_text(result)
                return_prefix = "@{}'s job `{}` (id: {}) (target: {}) returned".format(
                    this_job["user_name"], this_job["cmdline"], jid, this_job["target"])
                this_job['channel'].send_message(return_prefix)
                r = this_job["slack_client"].api_call(
                    "files.upload", channels=this_job['channel'].id, files=None,
                    content=return_text)
                # Handle unicode return
                log.debug("Got back {} via the slack client".format(r))
                resp = yaml.safe_load(json.dumps(r))
                if 'ok' in resp and resp['ok'] is False:
                    this_job['channel'].send_message('Error: {0}'.format(resp['error']))
                del outstanding[jid]


def run_command_async(msg):

    """
    :type message_generator: generator of dict
    :param message_generator: Generates messages from slack that should be run

    :type fire_all: bool
    :param fire_all: Whether to also fire messages to the event bus

    :type tag: str
    :param tag: The tag to send to use to send to the event bus

    :type interval: int
    :param interval: time to wait between ending a loop and beginning the next

    """
    log.debug("Going to run a command async")
    runner_functions = sorted(salt.runner.Runner(__opts__).functions)
    # Parse args and kwargs
    cmd = msg['cmdline'][0]

    args, kwargs = parse_args_and_kwargs(msg['cmdline'])
    # Check for target. Otherwise assume None
    target = msg["target"]["target"]
    # Check for tgt_type. Otherwise assume glob
    tgt_type = msg["target"]['tgt_type']
    log.debug("target_type is: {}".format(tgt_type))

    if cmd in runner_functions:
        runner = salt.runner.RunnerClient(__opts__)
        log.debug("Command {} will run via runner_functions".format(cmd))
        # pylint is tripping
        # pylint: disable=missing-whitespace-after-comma
        job_id_dict = runner.async(cmd, {"args": args, "kwargs": kwargs})
        job_id = job_id_dict['jid']

    # Default to trying to run as a client module.
    else:
        local = salt.client.LocalClient()
        log.debug("Command {} will run via local.cmd_async, targeting {}".format(cmd, target))
        log.debug("Running {}, {}, {}, {}, {}".format(str(target), cmd, args, kwargs, str(tgt_type)))
        # according to https://github.com/saltstack/salt-api/issues/164, tgt_type has changed to expr_form
        job_id = local.cmd_async(str(target), cmd, arg=args, kwargs=kwargs, tgt_type=str(tgt_type))
        log.info("ret from local.cmd_async is {}".format(job_id))
    return job_id


def start(token,
          control=False,
          trigger="!",
          groups=None,
          groups_pillar_name=None,
          fire_all=False,
          tag='salt/engines/slack'):
    '''
    Listen to slack events and forward them to salt, new version
    '''

    if (not token) or (not token.startswith('xoxb')):
        time.sleep(2)  # don't respawn too quickly
        log.error("Slack bot token not found, bailing...")
        raise UserWarning('Slack Engine bot token not configured')

    try:
        message_generator = generate_triggered_messages(token, trigger, groups, groups_pillar_name)
        run_commands_from_slack_async(message_generator, fire_all, tag, control)
    except Exception:
        raise Exception("{}".format(traceback.format_exc()))
