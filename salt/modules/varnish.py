# -*- coding: utf-8 -*-
'''
Support for Varnish

.. versionadded:: Helium

.. note::

    These functions are designed to work with all implementations of Varnish
    from 3.x onwards
'''

# Import python libs
import logging
import pipes
import re
import shlex

# Import salt libs
import salt.utils

log = logging.getLogger(__name__)

# Define the module's virtual name
__virtualname__ = 'varnish'


def __virtual__():
    '''
    Only load the module if varnish is installed
    '''
    if salt.utils.which('varnishd') and salt.utils.which('varnishadm'):
        return __virtualname__
    return False


def _run_varnishadm(cmd, params=[], **kwargs):
    '''
    Execute varnishadm command
    return the output of the command

    cmd
        The command to run in varnishadm

    params
        Any additional args to add to the command line

    kwargs
        Additional options to pass to the salt cmd.run_all function
    '''
    sanitized_params = [pipes.quote(p) for p in params if not p == None]
    cmd = 'varnishadm {0} {1}'.format(cmd, ' '.join(sanitized_params))
    log.debug('Executing: {0}'.format(cmd))
    return __salt__['cmd.run_all'](cmd, **kwargs)


def version():
    '''
    Return server version from varnishd -V

    CLI Example:

    .. code-block:: bash

        salt '*' varnish.version
    '''
    cmd = 'varnishd -V'
    out = __salt__['cmd.run'](cmd)
    ret = re.search(r'\(varnish-([^\)]+)\)', out).group(1)
    return ret


def ban(ban_expression):
    '''
    Add ban to the varnish cache

    CLI Example:

    .. code-block:: bash

        salt '*' varnish.ban ban_expression
    '''
    return _run_varnishadm('ban', [ban_expression])['retcode'] == 0


def ban_list():
    '''
    List varnish cache current bans

    CLI Example:

    .. code-block:: bash

        salt '*' varnish.ban_list
    '''
    ret = _run_varnishadm('ban.list')
    if ret['retcode']:
        return False
    else:
        return ret['stdout'].split('\n')[1:]


def purge():
    '''
    Purge the varnish cache

    CLI Example:

    .. code-block:: bash

        salt '*' varnish.purge
    '''
    return ban('req.url ~ .')


def param_set(param, value):
    '''
    Set a param in varnish cache

    CLI Example:

    .. code-block:: bash

        salt '*' varnish.param_set param value
    '''
    return _run_varnishadm('param.set', [param, str(value)])['retcode'] == 0


def param_show(param=None):
    '''
    Show params of varnish cache

    CLI Example:

    .. code-block:: bash

        salt '*' varnish.param_show param
    '''
    ret = _run_varnishadm('param.show', [param])
    if ret['retcode']:
        return False
    else:
        result = {}
        for line in ret['stdout'].split('\n'):
            m = re.search(r'^(\w+)\s+(.*)$', line)
            result[m.group(1)] = m.group(2)
            if param:
                # When we ask to varnishadm for a specific param, it gives full
                # info on what that parameter is, so we just process the first
                # line and we get out of the loop
                break
        return result
