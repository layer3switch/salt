# -*- coding: utf-8 -*-
'''
Glues the VMware vSphere Execution Module to the VMware ESXi Proxy Minions to the
:doc:`esxi proxymodule </ref/proxy/all/salt.proxy.esxi>`.

.. versionadded:: 2015.8.4

Depends: :doc:`vSphere Remote Execution Module (salt.modules.vsphere)
</ref/modules/all/salt.modules.vsphere>`

For documentation on commands that you can direct to an ESXi host via proxy,
look in the documentation for :doc:`salt.modules.vsphere
</ref/modules/all/salt.modules.vsphere>`.

This execution module calls through to a function in the ESXi proxy module
called ``ch_config``, which looks up the function passed in the ``command``
parameter in :doc:`salt.modules.vsphere </ref/modules/all/salt.modules.vsphere>`
and calls it.

To execute commands with an ESXi Proxy Minion using the vSphere Execution Module,
use the ``esxi.cmd <vsphere-function-name`` syntax:

.. code-block:: bash

    salt 'esxi-proxy' esxi.cmd system_info

'''
from __future__ import absolute_import

# Import python libs
import logging
import salt.utils


log = logging.getLogger(__name__)

__proxyenabled__ = ['esxi']
__virtualname__ = 'esxi'


def __virtual__():
    '''
    Only work on proxy
    '''
    if salt.utils.is_proxy():
        return __virtualname__
    return False


def cmd(command, *args, **kwargs):
    proxy_prefix = __opts__['proxy']['proxytype']
    proxy_cmd = proxy_prefix + '.ch_config'

    host = __pillar__['proxy']['host']
    username, password = __proxy__[proxy_prefix + '.find_credentials'](host)

    kwargs['host'] = host
    kwargs['username'] = username
    kwargs['password'] = password
    kwargs['protocol'] = __pillar__['proxy'].get('protocol')
    kwargs['port'] = __pillar__['proxy'].get('port')
    return __proxy__[proxy_cmd](command, *args, **kwargs)
