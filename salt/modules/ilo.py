# -*- coding: utf-8 -*-
'''
Manage HP ILOM
'''

import xml.etree.cElementTree as ET
import salt.utils
import os

import logging

log = logging.getLogger(__name__)


def __virtual__():
    '''

    '''
    if salt.utils.which('hponcfg'):
        return True

    return False


def __execute_cmd(name, xml):
    '''
    Execute ilom commands
    '''
    ret = {name.replace('_', ' '): {}}
    id = 0

    with salt.utils.fopen('/tmp/{0}.{1}'.format(name, os.getpid()), 'w') as fh:
        fh.write(xml)

    cmd = __salt__['cmd.run_all']('hponcfg -f /tmp/{0}.{1}'.format(name, os.getpid()))

    # Clean up the temp file
    __salt__['file.remove']('/tmp/{0}.{1}'.format(name, os.getpid()))

    if cmd['retcode'] != 0:
        log.warn('hponcfg return an exit code \'{0}\'.'.format(cmd['retcode']))
        return False

    for i in ET.fromstring(''.join(cmd['stdout'].splitlines()[3:-1])):
        # Ensure a key is unique since the ilo return the same key multiple times depending
        # on the action
        if ret[name.replace('_', ' ')].get(i.tag, None):
            ret[name.replace('_', ' ')].update({i.tag + '_' + str(id): i.attrib.get('VALUE', None)})
            id += 1
        else:
            ret[name.replace('_', ' ')].update({i.tag: i.attrib.get('VALUE', None)})

    return ret


def global_settings():
    '''
    Show global settings

    CLI Example:

    .. code-block:: bash

        salt '*' ilo.global_settings
    '''
    _xml = """<!-- Sample file for Get Global command -->
              <RIBCL VERSION="2.0">
                 <LOGIN USER_LOGIN="x" PASSWORD="x">
                   <RIB_INFO MODE="read">
                     <GET_GLOBAL_SETTINGS />
                   </RIB_INFO>
                 </LOGIN>
               </RIBCL>"""

    return __execute_cmd('Global_Settings', _xml)


def all_users():
    '''
    List all users

    CLI Example:

    .. code-block:: bash

        salt '*' ilo.all_users
    '''
    _xml = """<RIBCL VERSION="2.0">
                <LOGIN USER_LOGIN="x" PASSWORD="x">
                    <USER_INFO MODE="read">
                      <GET_ALL_USERS />
                    </USER_INFO>
                </LOGIN>
              </RIBCL>"""

    return __execute_cmd('All_users', _xml)
