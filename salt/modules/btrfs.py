# -*- coding: utf-8 -*-
#
# The MIT License (MIT)
# Copyright (C) 2014 SUSE LLC
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to
# deal in the Software without restriction, including without limitation the
# rights to use, copy, modify, merge, publish, distribute, sublicense, and/or
# sell copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
# FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS
# IN THE SOFTWARE.

'''
Module for managing BTRFS file systems.
'''

import os
import re
import time
import logging

import salt.utils
from salt.exceptions import CommandExecutionError

import fsutils

log = logging.getLogger(__name__)

def __virtual__():
    '''
    Only work on POSIX-like systems
    '''
    return not salt.utils.is_windows() and __grains__.get('kernel') == 'Linux'


def version():
    '''
    Return BTRFS version.
    '''
    out = __salt__['cmd.run_all']("btrfs --version")
    if out.get('stderr'):
        raise CommandExecutionError(out['stderr'])
    return {'version': out['stdout'].split(" ", 1)[-1]}


def _parse_btrfs_info(data):
    '''
    Parse BTRFS device info data.
    '''
    info = {}
    for line in [line for line in data.split("\n") if line][:-1]:
        if line.startswith("Label:"):
            line = re.sub(r"Label:\s+", "", line)
            label, uuid = [tkn.strip() for tkn in line.split("uuid:")]
            info['label'] = label != 'none' and label or None
            info['uuid'] = uuid
            continue

        if line.startswith("\tdevid"):
            dev_data = re.split(r"\s+", line.strip())
            dev_id = dev_data[-1]
            info[dev_id] = {
                'device_id': dev_data[1],
                'size': dev_data[3],
                'used': dev_data[5],
                }

    return info


def info(device):
    '''
    Get BTRFS filesystem information.

    CLI Example:

    .. code-block:: bash

        salt '*' btrfs.info /dev/sda1
    '''
    out = __salt__['cmd.run_all']("btrfs filesystem show {0}".format(device))
    if out.get('stderr'):
        raise CommandExecutionError(out['stderr'].replace("xfs_info:", "").strip())
    return _parse_btrfs_info(out['stdout'])


def devices():
    '''
    Get known BTRFS formatted devices on the system.

    CLI Example:

    .. code-block:: bash

        salt '*' btrfs.devices
    '''
    out = __salt__['cmd.run_all']("blkid -o export")
    fsutils._verify_run(out)

    return fsutils._blkid_output(out['stdout'], fs_type='btrfs')


def _defragment_mountpoint(mountpoint):
    '''
    Defragment only one BTRFS mountpoint.
    '''
    out = __salt__['cmd.run_all']("btrfs filesystem defragment -f {0}".format(mountpoint))
    return {
        'mount_point': mountpoint,
        'passed': not out['stderr'],
        'log': out['stderr'] or False,
        'range': False,
    }


def defragment(path):
    '''
    Defragment mounted BTRFS filesystem.
    In order to defragment a filesystem, device should be properly mounted and writable.

    If passed a device name, then defragmented whole filesystem, mounted on in.
    If passed a moun tpoint of the filesystem, then only this mount point is defragmented.

    CLI Example:

    .. code-block:: bash

        salt '*' btrfs.defragment /dev/sda1
        salt '*' btrfs.defragment /path/on/filesystem
    '''
    is_device = fsutils._is_device(path)
    mounts = fsutils._get_mounts("btrfs")
    if is_device and not mounts.get(path):
        raise CommandExecutionError("Device \"{0}\" is not mounted".format(path))

    result = []
    if is_device:
        for mount_point in mounts[path]:
            result.append(_defragment_mountpoint(mount_point['mount_point']))
    else:
        is_mountpoint = False
        for device, mountpoints in mounts.items():
            for mpnt in mountpoints:
                if path == mpnt['mount_point']:
                    is_mountpoint = True
                    break
        d_res = _defragment_mountpoint(path)
        if not is_mountpoint and not d_res['passed'] and "range ioctl not supported" in d_res['log']:
            d_res['log'] = "Range ioctl defragmentation is not supported in this kernel."

        if not is_mountpoint:
            d_res['mount_point'] = False
            d_res['range'] = os.path.exists(path) and path or False

        result.append(d_res)

    return result
