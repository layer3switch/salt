# -*- coding: utf-8 -*-
'''
Module for running ZFS zpool command

:codeauthor: Nitin Madhok <nmadhok@clemson.edu>
'''
from __future__ import absolute_import

# Import Python libs
import os
import stat
import logging

# Import Salt libs
import salt.utils
import salt.utils.decorators as decorators
from salt.utils.odict import OrderedDict

log = logging.getLogger(__name__)

__func_alias__ = {
    'import_': 'import',
    'list_': 'list',
}


@decorators.memoize
def _check_zpool():
    '''
    Looks to see if zpool is present on the system
    '''
    return salt.utils.which('zpool')


@decorators.memoize
def _check_features():
    '''
    Looks to see if zpool-features is available
    '''
    # get man location
    man = salt.utils.which('man')
    if not man:
        return False

    cmd = '{man} zpool-features'.format(
        man=man
    )
    res = __salt__['cmd.run_all'](cmd, python_shell=False)
    return res['retcode'] == 0


@decorators.memoize
def _check_mkfile():
    '''
    Looks to see if mkfile is present on the system
    '''
    return salt.utils.which('mkfile')


def __virtual__():
    '''
    Provides zpool.
    '''
    if _check_zpool():
        return 'zpool'
    return (False, "Module zpool: zpool not found")


def healthy():
    '''
    .. versionadded:: Boron
    Check if all zpools are healthy

    CLI Example:

    .. code-block:: bash

        salt '*' zpool.healthy
    '''
    zpool_cmd = _check_zpool()

    cmd = '{zpool_cmd} status -x'.format(
        zpool_cmd=zpool_cmd
    )
    res = __salt__['cmd.run_all'](cmd, python_shell=False)
    return res['stdout'] == 'all pools are healthy'


def status(zpool=None):
    '''
    .. versionchanged:: Boron

    Return the status of the named zpool

    zpool : string
        optional name of zpool to list

    CLI Example:

    .. code-block:: bash

        salt '*' zpool.status myzpool
    '''
    ret = OrderedDict()

    # get zpool list data
    zpool_cmd = _check_zpool()
    cmd = '{zpool_cmd} status{zpool}'.format(
        zpool_cmd=zpool_cmd,
        zpool=' {0}'.format(zpool) if zpool else ''
    )
    res = __salt__['cmd.run_all'](cmd, python_shell=False)
    if res['retcode'] != 0:
        ret['Error'] = res['stderr'] if 'stderr' in res else res['stdout']
        return ret

    # parse zpool status data
    zp_data = {}
    current_pool = None
    current_prop = None
    for zpd in res['stdout'].splitlines():
        if zpd.strip() == '':
            continue
        if ':' in zpd:
            prop = zpd.split(':')[0].strip()
            value = zpd.split(':')[1].strip()
            if prop == 'pool' and current_pool != value:
                current_pool = value
                zp_data[current_pool] = {}
            if prop != 'pool':
                zp_data[current_pool][prop] = value

            current_prop = prop
        else:
            zp_data[current_pool][current_prop] = "{0}\n{1}".format(
                zp_data[current_pool][current_prop],
                zpd
            )

    # parse zpool config data
    for pool in zp_data:
        if 'config' not in zp_data[pool]:
            continue
        header = None
        root_vdev = None
        vdev = None
        dev = None
        config = zp_data[pool]['config']
        config_data = OrderedDict()
        for line in config.splitlines():
            if not header:
                header = line.strip().lower()
                header = [x for x in header.split(' ') if x not in ['']]
                continue

            if line[0:1] == "\t":
                line = line[1:]

            stat_data = OrderedDict()
            stats = [x for x in line.strip().split(' ') if x not in ['']]
            for prop in header:
                if prop == 'name':
                    continue
                if header.index(prop) < len(stats):
                    stat_data[prop] = stats[header.index(prop)]

            dev = line.strip().split()[0]

            if line[0:4] != '    ':
                if line[0:2] == '  ':
                    vdev = line.strip().split()[0]
                    dev = None
                else:
                    root_vdev = line.strip().split()[0]
                    vdev = None
                    dev = None

            if root_vdev:
                if root_vdev not in config_data:
                    config_data[root_vdev] = {}
                    if len(stat_data) > 0:
                        config_data[root_vdev] = stat_data
                if vdev:
                    if vdev not in config_data[root_vdev]:
                        config_data[root_vdev][vdev] = {}
                        if len(stat_data) > 0:
                            config_data[root_vdev][vdev] = stat_data
                    if dev and dev not in config_data[root_vdev][vdev]:
                        config_data[root_vdev][vdev][dev] = {}
                        if len(stat_data) > 0:
                            config_data[root_vdev][vdev][dev] = stat_data

        zp_data[pool]['config'] = config_data

    return zp_data


def iostat(zpool=None):
    '''
    .. versionchanged:: Boron

    Display I/O statistics for the given pools

    zpool : string
        optional name of zpool to list

    CLI Example:

    .. code-block:: bash

        salt '*' zpool.iostat myzpool
    '''
    ret = OrderedDict()

    # get zpool list data
    zpool_cmd = _check_zpool()
    cmd = '{zpool_cmd} iostat -v{zpool}'.format(
        zpool_cmd=zpool_cmd,
        zpool=' {0}'.format(zpool) if zpool else ''
    )
    res = __salt__['cmd.run_all'](cmd, python_shell=False)
    if res['retcode'] != 0:
        ret['Error'] = res['stderr'] if 'stderr' in res else res['stdout']
        return ret

    # note: hardcoded header fields, the double header is hard to parse
    #                                capacity     operations    bandwidth
    #pool                         alloc   free   read  write   read  write
    header = [
        'pool',
        'capacity-alloc',
        'capacity-free',
        'operations-read',
        'operations-write',
        'bandwith-read',
        'bandwith-write'
    ]
    root_vdev = None
    vdev = None
    dev = None
    config_data = None
    current_pool = None
    for line in res['stdout'].splitlines():
        if line.strip() == '':
            continue

        if line.startswith('-') and line.endswith('-'):
            if config_data:
                ret[current_pool] = config_data
            config_data = OrderedDict()
            current_pool = None
        else:
            if not isinstance(config_data, salt.utils.odict.OrderedDict):
                continue

            stat_data = OrderedDict()
            stats = [x for x in line.strip().split(' ') if x not in ['']]
            for prop in header:
                if header.index(prop) < len(stats):
                    if prop == 'pool':
                        if not current_pool:
                            current_pool = stats[header.index(prop)]
                        continue
                    if stats[header.index(prop)] == '-':
                        continue
                    stat_data[prop] = stats[header.index(prop)]

            dev = line.strip().split()[0]

            if line[0:4] != '    ':
                if line[0:2] == '  ':
                    vdev = line.strip().split()[0]
                    dev = None
                else:
                    root_vdev = line.strip().split()[0]
                    vdev = None
                    dev = None

            if root_vdev:
                if root_vdev not in config_data:
                    config_data[root_vdev] = {}
                    if len(stat_data) > 0:
                        config_data[root_vdev] = stat_data
                if vdev:
                    if vdev not in config_data[root_vdev]:
                        config_data[root_vdev][vdev] = {}
                        if len(stat_data) > 0:
                            config_data[root_vdev][vdev] = stat_data
                    if dev and dev not in config_data[root_vdev][vdev]:
                        config_data[root_vdev][vdev][dev] = {}
                        if len(stat_data) > 0:
                            config_data[root_vdev][vdev][dev] = stat_data

    return ret


def list_(properties='size,alloc,free,cap,frag,health', zpool=None):
    '''
    .. versionadded:: 2015.5.0
    .. versionchanged:: Boron

    Return information about (all) zpools

    zpool : string
        optional name of zpool to list
    properties : string
        comma-separated list of properties to list

    .. note::
        the 'name' property will always be included, the 'frag' property will get removed if not available

    zpool : string
        optional zpool

    .. note::
        multiple zpools can be provded as a space seperated list

    CLI Example:

    .. code-block:: bash

        salt '*' zpool.list
    '''
    ret = OrderedDict()

    # remove 'frag' property if not available
    properties = properties.split(',')
    if 'name' in properties:
        properties.remove('name')
    properties.insert(0, 'name')
    if not _check_features() and 'frag' in properties:
        properties.remove('frag')

    # get zpool list data
    zpool_cmd = _check_zpool()
    cmd = '{zpool_cmd} list -H -o {properties}{zpool}'.format(
        zpool_cmd=zpool_cmd,
        properties=','.join(properties),
        zpool=' {0}'.format(zpool) if zpool else ''
    )
    res = __salt__['cmd.run_all'](cmd, python_shell=False)
    if res['retcode'] != 0:
        ret['Error'] = res['stderr'] if 'stderr' in res else res['stdout']
        return ret

    # parse zpool list data
    for zp in res['stdout'].splitlines():
        zp = zp.split("\t")
        zp_data = {}

        for prop in properties:
            zp_data[prop] = zp[properties.index(prop)]

        ret[zp_data['name']] = zp_data
        del ret[zp_data['name']]['name']

    return ret


def zpool_list():
    '''
    .. deprecated:: 2014.7.0
       Use :py:func:`~salt.modules.zpool.list_` instead.

    Return a list of all pools in the system with health status and space usage

    CLI Example:

    .. code-block:: bash

        salt '*' zpool.zpool_list
    '''
    salt.utils.warn_until(
            'Boron',
            'The \'zpool_list()\' module function is being deprecated and is '
            'being renamed to \'list()\'. This function \'zpool_list()\' will be removed in '
            'Salt Boron.'
        )
    return list_()


def exists(zpool):
    '''
    Check if a ZFS storage pool is active

    zpool : string
        name of zpool

    CLI Example:

    .. code-block:: bash

        salt '*' zpool.exists myzpool
    '''
    zpool_cmd = _check_zpool()
    cmd = '{zpool_cmd} list {zpool}'.format(
        zpool_cmd=zpool_cmd,
        zpool=zpool
    )
    res = __salt__['cmd.run_all'](cmd, python_shell=False)
    if res['retcode'] != 0:
        return False
    return True


def destroy(zpool):
    '''
    .. versionchanged:: Boron

    Destroys a storage pool

    zpool : string
        name of zpool

    CLI Example:

    .. code-block:: bash

        salt '*' zpool.destroy myzpool
    '''
    ret = {}
    if not exists(zpool):
        ret['Error'] = 'Storage pool {0} does not exist'.format(zpool)
        ret['retcode'] = 1
    else:
        zpool_cmd = _check_zpool()
        cmd = '{zpool_cmd} destroy {zpool}'.format(
            zpool_cmd=zpool_cmd,
            zpool=zpool
        )
        res = __salt__['cmd.run_all'](cmd, python_shell=False)
        if not exists(zpool):
            if 'stderr' in res:
                ret['Error'] = res['stderr']
            else:
                ret = False
        else:
            ret = True

    return ret


def scrub(zpool, stop=False):
    '''
    .. versionchanged:: Boron

    Scrub a zpool

    zpool : string
        name of zpool
    stop : boolean
        if true, cancel ongoing scrub

    CLI Example:

    .. code-block:: bash

        salt '*' zpool.scrub myzpool
    '''
    ret = {}
    if exists(zpool):
        zpool_cmd = _check_zpool()
        cmd = '{zpool_cmd} scrub {stop}{zpool}'.format(
            zpool_cmd=zpool_cmd,
            stop='-s ' if stop else '',
            zpool=zpool
        )
        res = __salt__['cmd.run_all'](cmd, python_shell=False)
        if res['retcode'] != 0:
            if 'stderr' in res:
                ret['Error'] = res['stderr']
                ret['retcode'] = res['retcode']
            else:
                ret = False
        else:
            ret = True
    else:
        ret['Error'] = 'Storage pool {0} does not exist'.format(zpool)
        ret['retcode'] = 2

    return ret


def create(zpool, *vdevs, **kwargs):
    '''
    .. versionadded:: 2015.5.0

    Create a simple zpool, a mirrored zpool, a zpool having nested VDEVs, a hybrid zpool with cache, spare and log drives or a zpool with RAIDZ-1, RAIDZ-2 or RAIDZ-3

    zpool : string
        name of zpool
    * : string
        one or move devices

    CLI Example:

    .. code-block:: bash

        salt '*' zpool.create myzpool /path/to/vdev1 [...] [force=True|False]
        salt '*' zpool.create myzpool mirror /path/to/vdev1 /path/to/vdev2 [...] [force=True|False]
        salt '*' zpool.create myzpool raidz1 /path/to/vdev1 /path/to/vdev2 raidz2 /path/to/vdev3 /path/to/vdev4 /path/to/vdev5 [...] [force=True|False]
        salt '*' zpool.create myzpool mirror /path/to/vdev1 [...] mirror /path/to/vdev2 /path/to/vdev3 [...] [force=True|False]
        salt '*' zpool.create myhybridzpool mirror /tmp/file1 [...] log mirror /path/to/vdev1 [...] cache /path/to/vdev2 [...] spare /path/to/vdev3 [...] [force=True|False]

    .. note::

        Zpool properties can be specified at the time of creation of the pool by
        passing an additional argument called "properties" and specifying the properties
        with their respective values in the form of a python dictionary::

            properties="{'property1': 'value1', 'property2': 'value2'}"

        Example:

        .. code-block:: bash

            salt '*' zpool.create myzpool /path/to/vdev1 [...] properties="{'property1': 'value1', 'property2': 'value2'}"
    '''
    ret = {}
    dlist = []

    # Check if the pool_name is already being used
    if exists(zpool):
        ret['Error'] = 'Storage Pool `{0}` already exists'.format(zpool)
        ret['retcode'] = 1
        return ret

    if not vdevs:
        ret['Error'] = 'Missing vdev specification. Please specify vdevs.'
        ret['retcode'] = 2
        return ret

    # make sure files are present on filesystem
    for vdev in vdevs:
        if vdev not in ['mirror', 'log', 'cache', 'raidz1', 'raidz2', 'raidz3', 'spare']:
            if not os.path.exists(vdev):
                # Path doesn't exist so error and return
                ret[vdev] = '{0} not present on filesystem'.format(vdev)
                ret['retcode'] = 3
                return ret
            mode = os.stat(vdev).st_mode
            if not stat.S_ISBLK(mode) and not stat.S_ISREG(mode) and not stat.S_ISCHR(mode):
                # Not a block device, file vdev, or character special device so error and return
                ret[vdev] = '{0} is not a block device, a file vdev, or character special device'.format(vdev)
                ret['retcode'] = 4
                return ret
        dlist.append(vdev)

    devs = ' '.join(dlist)
    zpool_cmd = _check_zpool()
    force = kwargs.get('force', False)
    properties = kwargs.get('properties', None)
    cmd = '{0} create'.format(zpool_cmd)

    if force:
        cmd = '{0} -f'.format(cmd)

    # if zpool properties specified, then
    # create "-o property=value" pairs
    if properties:
        optlist = []
        for prop in properties:
            optlist.append('-o {0}={1}'.format(prop, properties[prop]))
        opts = ' '.join(optlist)
        cmd = '{0} {1}'.format(cmd, opts)
    cmd = '{0} {1} {2}'.format(cmd, zpool, devs)

    # Create storage pool
    res = __salt__['cmd.run'](cmd, python_shell=False)

    # Check and see if the pools is available
    if exists(zpool):
        ret[zpool] = 'created'
        return ret
    else:
        ret['Error'] = {}
        ret['Error']['Messsage'] = 'Unable to create storage pool {0}'.format(zpool)
        ret['Error']['Reason'] = res
        ret['retcode'] = 5

    return ret


def add(zpool, *vdevs, **kwargs):
    '''
    Add the specified vdev\'s to the given pool

    zpool : string
        name of zpool
    * : string
        one or move devices
    force : boolean
        forces use of vdevs

    CLI Example:

    .. code-block:: bash

        salt '*' zpool.add myzpool /path/to/vdev1 /path/to/vdev2 [...]
    '''
    ret = {}
    dlist = []

    # check for pool
    if not exists(zpool):
        ret['Error'] = 'Storage Pool `{0}` doesn\'t exist'.format(zpool)
        ret['retcode'] = 1
        return ret

    if not vdevs:
        ret['Error'] = 'Missing vdev specification. Please specify vdevs.'
        ret['retcode'] = 2
        return ret

    force = kwargs.get('force', False)

    # make sure files are present on filesystem
    for vdev in vdevs:
        if vdev not in ['mirror', 'log', 'cache', 'raidz1', 'raidz2', 'raidz3', 'spare']:
            if not os.path.exists(vdev):
                # Path doesn't exist so error and return
                ret[vdev] = '{0} not present on filesystem'.format(vdev)
                ret['retcode'] = 3
                return ret
            mode = os.stat(vdev).st_mode
            if not stat.S_ISBLK(mode) and not stat.S_ISREG(mode):
                # Not a block device or file vdev so error and return
                ret[vdev] = '{0} is not a block device or a file vdev'.format(vdev)
                ret['retcode'] = 4
                return ret
        dlist.append(vdev)

    devs = ' '.join(dlist)

    # try and add watch out for mismatched replication levels
    zpool_cmd = _check_zpool()
    cmd = '{zpool_cmd} add {force}{zpool} {devs}'.format(
        zpool_cmd=zpool_cmd,
        force='-f ' if force else '',
        zpool=zpool,
        devs=devs
    )
    res = __salt__['cmd.run_all'](cmd, python_shell=False)
    if res['retcode'] != 0:
        ret['Error'] = res['stderr'] if 'stderr' in res else res['stdout']
        ret['retcode'] = res['retcode']
    else:
        ret['Added'] = '{0} to {1}'.format(', '.join(dlist), zpool)

    return ret


def attach(zpool, device, new_device, force=False):
    '''
    Attach specified device to zpool

    zpool : string
        name of zpool
    device : string
        device to attach too
    new_device : string
        device to attach
    force : boolean
        forces use of vdevs

    CLI Example:

    .. code-block:: bash

        salt '*' zpool.add myzpool /path/to/vdev1 /path/to/vdev2 [...]
    '''
    ret = {}
    dlist = []

    # check for pool
    if not exists(zpool):
        ret['Error'] = 'Storage Pool `{0}` doesn\'t exist'.format(zpool)
        ret['retcode'] = 1
        return ret

    # check devices
    if not os.path.exists(device):
        # Path doesn't exist so error and return
        ret[device] = '{0} not present on filesystem'.format(device)
        ret['retcode'] = 3
        return ret
    mode = os.stat(device).st_mode
    if not stat.S_ISBLK(mode) and not stat.S_ISREG(mode):
        # Not a block device or file vdev so error and return
        ret[device] = '{0} is not a block device or a file vdev'.format(device)
        ret['retcode'] = 4
        return ret
    if not os.path.exists(new_device):
        # Path doesn't exist so error and return
        ret[new_device] = '{0} not present on filesystem'.format(new_device)
        ret['retcode'] = 3
        return ret
    mode = os.stat(new_device).st_mode
    if not stat.S_ISBLK(mode) and not stat.S_ISREG(mode):
        # Not a block device or file vdev so error and return
        ret[device] = '{0} is not a block device or a file vdev'.format(new_device)
        ret['retcode'] = 4
        return ret

    # try and add watch out for mismatched replication levels
    zpool_cmd = _check_zpool()
    cmd = '{zpool_cmd} attach {force}{zpool} {device} {new_device}'.format(
        zpool_cmd=zpool_cmd,
        force='-f ' if force else '',
        zpool=zpool,
        device=device,
        new_device=new_device
    )
    res = __salt__['cmd.run_all'](cmd, python_shell=False)
    if res['retcode'] != 0:
        ret['Error'] = res['stderr'] if 'stderr' in res else res['stdout']
        ret['retcode'] = res['retcode']
    else:
        ret['Attached'] = '{0} to {1}'.format(new_device, zpool)

    return ret


def replace(zpool, old_device, new_device=None, force=False):
    '''
    .. versionchanged:: Boron

    Replaces old_device with new_device.

    .. note::
        This is equivalent to attaching new_device,
        waiting for it to resilver, and then detaching old_device.

        The size of new_device must be greater than or equal to the minimum
        size of all the devices in a mirror or raidz configuration.

    zpool : string
        name of zpool
    old_device : string
        old device to be replaced
    new_device : string
        optional new device
    force : boolean
        Forces use of new_device, even if its appears to be in use.

    CLI Example:

    .. code-block:: bash

        salt '*' zpool.replace myzpool /path/to/vdev1 /path/to/vdev2
    '''
    ret = {}
    # Make sure pool is there
    if not exists(zpool):
        ret['Error'] = '{0}: pool does not exists.'.format(zpool)
        ret['retcode'] = 1
        return ret

    # make sure old, new vdevs are on filesystem
    if not os.path.isfile(old_device):
        ret['Error'] = '{0}: is not on the file system.'.format(old_device)
        ret['retcode'] = 2
        return ret
    if new_device and not os.path.isfile(new_device):
        ret['Error'] = '{0}: is not on the file system.'.format(new_device)
        ret['retcode'] = 3
        return ret

    # Replace vdevs
    zpool_cmd = _check_zpool()
    cmd = '{zpool_cmd} replace {force}{zpool} {old_device}{new_device}'.format(
        zpool_cmd=zpool_cmd,
        zpool=zpool,
        force='-f ' if force else '',
        old_device=old_device,
        new_device=' {0}'.format(new_device) if new_device else ''
    )
    res = __salt__['cmd.run_all'](cmd, python_shell=False)
    if res['retcode'] != 0:
        ret['Error'] = res['stderr'] if 'stderr' in res else res['stdout']
        ret['retcode'] = res['retcode']
    else:
        ret = True

    return ret


@salt.utils.decorators.which('mkfile')
def create_file_vdev(size, *vdevs):
    '''
    .. versionchanged:: Boron

    Creates file based ``virtual devices`` for a zpool

    ``*vdevs`` is a list of full paths for mkfile to create

    CLI Example:

    .. code-block:: bash

        salt '*' zpool.create_file_vdev 7g /path/to/vdev1 [/path/to/vdev2] [...]

    .. note::

        Depending on file size, the above command may take a while to return.
    '''
    ret = {}
    dlist = []
    # Get file names to create
    for vdev in vdevs:
        # check if file is present if not add it
        if os.path.isfile(vdev):
            ret[vdev] = 'File: {0} already present'.format(vdev)
        else:
            dlist.append(vdev)

    mkfile = _check_mkfile()
    cmd = [mkfile, '{0}'.format(size)]
    cmd.extend(dlist)
    __salt__['cmd.run'](cmd, python_shell=False)

    # Makesure the files are there
    for vdev in vdevs:
        if not os.path.isfile(vdev):
            ret[vdev] = 'The vdev can\'t be created'
            ret['retcode'] = 1
    ret['status'] = True
    ret['cmd'] = ' '.join(cmd)
    return ret


def export(*pools, **kwargs):
    '''
    .. versionadded:: 2015.5.0

    Export storage pools

    * : string
        one or more zpools to export
    force : boolean
        force export of zpools

    CLI Example:

    .. code-block:: bash

        salt '*' zpool.export myzpool ... [force=True|False]
        salt '*' zpool.export myzpool2 myzpool2 ... [force=True|False]
    '''
    ret = {}
    pool_list = []
    if not pools:
        ret['Error'] = 'zpool name parameter is mandatory'
        ret['retcode'] = 1
        return ret

    for pool in pools:
        if not exists(pool):
            ret['Error'] = 'Storage pool {0} does not exist'.format(pool)
            ret['retcode'] = 2
            return ret
        pool_list.append(pool)

    pools = ' '.join(pool_list)
    zpool = _check_zpool()
    force = kwargs.get('force', False)
    if force is True:
        cmd = '{0} export -f {1}'.format(zpool, pools)
    else:
        cmd = '{0} export {1}'.format(zpool, pools)
    res = __salt__['cmd.run'](cmd, ignore_retcode=True)
    if res:
        ret['Error'] = {}
        ret['Error']['Message'] = 'Import failed!'
        ret['Error']['Reason'] = res
        ret['retcode'] = 3
    else:
        for pool in pool_list:
            ret[pool] = 'Exported'
    return ret


def import_(zpool=None, new_name=None, force=False, raw_options=None):
    '''
    .. versionadded:: 2015.5.0
    .. versionchanged:: Boron

    Import storage pools or list pools available for import

    zpool : string
        optional name of zpool to import
    new_name : string
        optional new name for the zpool
    force : boolean
        force import of zpool(s)
    raw_options : string
        optionally feed in raw options

    .. note::
        dangerous! this allows to pass additional pool properties, mount options,...
        to be flexable there is no validation for this.

    CLI Example:

    .. code-block:: bash

        salt '*' zpool.import [force=True|False]
        salt '*' zpool.import myzpool [mynewzpool] [force=True|False]
    '''
    ret = {}

    zpool_cmd = _check_zpool()
    cmd = '{zpool_cmd} import{force}{zpool}{new_name}{raw_options}'.format(
        zpool_cmd=zpool_cmd,
        force=' -f' if force else '',
        zpool=' {0}'.format(zpool) if zpool else ' -a',
        new_name=' {0}'.format(new_name) if zpool and new_name else '',
        raw_options=' {0}'.format(raw_options) if raw_options else ''
    )
    res = __salt__['cmd.run_all'](cmd, python_shell=False)
    if res['retcode'] != 0 and res['stdout'] != '':
        ret['Error'] = res['stderr'] if 'stderr' in res else res['stdout']
        ret['retcode'] = res['retcode']

    if zpool and 'Error' not in ret:
        ret = exists(zpool if not new_name else new_name)
    else:
        ret = True
    return ret


def online(zpool, *vdevs, **kwargs):
    '''
    .. versionadded:: 2015.5.0

    Ensure that the specified devices are online

    zpool : string
        name of zpool
    * : string
        one or more devices
    expand : boolean
        Expand the device to use all available space.

        .. note::
            If the device is part of a mirror or raidz then all devices must be
            expanded before the new space will become available to the pool.

    CLI Example:

    .. code-block:: bash

        salt '*' zpool.online myzpool /path/to/vdev1 [...]

    '''
    ret = {}
    dlist = []

    # Check if the pool_name exists
    if not exists(zpool):
        ret['Error'] = 'Storage Pool `{0}` doesn\'t exist'.format(zpool)
        ret['retcode'] = 1
        return ret

    if not vdevs:
        ret['Error'] = 'Missing vdev specification. Please specify vdevs.'
        ret['retcode'] = 2
        return ret

    # get expand option
    expand = kwargs.get('expand', False)

    # make sure files are present on filesystem
    for vdev in vdevs:
        if not os.path.exists(vdev):
            # Path doesn't exist so error and return
            ret[vdev] = '{0} not present on filesystem'.format(vdev)
            ret['retcode'] = 3
            return ret
        mode = os.stat(vdev).st_mode
        if not stat.S_ISBLK(mode) and not stat.S_ISREG(mode):
            # Not a block device or file vdev so error and return
            ret[vdev] = '{0} is not a block device or a file vdev'.format(vdev)
            ret['retcode'] = 4
            return ret
        dlist.append(vdev)

    devs = ' '.join(dlist)
    zpool_cmd = _check_zpool()
    cmd = '{zpool_cmd} online {expand}{zpool} {devs}'.format(
        zpool_cmd=zpool_cmd,
        expand='-e ' if expand else '',
        zpool=zpool,
        devs=devs
    )
    # Bring all specified devices online
    res = __salt__['cmd.run_all'](cmd, python_shell=False)
    if res['retcode'] != 0:
        ret['Error'] = res['stderr'] if 'stderr' in res else res['stdout']
        ret['retcode'] = res['retcode']
    else:
        ret[zpool] = 'Specified devices: {0} are online.'.format(', '.join(vdevs))
    return ret


def offline(zpool, *vdevs, **kwargs):
    '''
    .. versionadded:: 2015.5.0
    .. versionchanged:: Boron

    Ensure that the specified devices are offline

    .. warning::

        By default, the OFFLINE state is persistent. The device remains offline when
        the system is rebooted. To temporarily take a device offline, use ``temporary=True``.

    zpool : string
        name of zpool
    * : string
        one or more devices
    temporary : boolean
        enable temporarily offline

    CLI Example:

    .. code-block:: bash

        salt '*' zpool.offline myzpool /path/to/vdev1 [...] [temporary=True|False]
    '''
    ret = {}
    dlist = []

    # Check if the pool_name exists
    if not exists(zpool):
        ret['Error'] = 'Storage Pool `{0}` doesn\'t exist'.format(zpool)
        ret['retcode'] = 1
        return ret

    if not vdevs:
        ret['Error'] = 'Missing vdev specification. Please specify vdevs.'
        ret['retcode'] = 2
        return ret

    # make sure files are present on filesystem
    for vdev in vdevs:
        if not os.path.exists(vdev):
            # Path doesn't exist so error and return
            ret[vdev] = '{0} not present on filesystem'.format(vdev)
            ret['retcode'] = 3
            return ret
        mode = os.stat(vdev).st_mode
        if not stat.S_ISBLK(mode) and not stat.S_ISREG(mode):
            # Not a block device or file vdev so error and return
            ret[vdev] = '{0} is not a block device or a file vdev'.format(vdev)
            ret['retcode'] = 4
            return ret
        dlist.append(vdev)

    devs = ' '.join(dlist)
    zpool_cmd = _check_zpool()
    cmd = '{zpool_cmd} offline {temp}{zpool} {devs}'.format(
        zpool_cmd=zpool_cmd,
        temp='-t ' if kwargs.get('temporary', False) else '',
        zpool=zpool,
        devs=devs
    )
    # Bring all specified devices online
    res = __salt__['cmd.run_all'](cmd, python_shell=False)
    if res['retcode'] != 0:
        ret['Error'] = res['stderr'] if 'stderr' in res else res['stdout']
        ret['retcode'] = res['retcode']
    else:
        ret[zpool] = 'Specified devices: {0} are offline.'.format(', '.join(vdevs))
    return ret

# vim: tabstop=4 expandtab shiftwidth=4 softtabstop=4
