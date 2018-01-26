# -*- coding: utf-8 -*-
'''
Publish a command from a minion to a target
'''
from __future__ import absolute_import, unicode_literals, print_function

# Import python libs
import time
import logging

# Import salt libs
import salt.crypt
import salt.payload
import salt.transport
import salt.utils.args
import salt.utils.versions
from salt.exceptions import SaltReqTimeoutError, SaltInvocationError

log = logging.getLogger(__name__)

__virtualname__ = 'publish'


def __virtual__():
    return __virtualname__ if __opts__.get('transport', '') in ('zeromq', 'tcp') else False


def _parse_args(arg):
    '''
    yamlify `arg` and ensure it's outermost datatype is a list
    '''
    yaml_args = salt.utils.args.yamlify_arg(arg)

    if yaml_args is None:
        return []
    elif not isinstance(yaml_args, list):
        return [yaml_args]
    else:
        return yaml_args


def _publish(
        tgt,
        fun,
        arg=None,
        tgt_type='glob',
        returner='',
        timeout=5,
        form='clean',
        wait=False,
        via_master=None):
    '''
    Publish a command from the minion out to other minions, publications need
    to be enabled on the Salt master and the minion needs to have permission
    to publish the command. The Salt master will also prevent a recursive
    publication loop, this means that a minion cannot command another minion
    to command another minion as that would create an infinite command loop.

    The arguments sent to the minion publish function are separated with
    commas. This means that for a minion executing a command with multiple
    args it will look like this::

        salt system.example.com publish.publish '*' user.add 'foo,1020,1020'

    CLI Example:

    .. code-block:: bash

        salt system.example.com publish.publish '*' cmd.run 'ls -la /tmp'
    '''
    if 'master_uri' not in __opts__:
        log.error('Cannot run publish commands without a connection to a salt master. No command sent.')
        return {}
    if fun.startswith('publish.'):
        log.info('Cannot publish publish calls. Returning {}')
        return {}

    arg = _parse_args(arg)

    if via_master:
        if 'master_uri_list' not in __opts__:
            raise SaltInvocationError(message='Could not find list of masters \
                    in minion configuration but `via_master` was specified.')
        else:
            # Find the master in the list of master_uris generated by the minion base class
            matching_master_uris = [master for master
                    in __opts__['master_uri_list']
                    if '//{0}:'.format(via_master)
                    in master]

            if not matching_master_uris:
                raise SaltInvocationError('Could not find match for {0} in \
                list of configured masters {1} when using `via_master` option'.format(
                    via_master, __opts__['master_uri_list']))

            if len(matching_master_uris) > 1:
                # If we have multiple matches, consider this a non-fatal error
                # and continue with whatever we found first.
                log.warning('The `via_master` flag found '
                            'more than one possible match found for %s when '
                            'evaluating list %s',
                            via_master, __opts__['master_uri_list'])
            master_uri = matching_master_uris.pop()
    else:
        # If no preference is expressed by the user, just publish to the first master
        # in the list.
        master_uri = __opts__['master_uri']

    log.info('Publishing \'%s\' to %s', fun, master_uri)
    auth = salt.crypt.SAuth(__opts__)
    tok = auth.gen_token('salt')
    load = {'cmd': 'minion_pub',
            'fun': fun,
            'arg': arg,
            'tgt': tgt,
            'tgt_type': tgt_type,
            'ret': returner,
            'tok': tok,
            'tmo': timeout,
            'form': form,
            'id': __opts__['id'],
            'no_parse': __opts__.get('no_parse', [])}

    channel = salt.transport.Channel.factory(__opts__, master_uri=master_uri)
    try:
        peer_data = channel.send(load)
    except SaltReqTimeoutError:
        return '\'{0}\' publish timed out'.format(fun)
    if not peer_data:
        return {}
    # CLI args are passed as strings, re-cast to keep time.sleep happy
    if wait:
        loop_interval = 0.3
        matched_minions = set(peer_data['minions'])
        returned_minions = set()
        loop_counter = 0
        while len(returned_minions ^ matched_minions) > 0:
            load = {'cmd': 'pub_ret',
                    'id': __opts__['id'],
                    'tok': tok,
                    'jid': peer_data['jid']}
            ret = channel.send(load)
            returned_minions = set(ret.keys())

            end_loop = False
            if returned_minions >= matched_minions:
                end_loop = True
            elif (loop_interval * loop_counter) > timeout:
                # This may be unnecessary, but I am paranoid
                if len(returned_minions) < 1:
                    return {}
                end_loop = True

            if end_loop:
                if form == 'clean':
                    cret = {}
                    for host in ret:
                        cret[host] = ret[host]['ret']
                    return cret
                else:
                    return ret
            loop_counter = loop_counter + 1
            time.sleep(loop_interval)
    else:
        time.sleep(float(timeout))
        load = {'cmd': 'pub_ret',
                'id': __opts__['id'],
                'tok': tok,
                'jid': peer_data['jid']}
        ret = channel.send(load)
        if form == 'clean':
            cret = {}
            for host in ret:
                cret[host] = ret[host]['ret']
            return cret
        else:
            return ret


def publish(tgt,
            fun,
            arg=None,
            tgt_type='glob',
            returner='',
            timeout=5,
            via_master=None,
            expr_form=None):
    '''
    Publish a command from the minion out to other minions.

    Publications need to be enabled on the Salt master and the minion
    needs to have permission to publish the command. The Salt master
    will also prevent a recursive publication loop, this means that a
    minion cannot command another minion to command another minion as
    that would create an infinite command loop.

    The ``tgt_type`` argument is used to pass a target other than a glob into
    the execution, the available options are:

    - glob
    - pcre
    - grain
    - grain_pcre
    - pillar
    - pillar_pcre
    - ipcidr
    - range
    - compound

    .. versionchanged:: 2017.7.0
        The ``expr_form`` argument has been renamed to ``tgt_type``, earlier
        releases must use ``expr_form``.

    Note that for pillar matches must be exact, both in the pillar matcher
    and the compound matcher. No globbing is supported.

    The arguments sent to the minion publish function are separated with
    commas. This means that for a minion executing a command with multiple
    args it will look like this:

    .. code-block:: bash

        salt system.example.com publish.publish '*' user.add 'foo,1020,1020'
        salt system.example.com publish.publish 'os:Fedora' network.interfaces '' grain

    CLI Example:

    .. code-block:: bash

        salt system.example.com publish.publish '*' cmd.run 'ls -la /tmp'


    .. admonition:: Attention

        If you need to pass a value to a function argument and that value
        contains an equal sign, you **must** include the argument name.
        For example:

        .. code-block:: bash

            salt '*' publish.publish test.kwarg arg='cheese=spam'

        Multiple keyword arguments should be passed as a list.

        .. code-block:: bash

            salt '*' publish.publish test.kwarg arg="['cheese=spam','spam=cheese']"


    When running via salt-call, the `via_master` flag may be set to specific which
    master the publication should be sent to. Only one master may be specified. If
    unset, the publication will be sent only to the first master in minion configuration.
    '''
    # remember to remove the expr_form argument from this function when
    # performing the cleanup on this deprecation.
    if expr_form is not None:
        salt.utils.versions.warn_until(
            'Fluorine',
            'the target type should be passed using the \'tgt_type\' '
            'argument instead of \'expr_form\'. Support for using '
            '\'expr_form\' will be removed in Salt Fluorine.'
        )
        tgt_type = expr_form

    return _publish(tgt,
                    fun,
                    arg=arg,
                    tgt_type=tgt_type,
                    returner=returner,
                    timeout=timeout,
                    form='clean',
                    wait=True,
                    via_master=via_master)


def full_data(tgt,
              fun,
              arg=None,
              tgt_type='glob',
              returner='',
              timeout=5,
              expr_form=None):
    '''
    Return the full data about the publication, this is invoked in the same
    way as the publish function

    CLI Example:

    .. code-block:: bash

        salt system.example.com publish.full_data '*' cmd.run 'ls -la /tmp'

    .. admonition:: Attention

        If you need to pass a value to a function argument and that value
        contains an equal sign, you **must** include the argument name.
        For example:

        .. code-block:: bash

            salt '*' publish.full_data test.kwarg arg='cheese=spam'

    '''
    # remember to remove the expr_form argument from this function when
    # performing the cleanup on this deprecation.
    if expr_form is not None:
        salt.utils.versions.warn_until(
            'Fluorine',
            'the target type should be passed using the \'tgt_type\' '
            'argument instead of \'expr_form\'. Support for using '
            '\'expr_form\' will be removed in Salt Fluorine.'
        )
        tgt_type = expr_form

    return _publish(tgt,
                    fun,
                    arg=arg,
                    tgt_type=tgt_type,
                    returner=returner,
                    timeout=timeout,
                    form='full',
                    wait=True)


def runner(fun, arg=None, timeout=5):
    '''
    Execute a runner on the master and return the data from the runner
    function

    CLI Example:

    .. code-block:: bash

        salt publish.runner manage.down
    '''
    arg = _parse_args(arg)

    if 'master_uri' not in __opts__:
        return 'No access to master. If using salt-call with --local, please remove.'
    log.info('Publishing runner \'%s\' to %s', fun, __opts__['master_uri'])
    auth = salt.crypt.SAuth(__opts__)
    tok = auth.gen_token('salt')
    load = {'cmd': 'minion_runner',
            'fun': fun,
            'arg': arg,
            'tok': tok,
            'tmo': timeout,
            'id': __opts__['id'],
            'no_parse': __opts__.get('no_parse', [])}

    channel = salt.transport.Channel.factory(__opts__)
    try:
        return channel.send(load)
    except SaltReqTimeoutError:
        return '\'{0}\' runner publish timed out'.format(fun)
