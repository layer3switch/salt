# -*- coding: utf-8 -*-
'''
.. versionadded:: 2016.3.0

Manage Mac OSX local directory passwords and policies.

Note that it is usually better to apply password policies through the creation
of a configuration profile.
'''
# Authentication concepts reference:
# https://developer.apple.com/library/mac/documentation/Networking/Conceptual/Open_Directory/openDirectoryConcepts/openDirectoryConcepts.html#//apple_ref/doc/uid/TP40000917-CH3-CIFCAIBB

from __future__ import absolute_import

# Import salt libs
import salt.utils
import logging

log = logging.getLogger(__name__)  # Start logging

__virtualname__ = 'shadow'


def __virtual__():
    if not salt.utils.is_darwin():
        return False, 'Not Darwin'

    return __virtualname__


def _get_dscl_data_value(name, key):
    cmd = 'dscl . -read /Users/{0} {1}'.format(name, key)
    ret = __salt__['cmd.run'](cmd)
    if ': ' in ret:
        value = ret.split(': ')[1]
        return value
    if ':\n' in ret:
        value = ret.split(':\n')[1]
        return value
    return ret


def _get_account_policy_data_value(name, key):

    cmd = 'dscl . -readpl /Users/{0} accountPolicyData {1}'.format(name, key)
    ret = __salt__['cmd.run'](cmd)
    if ': ' in ret:
        value = ret.split(': ')[1]
        return value
    if ':\n' in ret:
        value = ret.split(':\n')[1]
        return value
    return ret


def _get_account_policy(name):
    cmd = 'pwpolicy -u {0} -getpolicy'
    ret = __salt__['cmd.run'](cmd)
    if ret:
        policy_list = ret.split(' ')
        policy_dict = {}
        for policy in policy_list:
            key, value = policy.split('=')
            policy_dict[key] = value
        return policy_dict
    else:
        return False


def info(name):
    '''
    Return information for the specified user

    CLI Example:

    .. code-block:: bash

        salt '*' mac_shadow.info admin
    '''
    ret = {}
    ret['name'] = _get_dscl_data_value(name, 'name')
    ret['passwd'] = _get_dscl_data_value(name, 'passwd')

    ret['account_created'] = _get_account_policy_data_value(name, 'creationTime')
    ret['login_failed_count'] = _get_account_policy_data_value(name, 'failedLoginCount')
    ret['login_failed_last'] = _get_account_policy_data_value(name, 'failedLoginTimestamp')
    ret['lstchg'] = _get_account_policy_data_value(name, 'passwordLastSetTime')

    ret['max'] = get_maxdays(name)
    ret['expire'] = get_expire(name)
    ret['change'] = get_change(name)
    ret['min'] = 'Unavailable'
    ret['warn'] = 'Unavailable'
    ret['inact'] = 'Unavailable'

    return ret


def set_maxdays(name, days):
    minutes = days * 24 * 60
    cmd = 'pwpolicy -u {0} -setpolicy ' \
          'maxMinutesUntilChangePassword={1}'.format(name, minutes)


def get_maxdays(name):
    policies = _get_account_policy(name)
    max_minutes = policies['maxMinutesUntilChangePassword']
    return max_minutes / 24 / 60


def set_mindays(name, days):
    return False, 'not available on OS X'


def set_inactdays(name, days):
    return False, 'not available on OS X'


def set_warndays(name, days):
    return False, 'not available on OS X'


def set_change(name, date):
    '''
    Sets the time at which the password expires (in seconds since the UNIX
    epoch). See ``man 8 usermod`` on NetBSD and OpenBSD or ``man 8 pw`` on
    FreeBSD.

    A value of ``0`` sets the password to never expire.

    CLI Example:

    .. code-block:: bash

        salt '*' shadow.set_change username 1419980400
    '''
    cmd = 'pwpolicy -u {0} -setpolicy usingExpirationDate=1 ' \
          'expirationDateGMT={1}'.format(name, date)
    __salt__['cmd.run'](cmd)

    new = get_change(name)

    return new == date


def get_change(name):
    policies = _get_account_policy(name)
    if policies['expirationDateGMT']:
        return policies['expirationDateGMT']
    else:
        return 'Value not set'


def set_expire(name, date):
    '''
    Sets the time at which the account expires (in seconds since the UNIX
    epoch). See ``man 8 usermod`` on NetBSD and OpenBSD or ``man 8 pw`` on
    FreeBSD.

    A value of ``0`` sets the account to never expire.

    CLI Example:

    .. code-block:: bash

        salt '*' shadow.set_expire username 1419980400
    '''
    cmd = 'pwpolicy -u {0} -setpolicy usingHardExpirationDate=1 ' \
          'hardExpireDateGMT={1}'.format(name, date)
    __salt__['cmd.run'](cmd)

    new = get_expire(name)

    return new == date


def get_expire(name):
    policies = _get_account_policy(name)
    if policies['hardExpireDateGMT']:
        return policies['hardExpireDateGMT']
    else:
        return 'Value not set'


def del_password(name):
    '''
    Delete the account password

    :param str name: The user name of the account

    CLI Example:

    .. code-block:: bash

        salt '*' shadow.del_password username
    '''
    # Re-order authentication authority and remove ShadowHashData
    cmd = "dscl . -create /Users/{0} '*'"
    __salt__['cmd.retcode'](cmd)

    new = _get_dscl_data_value(name, 'passwd')

    return new == '*'


def set_password(name, password):
    '''
    Set the password for a named user (insecure, the password will be in the
    process list while the command is running).

    :param str name: The name of the local user, which is assumed to be in the
    local directory service.

    :param str password: The plaintext password to set

    CLI Example:

    .. code-block:: bash

        salt '*' mac_shadow.set_password macuser macpassword
    '''

    cmd = 'dscl . -passwd /User/{0} {1}'.format(name, password)
    ret = __salt__['cmd.retcode'](cmd)
    if ret:
        return False
    else:
        return True
