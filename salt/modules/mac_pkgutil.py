# -*- coding: utf-8 -*-
'''
Installer support for OS X.

Installer is the native .pkg/.mpkg package manager for OS X.
'''

# Import Python libs
from __future__ import absolute_import
import os.path

# Import 3rd-party libs
from salt.ext.six.moves import urllib  # pylint: disable=import-error

# Import salt libs
import salt.utils
import salt.utils.itertools
import salt.utils.mac_utils
from salt.exceptions import SaltInvocationError

# Don't shadow built-in's.
__func_alias__ = {'list_': 'list'}

# Define the module's virtual name
__virtualname__ = 'pkgutil'


def __virtual__():
    if not salt.utils.is_darwin():
        return (False, 'Only available on Mac OS systems')

    if not salt.utils.which('pkgutil'):
        return (False, 'Missing pkgutil binary')

    return __virtualname__


def list_():
    '''
    List the installed packages.

    :return: A list of installed packages
    :rtype: list

    CLI Example:

    .. code-block:: bash

        salt '*' pkgutil.list
    '''
    cmd = 'pkgutil --pkgs'
    ret = salt.utils.mac_utils.execute_return_result(cmd)
    return ret.splitlines()


def is_installed(package_id):
    '''
    Returns whether a given package id is installed.

    :return: True if installed, otherwise False
    :rtype: bool

    CLI Example:

    .. code-block:: bash

        salt '*' pkgutil.is_installed com.apple.pkg.gcc4.2Leo
    '''
    return package_id in list_()


def _install_from_path(path):
    '''
    Internal function to install a package from the given path
    '''
    if not os.path.exists(path):
        msg = 'File not found: {0}'.format(path)
        raise SaltInvocationError(msg)

    cmd = 'installer -pkg "{0}" -target /'.format(path)
    return salt.utils.mac_utils.execute_return_success(cmd)


def install(source, package_id):
    '''
    Install a .pkg from an URI or an absolute path.

    :param str source: The path to a package.

    :param str package_id: The package ID

    :return: True if successful, otherwise False
    :rtype: bool

    CLI Example:

    .. code-block:: bash

        salt '*' pkgutil.install source=/vagrant/build_essentials.pkg package_id=com.apple.pkg.gcc4.2Leo
    '''
    if is_installed(package_id):
        return False

    uri = urllib.parse.urlparse(source)
    if uri.scheme == '':
        _install_from_path(source)
    else:
        msg = 'Unsupported scheme for source uri: {0}'.format(uri.scheme)
        raise SaltInvocationError(msg)

    return is_installed(package_id)
