# -*- coding: utf-8 -*-
'''
Manage groups on Mac OS 10.7+
'''

# Import python libs
from __future__ import absolute_import
try:
    import grp
except ImportError:
    pass

# Import Salt Libs
import salt.utils
from salt.exceptions import CommandExecutionError, SaltInvocationError
from salt.modules.mac_user import _dscl, _flush_dscl_cache

# Define the module's virtual name
__virtualname__ = 'group'


def __virtual__():
    global _dscl, _flush_dscl_cache
    if (__grains__.get('kernel') != 'Darwin' or
            __grains__['osrelease_info'] < (10, 7)):
        return False
    _dscl = salt.utils.namespaced_function(_dscl, globals())
    _flush_dscl_cache = salt.utils.namespaced_function(
        _flush_dscl_cache, globals()
    )
    return __virtualname__


def add(name, gid=None, **kwargs):
    '''
    Add the specified group

    CLI Example:

    .. code-block:: bash

        salt '*' group.add foo 3456
    '''
    ### NOTE: **kwargs isn't used here but needs to be included in this
    ### function for compatibility with the group.present state
    if info(name):
        raise CommandExecutionError('Group {0!r} already exists'.format(name))
    if salt.utils.contains_whitespace(name):
        raise SaltInvocationError('Group name cannot contain whitespace')
    if name.startswith('_'):
        raise SaltInvocationError(
            'Salt will not create groups beginning with underscores'
        )
    if gid is not None and not isinstance(gid, int):
        raise SaltInvocationError('gid must be an integer')
    # check if gid is already in use
    gid_list = _list_gids()
    if str(gid) in gid_list:
        raise CommandExecutionError(
            'gid {0!r} already exists'.format(gid)
        )

    cmd = 'dseditgroup -o create '
    if gid:
        cmd += '-i {0} '.format(gid)
    cmd += str(name)
    return __salt__['cmd.retcode'](cmd) == 0


def _list_gids():
    '''
    Return a list of gids in use
    '''
    cmd = __salt__['cmd.run']('dscacheutil -q group | grep gid:',
                              output_loglevel='quiet',
                              python_shell=True)
    data_list = cmd.split()
    for item in data_list:
        if item == 'gid:':
            data_list.remove(item)
    return sorted(set(data_list))


def delete(name):
    '''
    Remove the named group

    CLI Example:

    .. code-block:: bash

        salt '*' group.delete foo
    '''
    if salt.utils.contains_whitespace(name):
        raise SaltInvocationError('Group name cannot contain whitespace')
    if name.startswith('_'):
        raise SaltInvocationError(
            'Salt will not remove groups beginning with underscores'
        )
    if not info(name):
        return True
    cmd = 'dseditgroup -o delete {0}'.format(name)
    return __salt__['cmd.retcode'](cmd) == 0


def adduser(group, name):
    '''
    Add a user in the group.

    CLI Example:

    .. code-block:: bash

         salt '*' group.adduser foo bar

    Verifies if a valid username 'bar' as a member of an existing group 'foo',
    if not then adds it.
    '''
    cmd = 'dscl . -merge /Groups/{0} GroupMembership {1}'.format(group, name)
    return __salt__['cmd.retcode'](cmd) == 0


def deluser(group, name):
    '''
    Remove a user from the group

    .. versionadded:: Boron

    CLI Example:

    .. code-block:: bash

         salt '*' group.deluser foo bar

    Removes a member user 'bar' from a group 'foo'. If group is not present
    then returns True.
    '''
    cmd = 'dscl . -delete /Groups/{0} GroupMembership {1}'.format(group, name)
    return __salt__['cmd.retcode'](cmd) == 0


def members(name, members_list):
    '''
    Replaces members of the group with a provided list.

    .. versionadded:: Boron

    CLI Example:

        salt '*' group.members foo 'user1,user2,user3,...'

    Replaces a membership list for a local group 'foo'.
    '''
    retcode = 1
    grp_info = __salt__['group.info'](name)
    if grp_info and name in grp_info['name']:
        cmd = '/usr/bin/dscl . -delete /Groups/{0} GroupMembership'.format(name)
        retcode = __salt__['cmd.retcode'](cmd) == 0
        for user in members_list.split(','):
            cmd = '/usr/bin/dscl . -merge /Groups/{0} GroupMembership {1}'.format(name, user)
            retcode = __salt__['cmd.retcode'](cmd)
            if not retcode == 0:
                break
            # provided list is '': users previously deleted from group
            else:
                retcode = 0

    return retcode == 0


def info(name):
    '''
    Return information about a group

    CLI Example:

    .. code-block:: bash

        salt '*' group.info foo
    '''
    if salt.utils.contains_whitespace(name):
        raise SaltInvocationError('Group name cannot contain whitespace')
    try:
        # getgrnam seems to cache weirdly, so don't use it
        grinfo = next(iter(x for x in grp.getgrall() if x.gr_name == name))
    except StopIteration:
        return {}
    else:
        return _format_info(grinfo)


def _format_info(data):
    '''
    Return formatted information in a pretty way.
    '''
    return {'name': data.gr_name,
            'gid': data.gr_gid,
            'passwd': data.gr_passwd,
            'members': data.gr_mem}


def getent(refresh=False):
    '''
    Return info on all groups

    CLI Example:

    .. code-block:: bash

        salt '*' group.getent
    '''
    if 'group.getent' in __context__ and not refresh:
        return __context__['group.getent']

    ret = []
    for grinfo in grp.getgrall():
        if not grinfo.gr_name.startswith('_'):
            ret.append(_format_info(grinfo))
    __context__['group.getent'] = ret
    return ret


def chgid(name, gid):
    '''
    Change the gid for a named group

    CLI Example:

    .. code-block:: bash

        salt '*' group.chgid foo 4376
    '''
    if not isinstance(gid, int):
        raise SaltInvocationError('gid must be an integer')
    pre_gid = __salt__['file.group_to_gid'](name)
    pre_info = info(name)
    if not pre_info:
        raise CommandExecutionError('Group {0!r} does not exist'.format(name))
    if gid == pre_info['gid']:
        return True
    cmd = 'dseditgroup -o edit -i {0} {1}'.format(gid, name)
    return __salt__['cmd.retcode'](cmd) == 0
