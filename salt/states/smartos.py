# -*- coding: utf-8 -*-
'''
Management of SmartOS Standalone Compute Nodes

.. code-block:: yaml

    test.example.org:
      smartos.vm_present:
        - vmconfig:
          - image_uuid: c02a2044-c1bd-11e4-bd8c-dfc1db8b0182
          - brand: joyent
          - alias: test
          - quota: 5
          - max_physical_memory: 512
          - nics:
            -
              - mac: "82:1b:8e:49:e9:12"
              - nic_tag: trunk
              - mtu: 1500
              - ips: [ "dhcp" ]
              - vlan_id: 10
            -
              - mac: "82:1b:8e:49:e9:13"
              - nic_tag: trunk
              - mtu: 1500
              - ips: [ "dhcp" ]
              - vlan_id: 30

    cleanup_images:
      smartos.image_vacuum

    .. note::

        Keep in mind that when removing entries from vmconfig they will not get removed from the vm's current configuration,
         for nics, disk, tags, ... they get removed as via add_*, set_*, update_*, and remove_*. Other properties must be
         manual reset to there default value just like when using vmadm update.

'''
from __future__ import absolute_import

# Import Python libs
import logging
import os

# Import Salt libs
import salt.utils
import salt.utils.files
from salt.utils.odict import OrderedDict

log = logging.getLogger(__name__)

# Define the state's virtual name
__virtualname__ = 'smartos'


def __virtual__():
    '''
    Provides smartos state provided for SmartOS
    '''
    return __virtualname__ if 'vmadm.create' in __salt__ else False


def _load_config():
    '''
    Loads and parses /usbkey/config
    '''
    config = {}

    if os.path.isfile('/usbkey/config'):
        with salt.utils.fopen('/usbkey/config', 'r') as config_file:
            for optval in config_file:
                if optval[0] == '#':
                    continue
                if '=' not in optval:
                    continue
                optval = optval.split('=')
                config[optval[0].lower()] = optval[1].strip()
    log.debug('smartos - read /usbkey/config: {0}'.format(config))
    return config


def _write_config(config):
    '''
    writes /usbkey/config
    '''
    with salt.utils.fopen('/usbkey/config.salt', 'w') as config_file:
        config_file.write("#\n# This file was generated by salt\n#\n")
        for prop in OrderedDict(sorted(config.items())):
            config_file.write("{0}={1}\n".format(prop, config[prop]))

    if os.path.isfile('/usbkey/config.salt'):
        try:
            salt.utils.files.rename('/usbkey/config.salt', '/usbkey/config')
        except IOError:
            return False
        log.debug('smartos - wrote /usbkey/config: {0}'.format(config))
        return True
    else:
        return False


def _parse_state_config(config, default_config):
    '''
    Parse vm_present state config
    '''
    for cfg_item in config if config else []:
        for k in cfg_item:
            if k in default_config:
                if isinstance(cfg_item[k], (bool)):
                    default_config[k] = cfg_item[k]
                else:
                    log.warning('smartos.vm_present - config property {0} must be bool, using default: {1}'.format(k, default_config[k]))
            else:
                log.warning('smartos.vm_present - config property {0} not one of {1}'.format(k, default_config.keys()))

    return default_config


def _parse_vmconfig(config):
    '''
    Parse vm_present vm config
    '''
    vmconfig = None

    if isinstance(config, (list)):
        for prop in config:
            # property
            if len(prop) == 1 and isinstance(prop, (salt.utils.odict.OrderedDict)):
                if not vmconfig:
                    vmconfig = {}
                for k in prop:
                    if isinstance(prop[k], (list)):
                        vmconfig[k] = _parse_vmconfig(prop[k])
                    else:
                        vmconfig[k] = prop[k]
            # instance
            if len(prop) > 1 and isinstance(prop, (list)):
                if not vmconfig:
                    vmconfig = []
                instance = {}
                for dataset in prop:
                    for k in dataset:
                        instance[k] = dataset[k]
                vmconfig.append(instance)
    else:
        log.error('smartos.vm_present - failed to parse vmconfig')

    return vmconfig


def _get_instance_changes(current, state):
    '''
    get modified properties
    '''
    # get keys
    current_keys = set(current.keys())
    state_keys = set(state.keys())

    # compare configs
    changed = salt.utils.compare_dicts(current, state)
    for change in changed.keys():
        if changed[change]['old'] == "":
            del changed[change]
        if changed[change]['new'] == "":
            del changed[change]

    return changed


def config_present(name, value):
    '''
    Ensure configuration property is present in /usbkey/config

    name : string
        name of property
    value : string
        value of property

    '''
    name = name.lower()
    ret = {'name': name,
           'changes': {},
           'result': None,
           'comment': ''}

    # load confiration
    config = _load_config()

    # handle bool and None value
    if isinstance(value, (bool)):
        value = 'true' if value else 'false'
    if not value:
        value = ""

    if name in config:
        if config[name] == value:
            # we're good
            ret['result'] = True
            ret['comment'] = 'property {0} already has value "{1}"'.format(name, value)
        else:
            # update property
            ret['result'] = True
            ret['comment'] = 'updated property {0} with value "{1}"'.format(name, value)
            ret['changes'][name] = value
            config[name] = value
    else:
        # add property
        ret['result'] = True
        ret['comment'] = 'added property {0} with value "{1}"'.format(name, value)
        ret['changes'][name] = value
        config[name] = value

    # apply change if needed
    if not __opts__['test'] and len(ret['changes']) > 0:
        ret['result'] = _write_config(config)

    return ret


def config_absent(name):
    '''
    Ensure configuration property is absent in /usbkey/config

    name : string
        name of property

    '''
    name = name.lower()
    ret = {'name': name,
           'changes': {},
           'result': None,
           'comment': ''}

    # load configuration
    config = _load_config()

    if name in config:
        # delete property
        ret['result'] = True
        ret['comment'] = 'property {0} deleted'.format(name)
        ret['changes'][name] = None
        del config[name]
    else:
        # we're good
        ret['result'] = True
        ret['comment'] = 'property {0} is absent'.format(name)

    # apply change if needed
    if not __opts__['test'] and len(ret['changes']) > 0:
        ret['result'] = _write_config(config)

    return ret


def image_present(name):
    '''
    Ensure image is present on the computenode

    name : string
        uuid of image
    '''
    ret = {'name': name,
           'changes': {},
           'result': None,
           'comment': ''}

    if name in __salt__['imgadm.list']():
        # we're good
        ret['result'] = True
        ret['comment'] = 'image {0} is present'.format(name)
    else:
        # add image
        available_images = __salt__['imgadm.avail']()
        if name in available_images:
            if __opts__['test']:
                ret['result'] = True
            else:
                __salt__['imgadm.import'](name)
                ret['result'] = (name in __salt__['imgadm.list']())
            ret['comment'] = 'image {0} installed'.format(name)
            ret['changes'][name] = available_images[name]
        else:
            ret['result'] = False
            ret['comment'] = 'image {0} does not exists'.format(name)

    return ret


def image_absent(name):
    '''
    Ensure image is absent on the computenode

    name : string
        uuid of image

    .. note::

        computenode.image_absent will only remove the image if
         it is not used by a vm.

    '''
    ret = {'name': name,
           'changes': {},
           'result': None,
           'comment': ''}

    if name not in __salt__['imgadm.list']():
        # we're good
        ret['result'] = True
        ret['comment'] = 'image {0} is absent'.format(name)
    else:
        # check if image in use by vm
        if name in __salt__['vmadm.list'](order='image_uuid'):
            ret['result'] = False
            ret['comment'] = 'image {0} currently in use by a vm'.format(name)
        else:
            # delete image
            if __opts__['test']:
                ret['result'] = True
            else:
                __salt__['imgadm.delete'](name)
                ret['result'] = name not in __salt__['imgadm.list']()
            ret['comment'] = 'image {0} deleted'.format(name)
            ret['changes'][name] = None

    return ret


def image_vacuum(name):
    '''
    Delete images not in use or installed via image_present
    '''
    name = name.lower()
    ret = {'name': name,
           'changes': {},
           'result': None,
           'comment': ''}

    # list of images to keep
    images = []

    # retreive image_present state data for host
    for state in __salt__['state.show_lowstate']():
        # skip if not from this state module
        if state['state'] != __virtualname__:
            continue
        # skip if not image_present
        if state['fun'] not in ['image_present']:
            continue
        # keep images installed via image_present
        if 'name' in state:
            images.append(state['name'])

    # retrieve images in use by vms
    for image_uuid in __salt__['vmadm.list'](order='image_uuid'):
        if image_uuid in images:
            continue
        images.append(image_uuid)

    # purge unused images
    ret['result'] = True
    for image_uuid in __salt__['imgadm.list']():
        if image_uuid in images:
            continue
        if image_uuid in __salt__['imgadm.delete'](image_uuid):
            ret['changes'][image_uuid] = None
        else:
            ret['result'] = False
            ret['comment'] = 'failed to delete images'

    if ret['result'] and len(ret['changes']) == 0:
        ret['comment'] = 'no images deleted'
    elif ret['result'] and len(ret['changes']) > 0:
        ret['comment'] = 'images deleted'

    return ret


def vm_present(name, vmconfig, config=None):
    '''
    Ensure vm is present on the computenode

    name : string
        hostname of vm
    vmconfig : dict
        options to set for the vm
    config : dict
        fine grain control over vm_present

    .. note::

        The following configuration properties can be toggled in the config parameter.
          - kvm_reboot (true) - reboots of kvm zones if needed for a config update
          - auto_import (false) - automatic importing of missing images
          - reprovision (false) - reprovision on image_uuid changes

    .. note::

        State ID is used as hostname. Hostnames should be unique.

    .. note::

        If hostname is provided in vmconfig, this hostname will be used and not the state id.
        This allows multiple states to be applied to the same vm.

    .. note::

        Instances for the follow properties should have unique ids.
          - nic : mac
          - disk : path

    '''
    name = name.lower()
    ret = {'name': name,
           'changes': {},
           'result': None,
           'comment': ''}

    # parse config
    config = _parse_state_config(
        config,
        {
            'kvm_reboot': True,
            'auto_import': False,
            'reprovision': False
        }
    )
    log.debug('smartos.vm_present - config for {0} is {1}'.format(name, config))

    # map special vmconfig parameters
    #  collections have set/remove handlers
    #  instances have add/update/remove handlers and a unique id
    vmconfig_type = {
        'collection': [
            'tags',
            'customer_metadata',
            'internal_metadata',
            'routes'
        ],
        'instance': {
            'nics': 'mac',
            'disk': 'path'
        },
        'create_only': [
            'filesystems'
        ]
    }

    # parse vmconfig
    vmconfig = _parse_vmconfig(vmconfig)
    log.debug('smartos.vm_present - vmconfig: {0}'.format(vmconfig))

    # set hostname if needed
    if 'hostname' not in vmconfig:
        vmconfig['hostname'] = name

    # ensure instances have ids
    for instance_type in vmconfig_type['instance']:
        # skip if instance type not in vmconfig
        if instance_type not in vmconfig:
            continue
        # ensure we have unique id
        for instance in vmconfig[instance_type]:
            # skip if we have the id
            if vmconfig_type['instance'][instance_type] in instance:
                continue
            ret['result'] = False
            ret['comment'] = 'one or more {0} is missing unique id {1}'.format(
                instance_type,
                vmconfig_type['instance'][instance_type]
            )
            return ret

    # check if vm exists
    if vmconfig['hostname'] in __salt__['vmadm.list'](order='hostname'):
        # update vm
        ret['result'] = True

        # expand vmconfig
        vmconfig = {
            'state': vmconfig,
            'current': __salt__['vmadm.get'](vmconfig['hostname'], key='hostname'),
            'changed': {},
            'reprovision_uuid': None
        }

        # prepare reprovision
        if 'image_uuid' in vmconfig['state']:
            vmconfig['reprovision_uuid'] = vmconfig['state']['image_uuid']
            vmconfig['state']['image_uuid'] = vmconfig['current']['image_uuid']

        # process properties
        for prop in vmconfig['state']:
            # skip special vmconfig_types
            if prop in vmconfig_type['instance'] or \
                prop in vmconfig_type['collection'] or \
                prop in vmconfig_type['create_only']:
                continue

            # skip unchanged properties
            if prop in vmconfig['current'] and \
                vmconfig['current'][prop] == vmconfig['state'][prop]:
                continue

            # add property to changeset
            vmconfig['changed'][prop] = vmconfig['state'][prop]

        # process collections
        for collection in vmconfig_type['collection']:
            # skip if not present
            if collection not in vmconfig['state']:
                continue

            # process add and update for collection
            for prop in vmconfig['state'][collection]:
                # skip unchanged properties
                if prop in vmconfig['current'][collection] and \
                    vmconfig['current'][collection][prop] == vmconfig['state'][collection][prop]:
                    continue

                # create set_ dict
                if 'set_{0}'.format(collection) not in vmconfig['changed']:
                    vmconfig['changed']['set_{0}'.format(collection)] = {}

                # add property to changeset
                vmconfig['changed']['set_{0}'.format(collection)][prop] = vmconfig['state'][collection][prop]

            # process remove for collection
            for prop in vmconfig['current'][collection]:
                # skip if exists in state
                if prop in vmconfig['state'][collection]:
                    continue

                # create remove_ array
                if 'remove_{0}'.format(collection) not in vmconfig['changed']:
                    vmconfig['changed']['remove_{0}'.format(collection)] = []

                # remove property
                vmconfig['changed']['remove_{0}'.format(collection)].append(prop)

        # process instances
        for instance in vmconfig_type['instance']:
            # skip if not present
            if instance not in vmconfig['state']:
                continue

            # add or update instances
            for state_cfg in vmconfig['state'][instance]:
                add_instance = True

                # find instance with matching ids
                for current_cfg in vmconfig['current'][instance]:
                    if state_cfg[vmconfig_type['instance'][instance]] == current_cfg[vmconfig_type['instance'][instance]]:
                        # ids have matched, disable add instance
                        add_instance = False

                        # skip if value is unchanged
                        changed = _get_instance_changes(current_cfg, state_cfg)
                        if len(changed) == 0:
                            continue

                        # create update_ array
                        if 'remove_{0}'.format(instance) not in vmconfig['changed']:
                            vmconfig['changed']['update_{0}'.format(instance)] = []

                        # generate update
                        update_cfg = {}
                        update_cfg[vmconfig_type['instance'][instance]] = state_cfg[vmconfig_type['instance'][instance]]
                        for prop in changed:
                            update_cfg[prop] = state_cfg[prop]

                        # update instance
                        vmconfig['changed']['update_{0}'.format(instance)].append(update_cfg)

                if add_instance:
                    # create add_ array
                    if 'add_{0}'.format(instance) not in vmconfig['changed']:
                        vmconfig['changed']['add_{0}'.format(instance)] = []

                    # add instance
                    vmconfig['changed']['add_{0}'.format(instance)].append(state_cfg)

            # skip remove instances if none in current
            if prop not in vmconfig['current']:
                continue

            # remove instances
            for current_cfg in vmconfig['current'][instance]:
                remove_instance = True

                # find instance with matching ids
                for state_cfg in vmconfig['state'][instance]:
                    if state_cfg[vmconfig_type['instance'][instance]] == current_cfg[vmconfig_type['instance'][instance]]:
                        # keep instance if matched
                        remove_instance = False

                if remove_instance:
                    # create remove_ array
                    if 'remove_{0}'.format(instance) not in vmconfig['changed']:
                        vmconfig['changed']['remove_{0}'.format(instance)] = []

                    # remove instance
                    vmconfig['changed']['remove_{0}'.format(instance)].append(
                        current_cfg[vmconfig_type['instance'][instance]]
                    )

        # update vm if we have pending changes
        if not __opts__['test'] and len(vmconfig['changed']) > 0:
            if __salt__['vmadm.update'](vm=vmconfig['state']['hostname'], key='hostname', **vmconfig['changed']):
                ret['changes'][vmconfig['state']['hostname']] = vmconfig['changed']
            else:
                ret['result'] = False

        if ret['result']:
            if len(ret['changes']) > 0:
                ret['comment'] = 'vm {0} updated'.format(vmconfig['state']['hostname'])
                if config['kvm_reboot'] and vmconfig['current']['brand'] == 'kvm' and not __opts__['test']:
                    __salt__['vmadm.reboot'](vm=vmconfig['state']['hostname'], key='hostname')
            else:
                ret['comment'] = 'vm {0} is up to date'.format(vmconfig['state']['hostname'])

            if vmconfig['reprovision_uuid'] != vmconfig['current']['image_uuid']:
                if config['reprovision']:
                    # check required image installed
                    if vmconfig['reprovision_uuid'] not in __salt__['imgadm.list']():
                        if config['auto_import']:
                            # check if image is available
                            available_images = __salt__['imgadm.avail']()
                            if vmconfig['reprovision_uuid'] in available_images and not __opts__['test']:
                                # import image
                                __salt__['imgadm.import'](vmconfig['reprovision_uuid'])

                    # reprovision
                    rret = __salt__['vmadm.reprovision'](
                        vm=vmconfig['state']['hostname'],
                        key='hostname',
                        image=vmconfig['reprovision_uuid']
                    )
                    if not isinstance(rret, (bool)) and 'Error' in rret:
                        ret['result'] = False
                        if vmconfig['reprovision_uuid'] not in __salt__['imgadm.list']():
                            ret['comment'] = 'vm {0} updated, reprovision failed because images {1} not installed'.format(
                                vmconfig['state']['hostname'],
                                vmconfig['reprovision_uuid']
                            )
                        else:
                            ret['comment'] = 'vm {0} updated, reprovision failed'.format(
                                vmconfig['state']['hostname']
                            )
                    else:
                        ret['comment'] = 'vm {0} updated and reprovisioned'.format(vmconfig['state']['hostname'])
                        if vmconfig['state']['hostname'] not in ret['changes']:
                            ret['changes'][vmconfig['state']['hostname']] = {}
                        ret['changes'][vmconfig['state']['hostname']]['image_uuid'] = vmconfig['reprovision_uuid']
                else:
                    log.warning('smartos.vm_present - image_uuid in state does not match current, reprovision not allowed')
        else:
            ret['comment'] = 'vm {0} failed to be updated'.format(vmconfig['state']['hostname'])
    else:
        # check required image installed
        ret['result'] = True
        if 'image_uuid' in vmconfig and vmconfig['image_uuid'] not in __salt__['imgadm.list']():
            if config['auto_import']:
                # check if image is available
                available_images = __salt__['imgadm.avail']()
                if vmconfig['image_uuid'] not in available_images:
                    ret['result'] = False
                    ret['comment'] = 'image {0} not available'.format(vmconfig['image_uuid'])
                elif not __opts__['test']:
                    if vmconfig['image_uuid'] not in __salt__['imgadm.import'](vmconfig['image_uuid']):
                        ret['result'] = False
                        ret['comment'] = 'failed to import image {0}'.format(vmconfig['image_uuid'])
            else:
                ret['result'] = False
                ret['comment'] = 'image {0} not installed'.format(vmconfig['image_uuid'])

        # create vm
        if ret['result']:
            uuid = __salt__['vmadm.create'](**vmconfig) if not __opts__['test'] else None
            if not isinstance(uuid, (bool)) and 'Error' in uuid:
                ret['result'] = False
                ret['comment'] = "{0}".format(uuid['Error'])
            else:
                ret['result'] = True
                ret['changes'][vmconfig['hostname']] = vmconfig
                ret['comment'] = 'vm {0} created'.format(vmconfig['hostname'])

    return ret


def vm_absent(name, archive=False):
    '''
    Ensure vm is absent on the computenode

    name : string
        hostname of vm
    archive : boolean
        toggle archiving of vm on removal

    .. note::

        State ID is used as hostname. Hostnames should be unique.

    '''
    name = name.lower()
    ret = {'name': name,
           'changes': {},
           'result': None,
           'comment': ''}

    if name not in __salt__['vmadm.list'](order='hostname'):
        # we're good
        ret['result'] = True
        ret['comment'] = 'vm {0} is absent'.format(name)
    else:
        # delete vm
        if not __opts__['test']:
            # set archive to true if needed
            if archive:
                __salt__['vmadm.update'](vm=name, key='hostname', archive_on_delete=True)

            ret['result'] = __salt__['vmadm.delete'](name, key='hostname')
        else:
            ret['result'] = True

        if not isinstance(ret['result'], (bool)) and 'Error' in ret['result']:
            ret['result'] = False
            ret['comment'] = 'failed to delete vm {0}'.format(name)
        else:
            ret['comment'] = 'vm {0} deleted'.format(name)
            ret['changes'][name] = None

    return ret


def vm_running(name):
    '''
    Ensure vm is in the running state on the computenode

    name : string
        hostname of vm

    .. note::

        State ID is used as hostname. Hostnames should be unique.

    '''
    name = name.lower()
    ret = {'name': name,
           'changes': {},
           'result': None,
           'comment': ''}

    if name in __salt__['vmadm.list'](order='hostname', search='state=running'):
        # we're good
        ret['result'] = True
        ret['comment'] = 'vm {0} already running'.format(name)
    else:
        # start the vm
        ret['result'] = True if __opts__['test'] else __salt__['vmadm.start'](name, key='hostname')
        if not isinstance(ret['result'], (bool)) and 'Error' in ret['result']:
            ret['result'] = False
            ret['comment'] = 'failed to start {0}'.format(name)
        else:
            ret['changes'][name] = 'running'
            ret['comment'] = 'vm {0} started'.format(name)

    return ret


def vm_stopped(name):
    '''
    Ensure vm is in the stopped state on the computenode

    name : string
        hostname of vm

    .. note::

        State ID is used as hostname. Hostnames should be unique.

    '''
    name = name.lower()
    ret = {'name': name,
           'changes': {},
           'result': None,
           'comment': ''}

    if name in __salt__['vmadm.list'](order='hostname', search='state=stopped'):
        # we're good
        ret['result'] = True
        ret['comment'] = 'vm {0} already stopped'.format(name)
    else:
        # stop the vm
        ret['result'] = True if __opts__['test'] else __salt__['vmadm.stop'](name, key='hostname')
        if not isinstance(ret['result'], (bool)) and 'Error' in ret['result']:
            ret['result'] = False
            ret['comment'] = 'failed to stop {0}'.format(name)
        else:
            ret['changes'][name] = 'stopped'
            ret['comment'] = 'vm {0} stopped'.format(name)

    return ret

# vim: tabstop=4 expandtab shiftwidth=4 softtabstop=4
