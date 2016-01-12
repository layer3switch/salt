# -*- coding: utf-8 -*-
'''
Management zfs datasets

:maintainer:    Jorge Schrauwen <sjorge@blackdot.be>
:maturity:      new
:depends:       zfs
:platform:      smartos, illumos, solaris, freebsd, linux

.. versionadded:: Boron

.. code-block:: yaml

    test/shares/yuki:
      zfs.filesystem_present:
        - create_parent: true
        - properties:
            quota: 16G

    test/iscsi/haruhi:
      zfs.volume_present:
        - create_parent: true
        - volume_size: 16M
        - sparse: true
        - properties:
            readonly: on

    test/shares/yuki@frozen:
      zfs.snapshot_present

    moka_origin:
      zfs.hold_present
        - snapshot: test/shares/yuki@frozen

    test/shares/moka:
      zfs.filesystem_present:
        - cloned_from: test/shares/yuki@frozen

    test/shares/moka@tsukune:
      zfs.snapshot_absent

'''
from __future__ import absolute_import

# Import Python libs
import logging

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
        dataset = name if '#' not in name else None  # work around bookmark oddities
        if name in __salt__['zfs.list'](dataset, **{'type': dataset_type}):  # we need to destroy it
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

        If a filesystem with ``name`` exists, this state will succeed without
        destroying the filesystem specified by ``name``. This module is dataset type sensitive.

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


def hold_absent(name, snapshot, recursive=False):
    '''
    ensure hold is absent on the system

    name : string
        name of holdt
    snapshot : string
        name of snapshot
    recursive : boolean
        recursively releases a hold with the given tag on the snapshots of all descendent file systems.
    '''
    name = name.lower()
    ret = {'name': name,
           'changes': {},
           'result': True,
           'comment': ''}

    log.debug('zfs.hold_absent::{0}::config::snapshot = {1}'.format(name, snapshot))
    log.debug('zfs.hold_absent::{0}::config::recursive = {1}'.format(name, recursive))

    # check name and type
    if '@' not in snapshot:
        ret['result'] = False
        ret['comment'] = 'invalid snapshot name: {0}'.format(snapshot)

    if '@' in name or '#' in name:
        ret['result'] = False
        ret['comment'] = 'invalid tag name: {0}'.format(name)

    if ret['result']:
        result = __salt__['zfs.holds'](snapshot)
        if snapshot not in result:
            ret['result'] = False
            ret['comment'] = '{0} is probably not a snapshot'.format(snapshot)
        else:
            if snapshot in result[snapshot]:
                ret['result'] = False
                ret['comment'] = result[snapshot]
            elif result[snapshot] == 'no holds' or name not in result[snapshot]:
                ret['comment'] = 'hold {0} not present'.format(name)
            else:
                result = {snapshot: {name: 'released'}}
                if not __opts__['test']:
                    result = __salt__['zfs.release'](name, snapshot, **{'recursive': recursive})

                ret['result'] = snapshot in result and name in result[snapshot]
                if ret['result']:
                    ret['changes'] = result[snapshot]
                    ret['comment'] = 'hold {0} released'.format(name)
                else:
                    ret['comment'] = 'failed to release {0}'.format(name)
                    if snapshot in result:
                        ret['comment'] = result[snapshot]

    return ret


def hold_present(name, snapshot, recursive=False):
    '''
    ensure hold is present on the system

    name : string
        name of holdt
    snapshot : string
        name of snapshot
    recursive : boolean
        recursively add hold with the given tag on the snapshots of all descendent file systems.
    '''
    name = name.lower()
    ret = {'name': name,
           'changes': {},
           'result': True,
           'comment': ''}

    log.debug('zfs.hold_present::{0}::config::snapshot = {1}'.format(name, snapshot))
    log.debug('zfs.hold_present::{0}::config::recursive = {1}'.format(name, recursive))

    # check name and type
    if '@' not in snapshot:
        ret['result'] = False
        ret['comment'] = 'invalid snapshot name: {0}'.format(snapshot)

    if '@' in name or '#' in name:
        ret['result'] = False
        ret['comment'] = 'invalid tag name: {0}'.format(name)

    if ret['result']:
        result = __salt__['zfs.holds'](snapshot)
        if snapshot not in result:
            ret['result'] = False
            ret['comment'] = '{0} is probably not a snapshot'.format(snapshot)
        else:
            if snapshot in result[snapshot]:
                ret['result'] = False
                ret['comment'] = result[snapshot]
            elif result[snapshot] == 'no holds' or name not in result[snapshot]:  # add hold
                result = {snapshot: {name: 'held'}}
                if not __opts__['test']:
                    result = __salt__['zfs.hold'](name, snapshot, **{'recursive': recursive})

                log.warning(result)
                ret['result'] = snapshot in result and name in result[snapshot]
                if ret['result']:
                    ret['changes'] = result[snapshot]
                    ret['comment'] = 'hold {0} added to {1}'.format(name, snapshot)
                else:
                    ret['comment'] = 'failed to add hold {0}'.format(name)
                    if snapshot in result:
                        ret['comment'] = result[snapshot]
            else:  # hold present
                ret['comment'] = 'hold already exists'

    return ret


def filesystem_present(name, create_parent=False, properties=None, cloned_from=None):
    '''
    ensure filesystem exists and has properties set

    name : string
        name of filesystem
    create_parent : boolean
        creates all the non-existing parent datasets.
        any property specified on the command line using the -o option is ignored.
    cloned_from : string
        name of snapshot to clone
    properties : dict
        additional zfs properties (-o)

    ..note::

        ``cloned_from`` is only use if the filesystem does not exist yet,
        when ``cloned_from`` is set after the filesystem exists it will be ignored.

    ..note::

        properties do not get cloned, if you specify the properties in the state file
        they will be applied on a subsequent run.

    '''
    name = name.lower()
    ret = {'name': name,
           'changes': {},
           'result': True,
           'comment': ''}

    # check params
    if not properties:
        properties = {}

    log.debug('zfs.filesystem_present::{0}::config::create_parent = {1}'.format(name, create_parent))
    log.debug('zfs.filesystem_present::{0}::config::cloned_from = {1}'.format(name, cloned_from))
    log.debug('zfs.filesystem_present::{0}::config::properties = {1}'.format(name, properties))

    for prop in properties.keys():  # salt breaks the on/off/yes/no properties
        if isinstance(properties[prop], bool):
            properties[prop] = 'on' if properties[prop] else 'off'

    if '@' in name or '#' in name:
        ret['result'] = False
        ret['comment'] = 'invalid filesystem or volume name: {0}'.format(name)

    if cloned_from:
        cloned_parent = cloned_from[:cloned_from.index('@')]
        if '@' not in cloned_from:
            ret['result'] = False
            ret['comment'] = '{0} is not a snapshot'.format(cloned_from)
        elif cloned_from not in __salt__['zfs.list'](cloned_from, **{'type': 'snapshot'}):
            ret['result'] = False
            ret['comment'] = 'snapshot {0} does not exist'.format(cloned_from)
        elif cloned_parent not in __salt__['zfs.list'](cloned_parent, **{'type': 'filesystem'}):
            ret['result'] = False
            ret['comment'] = 'snapshot {0} is not from a filesystem'.format(cloned_from)

    if ret['result']:
        if name in __salt__['zfs.list'](name, **{'type': 'filesystem'}):  # update properties if needed
            result = {}
            if len(properties) > 0:
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
                if not cloned_from:
                    result = __salt__['zfs.create'](name, **{'create_parent': create_parent, 'properties': properties})
                else:
                    result = __salt__['zfs.clone'](cloned_from, name, **{'create_parent': create_parent, 'properties': properties})

            ret['result'] = name in result
            if ret['result']:
                ret['result'] = result[name] == 'created' or result[name].startswith('cloned')
            if ret['result']:
                ret['changes'][name] = properties if len(properties) > 0 else result[name]
                ret['comment'] = 'filesystem {0} was created'.format(name)
            else:
                ret['comment'] = 'failed to create filesystem {0}'.format(name)
                if name in result:
                    ret['comment'] = result[name]
    return ret


def volume_present(name, volume_size, sparse=False, create_parent=False, properties=None, cloned_from=None):
    '''
    ensure volume exists and has properties set

    name : string
        name of volume
    volume_size : string
        size of volume
    sparse : boolean
        create sparse volume
    create_parent : boolean
        creates all the non-existing parent datasets.
        any property specified on the command line using the -o option is ignored.
    cloned_from : string
        name of snapshot to clone
    properties : dict
        additional zfs properties (-o)

    ..note::

        ``cloned_from`` is only use if the volume does not exist yet,
        when ``cloned_from`` is set after the volume exists it will be ignored.

    ..note::

        properties do not get cloned, if you specify the properties in the state file
        they will be applied on a subsequent run.

        volume_size is considered a property so it the volume's size will be corrected
        when the properties get update if it differs from the original volume.

        the sparse parameter is ignored when using cloned_from.

    '''
    name = name.lower()
    ret = {'name': name,
           'changes': {},
           'result': True,
           'comment': ''}

    # check params
    if not properties:
        properties = {}

    log.debug('zfs.volume_present::{0}::config::volume_size = {1}'.format(name, volume_size))
    log.debug('zfs.volume_present::{0}::config::sparse = {1}'.format(name, sparse))
    log.debug('zfs.volume_present::{0}::config::create_parent = {1}'.format(name, create_parent))
    log.debug('zfs.volume_present::{0}::config::cloned_from = {1}'.format(name, cloned_from))
    log.debug('zfs.volume_present::{0}::config::properties = {1}'.format(name, properties))

    for prop in properties.keys():  # salt breaks the on/off/yes/no properties
        if isinstance(properties[prop], bool):
            properties[prop] = 'on' if properties[prop] else 'off'

    if '@' in name or '#' in name:
        ret['result'] = False
        ret['comment'] = 'invalid filesystem or volume name: {0}'.format(name)

    if cloned_from:
        cloned_parent = cloned_from[:cloned_from.index('@')]
        if '@' not in cloned_from:
            ret['result'] = False
            ret['comment'] = '{0} is not a snapshot'.format(cloned_from)
        elif cloned_from not in __salt__['zfs.list'](cloned_from, **{'type': 'snapshot'}):
            ret['result'] = False
            ret['comment'] = 'snapshot {0} does not exist'.format(cloned_from)
        elif cloned_parent not in __salt__['zfs.list'](cloned_parent, **{'type': 'volume'}):
            ret['result'] = False
            ret['comment'] = 'snapshot {0} is not from a volume'.format(cloned_from)

    if ret['result']:
        if name in __salt__['zfs.list'](name, **{'type': 'volume'}):  # update properties if needed
            properties['volsize'] = volume_size  # add volume_size to properties
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
                    ret['comment'] = 'volume {0} was updated'.format(name)
                else:
                    ret['changes'] = {}
                    ret['comment'] = 'volume {0} failed to be updated'.format(name)
            else:
                ret['comment'] = 'volume {0} is up to date'.format(name)
        else:  # create volume
            result = {name: 'created'}
            if not __opts__['test']:
                if not cloned_from:
                    result = __salt__['zfs.create'](name, **{
                        'volume_size': volume_size,
                        'sparse': sparse,
                        'create_parent': create_parent,
                        'properties': properties
                    })
                else:
                    result = __salt__['zfs.clone'](cloned_from, name, **{'create_parent': create_parent, 'properties': properties})

            ret['result'] = name in result
            if ret['result']:
                ret['result'] = result[name] == 'created' or result[name].startswith('cloned')
            if ret['result']:
                ret['changes'][name] = properties if len(properties) > 0 else result[name]
                ret['comment'] = 'volume {0} was created'.format(name)
            else:
                ret['comment'] = 'failed to create volume {0}'.format(name)
                if name in result:
                    ret['comment'] = result[name]
    return ret


def bookmark_present(name, snapshot):
    '''
    ensure bookmark exists

    name : string
        name of bookmark
    snapshot : string
        name of snapshot

    '''
    name = name.lower()
    ret = {'name': name,
           'changes': {},
           'result': True,
           'comment': ''}

    log.debug('zfs.bookmark_present::{0}::config::snapshot = {1}'.format(name, snapshot))

    if '@' not in snapshot:
        ret['result'] = False
        ret['comment'] = '{0} is not a snapshot'.format(snapshot)

    if '#' not in name:
        if '/' not in name:
            name = '{0}#{1}'.format(snapshot[:snapshot.index('@')], name)
        else:
            ret['result'] = False
            ret['comment'] = '{0} is not a bookmark'.format(name)

    if ret['result']:
        if name in __salt__['zfs.list'](**{'type': 'bookmark'}):
            ret['comment'] = 'bookmark already exists'
        else:  # create bookmark
            result = {snapshot: 'bookmarked'}
            if not __opts__['test']:
                result = __salt__['zfs.bookmark'](snapshot, name)

            ret['result'] = snapshot in result and result[snapshot].startswith('bookmarked')
            if ret['result']:
                ret['changes'] = result
                ret['comment'] = 'snapshot {0} was bookmarked as {1}'.format(snapshot, name)
            else:
                ret['comment'] = 'failed to create bookmark {0}'.format(name)
    return ret


def snapshot_present(name, recursive=False, properties=None):
    '''
    ensure snapshot exists and has properties set

    name : string
        name of snapshot
    recursive : boolean
        recursively create snapshots of all descendent datasets
    properties : dict
        additional zfs properties (-o)

    ..note:

        properties are only set at creation time.

    '''
    name = name.lower()
    ret = {'name': name,
           'changes': {},
           'result': True,
           'comment': ''}

    # check params
    if not properties:
        properties = {}

    log.debug('zfs.snapshot_present::{0}::config::recursive = {1}'.format(name, recursive))
    log.debug('zfs.snapshot_present::{0}::config::properties = {1}'.format(name, properties))

    for prop in properties.keys():  # salt breaks the on/off/yes/no properties
        if isinstance(properties[prop], bool):
            properties[prop] = 'on' if properties[prop] else 'off'

    if '@' not in name:
        ret['result'] = False
        ret['comment'] = 'invalid snapshot name: {0}'.format(name)

    if ret['result']:
        if name in __salt__['zfs.list'](name, **{'type': 'snapshot'}):  # we are all good
            ret['comment'] = 'snapshot already exists'
        else:  # create snapshot
            result = {name: 'snapshotted'}
            if not __opts__['test']:
                result = __salt__['zfs.snapshot'](name, **{'recursive': recursive, 'properties': properties})

            ret['result'] = name in result and result[name] == 'snapshotted'
            if ret['result']:
                ret['changes'][name] = properties if len(properties) > 0 else result[name]
                ret['comment'] = 'snapshot {0} was created'.format(name)
            else:
                ret['comment'] = 'failed to create snapshot {0}'.format(name)
                if name in result:
                    ret['comment'] = result[name]

    return ret


def promoted(name):
    '''
    ensure a dataset is not a clone

    name : string
        name of fileset or volume

    ..warning::

        only one dataset can be the origin,
        if you promote a clone the original will now point to the promoted dataset

    '''
    name = name.lower()
    ret = {'name': name,
           'changes': {},
           'result': True,
           'comment': ''}

    if '@' in name or '#' in name:
        ret['result'] = False
        ret['comment'] = 'invalid filesystem or volume name: {0}'.format(name)

    if ret['result']:
        if name in __salt__['zfs.list'](name):
            origin = '-'
            if not __opts__['test']:
                origin = __salt__['zfs.get'](name, **{'properties': 'origin', 'fields': 'value'})[name]['origin']['value']

            if origin == '-':
                ret['comment'] = '{0} already promoted'.format(name)
            else:
                result = {name: 'promoted'}
                if not __opts__['test']:
                    result = __salt__['zfs.promote'](name)

                ret['result'] = name in result and result[name] == 'promoted'
                ret['changes'] = result if ret['result'] else {}
                if ret['result']:
                    ret['comment'] = '{0} was promoted'.format(name)
                else:
                    ret['comment'] = 'failed to promote {0}'.format(name)
                    if name in result:
                        ret['comment'] = result[name]

        else:  # we don't have the dataset
            ret['result'] = False
            ret['comment'] = 'dataset {0} does not exist'.format(name)

    return ret

# vim: tabstop=4 expandtab shiftwidth=4 softtabstop=4
