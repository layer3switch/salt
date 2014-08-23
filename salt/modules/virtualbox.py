# -*- coding: utf-8 -*-
'''
VirtualBox Guest Additions installer
'''

# Import python libs
import contextlib
import functools
import glob
import logging
import os
import re
import tempfile

# Import salt libs
import salt.utils
from salt.exceptions import CommandExecutionError

log = logging.getLogger(__name__)


__virtualname__ = 'virtualbox'

_guest_additions_dir_prefix = 'VBoxGuestAdditions'

def __virtual__():
    '''
    Set the virtualbox module if the OS Linux
    '''
    if __grains__.get('kernel', '') not in ('Linux'):
        return False
    return __virtualname__



def guest_additions_mount():
    '''
    Mount VirtualBox Guest Additions CD to the temp directory

    CLI Example:

    .. code-block:: bash

        salt '*' virtualbox.guest_additions_mount
    '''
    mount_point = tempfile.mkdtemp()
    ret = __salt__['mount.mount'](mount_point, '/dev/cdrom')
    if ret is True:
        return mount_point
    else:
        raise OSError(ret)


def guest_additions_umount(mount_point):
    '''
    Unmount VirtualBox Guest Additions CD from the temp directory

    CLI Example:

    .. code-block:: bash

        salt '*' virtualbox.guest_additions_umount
    '''
    ret = __salt__['mount.umount'](mount_point)
    if ret:
        os.rmdir(mount_point)
    return ret


@contextlib.contextmanager
def _guest_additions_mounted():
    mount_point = guest_additions_mount()
    yield mount_point
    guest_additions_umount(mount_point)


def _return_mount_error(f):
    @functools.wraps(f)
    def wrapper(*args, **kwargs):
        try:
            return f(*args, **kwargs)
        except OSError as e:
            return str(e)
    return wrapper


def _guest_additions_install_program_path(mount_point):
    return os.path.join(mount_point, {
        'Linux': 'VBoxLinuxAdditions.run',
        'Solaris': 'VBoxSolarisAdditions.pkg',
        'Windows': 'VBoxWindowsAdditions.exe'
    }[__grains__.get('kernel', '')])


def _guest_additions_install_opensuse(**kwargs):
    upgrade_os = kwargs.pop('upgrade_os', True)
    if upgrade_os:
        __salt__['pkg.upgrade']()
    kernel_type = re.sub(r'^(\d|\.|-)*', '',  __grains__.get('kernelrelease', ''))
    kernel_devel = 'kernel-{}-devel'.format(kernel_type)
    ret = __salt__['state.single'](
            'pkg.installed', 'devel packages', pkgs=['make','gcc', kernel_devel])
    return ret


def _guest_additions_install_linux(mount_point, **kwargs):
    reboot = kwargs.pop('reboot', False)
    restart_x11 = kwargs.pop('restart_x11', False)
    # dangerous: do not call variable `os` as it will hide os module
    guest_os = __grains__.get('os', '')
    if guest_os == 'openSUSE':
        _guest_additions_install_opensuse(**kwargs)
    else:
        raise NotImplementedError("{} is not supported yet.".format(guest_os))
    installer_path = _guest_additions_install_program_path(mount_point)
    installer_ret = __salt__['cmd.run_all'](installer_path)
    if installer_ret['retcode'] in (0, 1):
        if reboot:
            __salt__['system.reboot']()
        elif restart_x11:
            raise NotImplementedError("Restarting x11 is not supported yet.")
        else:
            # VirtualBox script enables module itself, need to restart OS
            # anyway, probably don't need that.
            # for service in ('vboxadd', 'vboxadd-service', 'vboxadd-x11'):
            #     __salt__['service.start'](service)
            pass
        return guest_additions_version()
    elif installer_ret['retcode'] in (127, '127'):
        return ("'{}' not found on CD. Make sure that VirtualBox Guest "
                "Additions CD is attached to the CD IDE Controller.".format(
                    os.path.basename(installer_path)))
    else:
        return installer_ret['stderr']



@_return_mount_error
def guest_additions_install(**kwargs):
    '''
    Install VirtualBox Guest Additions. Uses the CD, connected by VirtualBox

    CLI Example:

    .. code-block:: bash

        salt '*' virtualbox.guest_additions_install
        salt '*' virtualbox.guest_additions_install reboot=True
        salt '*' virtualbox.guest_additions_install upgrade_os=False
    '''
    with _guest_additions_mounted() as mount_point:
        kernel = __grains__.get('kernel', '')
        if kernel == 'Linux':
            return _guest_additions_install_linux(mount_point, **kwargs)


def _guest_additions_dir():
    root = '/opt'
    dirs = glob.glob(os.path.join(root, _guest_additions_dir_prefix) + '*')
    if dirs:
        return dirs[0]
    else:
        raise EnvironmentError('No VirtualBox Guest Additions dirs found!')


def _guest_additions_remove_linux_run(cmd):
    uninstaller_ret = __salt__['cmd.run_all'](cmd)
    return uninstaller_ret['retcode'] in (0, )


def _guest_additions_remove_linux(**kwargs):
    try:
        return _guest_additions_remove_linux_run(
                os.path.join(_guest_additions_dir(), 'uninstall.sh'))
    except EnvironmentError:
        return False


def _guest_additions_remove_linux_use_cd(mount_point, **kwargs):
    force = kwargs.pop('force', False)
    args = ''
    if force:
        args += '--force'
    return _guest_additions_remove_linux_run('{program} uninstall {args}'.format(
        program=_guest_additions_install_program_path(mount_point), args=args))


@_return_mount_error
def _guest_additions_remove_use_cd(**kwargs):
    '''
    Remove VirtualBox Guest Additions.

    It uses the CD, connected by VirtualBox.
    '''

    with _guest_additions_mounted() as mount_point:
        kernel = __grains__.get('kernel', '')
        if kernel == 'Linux':
            return _guest_additions_remove_linux_use_cd(mount_point, **kwargs)


def guest_additions_remove(**kwargs):
    '''
    Remove VirtualBox Guest Additions.

    Firstly it tries to uninstall itself by executing
    '/opt/VBoxGuestAdditions-VERSION/uninstall.run uninstall'.
    It uses the CD, connected by VirtualBox if it failes.

    CLI Example:

    .. code-block:: bash

        salt '*' virtualbox.guest_additions_remove
        salt '*' virtualbox.guest_additions_remove force=True
    '''
    kernel = __grains__.get('kernel', '')
    if kernel == 'Linux':
        ret = _guest_additions_remove_linux()
    if not ret:
        ret = _guest_additions_remove_use_cd(**kwargs)
    return ret


def guest_additions_version():
    '''
    Check VirtualBox Guest Additions version.

    CLI Example:

    .. code-block:: bash

        salt '*' virtualbox.guest_additions_version
    '''
    try:
        d = _guest_additions_dir()
    except EnvironmentError:
        return False
    if d and len(os.listdir(d)) > 0:
        return re.sub(r'^{}-'.format(_guest_additions_dir_prefix), '',
                os.path.basename(d))
    return False
