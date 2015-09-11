# -*- coding: utf-8 -*-
'''
State to manage monitoring in Zenoss.

.. versionadded:: Boron

This state module depends on the 'zenoss' Salt execution module.

Allows for setting a state of minions in Zenoss using the Zenoss API. Currently Zenoss 4.x is supported.

.. code-block:: yaml

    enable_monitoring:
      zenoss.monitored:
        - name: web01.example.com
        - device_class: /Servers/Linux
        - collector: localhost
'''

from __future__ import absolute_import
import logging

log = logging.getLogger(__name__)


def __virtual__():
    '''
    Only load if the Zenoss execution module is available.
    '''
    if 'zenoss.add_device' in __salt__:
        return 'zenoss'


def monitored(name, device_class=None, collector='localhost', prod_state=None):
    '''
    Ensure a device is monitored. The 'name' given will be used for Zenoss device name and should be resolvable.

    .. code-block:: yaml

        enable_monitoring:
          zenoss.monitored:
            - name: web01.example.com
            - device_class: /Servers/Linux
            - collector: localhost
            - prod_state: 1000
    '''

    ret = {}
    ret['name'] = name

    # If device is already monitored, return early
    device = __salt__['zenoss.find_device'](name)
    if device:
        ret['result'] = True
        ret['changes'] = None
        ret['comment'] = '{0} is already monitored'.format(name)

        # if prod_state is set, ensure it matches with the current state
        if prod_state:
            if device['productionState'] != prod_state:
                __salt__['zenoss.set_prod_state'](prod_state, name)
                ret['changes'] = {'old': 'prodState == {0}'.format(device['productionState']), 'new':'prodState == {0}'.format(prod_state)}
                ret['comment'] = '{0} is already monitored but prodState was incorrect, setting to Production'.format(name)

        return ret

    if __opts__['test']:
        ret['comment'] = 'The state of "{0}" will be changed.'.format(name)
        ret['changes'] = {'old': 'monitored == False', 'new': 'monitored == True'}
        ret['result'] = None
        return ret

    # Device not yet in Zenoss. Add and check result
    if __salt__['zenoss.add_device'](name, device_class, collector, prod_state):
        ret['result'] = True
        ret['changes'] = {'old': 'monitored == False', 'new': 'monitored == True'}
        ret['comment'] = '{0} has been added to Zenoss'.format(name)
    else:
        ret['result'] = False
        ret['changes'] = None
        ret['comment'] = 'Unable to add {0} to Zenoss'.format(name)
    return ret
