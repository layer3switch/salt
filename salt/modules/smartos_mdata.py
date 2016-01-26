# -*- coding: utf-8 -*-
'''
Module for managaging metadata on SmartOS

.. versionadded:: Boron

:maintainer:    Jorge Schrauwen <sjorge@blackdot.be>
:maturity:      new
:platform:      smartos
'''
from __future__ import absolute_import

# Import Python libs
import logging

# Import Salt libs
import salt.utils
import salt.utils.decorators as decorators

log = logging.getLogger(__name__)

# Function aliases
__func_alias__ = {
    'list_': 'list',
    'get_': 'get',
    'put_': 'put',
    'delete_': 'delete',
}

# Define the module's virtual name
__virtualname__ = 'mdata'


@decorators.memoize
def _check_mdata_list():
    '''
    looks to see if mdata-list is present on the system
    '''
    return salt.utils.which('mdata-list')


@decorators.memoize
def _check_mdata_get():
    '''
    looks to see if mdata-get is present on the system
    '''
    return salt.utils.which('mdata-get')


@decorators.memoize
def _check_mdata_put():
    '''
    looks to see if mdata-put is present on the system
    '''
    return salt.utils.which('mdata-put')


@decorators.memoize
def _check_mdata_delete():
    '''
    looks to see if mdata-delete is present on the system
    '''
    return salt.utils.which('mdata-delete')


def __virtual__():
    '''
    Provides mdata only on SmartOS
    '''
    if salt.utils.is_smartos_zone() and _check_mdata_list():
        return __virtualname__
    return (
        False,
        '{0} module can only be loaded on SmartOS zones'.format(
            __virtualname__
        )
    )


def list_():
    '''
    List available metadata

    CLI Example:

    .. code-block:: bash

        salt '*' mdata.list
    '''
    mdata = _check_mdata_list()
    if mdata:
        cmd = '{0}'.format(mdata)
        return __salt__['cmd.run'](cmd).splitlines()
    return {}


def get_(*keyname):
    '''
    Get metadata

    keyname : string
        name of key

    .. note::

        If no keynames are specified, we get all properties

    CLI Example:

    .. code-block:: bash

        salt '*' mdata.get salt:role
        salt '*' mdata.get user-script salt:role
    '''
    mdata = _check_mdata_get()
    valid_keynames = list_()
    ret = {}

    if len(keyname) == 0:
        keyname = valid_keynames

    for k in keyname:
        if mdata and k in valid_keynames:
            cmd = '{0} {1}'.format(mdata, k)
            ret[k] = __salt__['cmd.run'](cmd)
        else:
            ret[k] = ''

    return ret


def put_(keyname, val):
    '''
    Put metadata

    prop : string
        name of property
    val : string
        value to set

    CLI Example:

    .. code-block:: bash

        salt '*' mdata.list
    '''
    mdata = _check_mdata_put()
    ret = {}

    if mdata:
        cmd = 'echo {2} | {0} {1}'.format(mdata, keyname, val)
        ret = __salt__['cmd.run_all'](cmd, python_shell=True)

    return ret['retcode'] == 0


def delete_(*keyname):
    '''
    Delete metadata

    prop : string
        name of property

    CLI Example:

    .. code-block:: bash

        salt '*' mdata.get salt:role
        salt '*' mdata.get user-script salt:role
    '''
    mdata = _check_mdata_delete()
    valid_keynames = list_()
    ret = {}

    for k in keyname:
        if mdata and k in valid_keynames:
            cmd = '{0} {1}'.format(mdata, k)
            ret[k] = __salt__['cmd.run_all'](cmd)['retcode'] == 0
        else:
            ret[k] = True

    return ret

# vim: tabstop=4 expandtab shiftwidth=4 softtabstop=4
