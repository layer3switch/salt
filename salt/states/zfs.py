# -*- coding: utf-8 -*-
'''
Management zfs datasets

:maintainer:    Jorge Schrauwen <sjorge@blackdot.be>
:maturity:      new
:depends:       zfs
:platform:      smartos, illumos, solaris, freebsd, linux

.. versionadded:: Boron

.. code-block:: yaml

    TODO: add example here
    TODO: add note here about 'properties' needing a manual resut or inherith

'''
from __future__ import absolute_import

# Import Python libs
import logging

# Import Salt libs
from salt.utils.odict import OrderedDict

log = logging.getLogger(__name__)

# Define the state's virtual name
__virtualname__ = 'zfs'


def __virtual__():
    '''
    Provides zfs state
    '''
    if 'zfs.create' in __salt__:
        return True
    else:
        return (
            False,
            '{0} state module can only be loaded on illumos, Solaris, SmartOS, FreeBSD, ...'.format(
                __virtualname__
            )
        )


def _absent(name, dataset_type, force=False, recursive=False):
    '''
    internal shared function for *_absent

    name : string
        name of dataset
    dataset_type : string [filesystem, volume, snapshot, or bookmark]
        type of dataset to remove
    force : boolean
        try harder to destroy the dataset
    recursive : boolean
        also destroy all the child datasets

    '''
    name = name.lower()
    dataset_type = dataset_type.lower()
    ret = {'name': name,
           'changes': {},
           'result': True,
           'comment': ''}

    log.debug('zfs.{0}_absent::{1}::config::force = {2}'.format(dataset_type, name, force))
    log.debug('zfs.{0}_absent::{1}::config::recursive = {2}'.format(dataset_type, name, recursive))

    # check name and type
    if dataset_type not in ['filesystem', 'volume', 'snapshot', 'bookmark']:
        ret['result'] = False
        ret['comment'] = 'unknown dateset type: {0}'.format(dataset_type)

    if ret['result'] and dataset_type in ['snapshot'] and '@' not in name:
        ret['result'] = False
        ret['comment'] = 'invalid snapshot name: {0}'.format(name)

    if ret['result'] and dataset_type in ['bookmark'] and '#' not in name:
        ret['result'] = False
        ret['comment'] = 'invalid bookmark name: {0}'.format(name)

    if ret['result'] and dataset_type in ['filesystem', 'volume']:
        if '@' in name or '#' in name:
            ret['result'] = False
            ret['comment'] = 'invalid filesystem or volume name: {0}'.format(name)

    # check if dataset exists
    if ret['result']:
        if name in __salt__['zfs.list'](name, **{'type': dataset_type}):  # we need to destroy it
            result = {name: 'destroyed'}
            if not __opts__['test']:
                result = __salt__['zfs.destroy'](name, **{'force': force, 'recursive': recursive})

            ret['result'] = name in result and result[name] == 'destroyed'
            ret['changes'] = result if ret['result'] else {}
            if ret['result']:
                ret['comment'] = '{0} {1} was destroyed'.format(
                    dataset_type,
                    name
                )
            else:
                ret['comment'] = 'failed to destroy {0}'.format(name)
                if name in result:
                    ret['comment'] = result[name]
        else:  # dataset with type and name does not exist! (all good)
            ret['comment'] = '{0} {1} is not present'.format(
                dataset_type,
                name
            )

    return ret


def filesystem_absent(name, force=False, recursive=False):
    '''
    ensure filesystem is absent on the system

    name : string
        name of filesystem
    force : boolean
        try harder to destroy the dataset (zfs destroy -f)
    recursive : boolean
        also destroy all the child datasets (zfs destroy -r)

    ..warning:

        If a volume with ``name`` exists, this state will succeed without
        destroying the volume specified by ``name``. This module is dataset type sensitive.

    '''
    return _absent(name, 'filesystem', force, recursive)


def volume_absent(name, force=False, recursive=False):
    '''
    ensure volume is absent on the system

    name : string
        name of volume
    force : boolean
        try harder to destroy the dataset (zfs destroy -f)
    recursive : boolean
        also destroy all the child datasets (zfs destroy -r)

    ..warning:

        If a volume with ``name`` exists, this state will succeed without
        destroying the volume specified by ``name``. This module is dataset type sensitive.

    '''
    return _absent(name, 'volume', force, recursive)


def snapshot_absent(name, force=False, recursive=False):
    '''
    ensure snapshot is absent on the system

    name : string
        name of snapshot
    force : boolean
        try harder to destroy the dataset (zfs destroy -f)
    recursive : boolean
        also destroy all the child datasets (zfs destroy -r)
    '''
    return _absent(name, 'snapshot', force, recursive)


def bookmark_absent(name, force=False, recursive=False):
    '''
    ensure bookmark is absent on the system

    name : string
        name of snapshot
    force : boolean
        try harder to destroy the dataset (zfs destroy -f)
    recursive : boolean
        also destroy all the child datasets (zfs destroy -r)
    '''
    return _absent(name, 'bookmark', force, recursive)


def filesystem_present(name, create_parent=False, properties=None):
    '''
    ensure filesystem exists and has properties set

    name : string
        name of filesystem
    create_parent : boolean
        creates all the non-existing parent datasets.
        any property specified on the command line using the -o option is ignored.
    properties : dict
        additional zfs properties (-o)

    '''
    name = name.lower()
    ret = {'name': name,
           'changes': {},
           'result': True,
           'comment': ''}

    # check params
    if not properties:
        properties = {}

    for prop in properties.keys():  # salt breaks the on/off/yes/no properties
        if isinstance(properties[prop], bool):
            properties[prop] = 'on' if properties[prop] else 'off'

    if '@' in name or '#' in name:
        ret['result'] = False
        ret['comment'] = 'invalid filesystem or volume name: {0}'.format(name)

    log.debug('zfs.filesystem_present::{0}::config::create_parent = {1}'.format(name, create_parent))
    log.debug('zfs.filesystem_present::{0}::config::properties = {1}'.format(name, properties))

    if ret['result']:
        if name in __salt__['zfs.list'](name, **{'type': 'filesystem'}):  # update properties if needed
            result = __salt__['zfs.get'](name, **{'properties': ','.join(properties.keys()), 'fields': 'value', 'depth': 1})

            for prop in properties.keys():
                if properties[prop] != result[name][prop]['value']:
                    if name not in ret['changes']:
                        ret['changes'][name] = {}
                    ret['changes'][name][prop] = properties[prop]

            if len(ret['changes']) > 0:
                if not __opts__['test']:
                    result = __salt__['zfs.set'](name, **ret['changes'][name])
                    if name not in result:
                        ret['result'] = False
                    else:
                        for prop in result[name].keys():
                            if result[name][prop] != 'set':
                                ret['result'] = False

                if ret['result']:
                    ret['comment'] = 'filesystem {0} was updated'.format(name)
                else:
                    ret['changes'] = {}
                    ret['comment'] = 'filesystem {0} failed to be updated'.format(name)
            else:
                ret['comment'] = 'filesystem {0} is up to date'.format(name)
        else:  # create filesystem
            result = {name: 'created'}
            if not __opts__['test']:
                result = __salt__['zfs.create'](name, **{'create_parent': create_parent, 'properties': properties})

            ret['result'] = name in result and result[name] == 'created'
            if ret['result']:
                ret['changes'][name] = properties if len(properties) > 0 else 'created'
                ret['comment'] = 'filesystem {0} was created'.format(name)
            else:
                ret['comment'] = 'failed to filesystem {0}'.format(name)
                if name in result:
                    ret['comment'] = result[name]
    return ret

# vim: tabstop=4 expandtab shiftwidth=4 softtabstop=4
