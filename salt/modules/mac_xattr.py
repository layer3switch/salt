# -*- coding: utf-8 -*-
'''
This module allows you to manage extended attributes on files or directories

.. code-block:: bash

    salt '*' xattr.list /path/to/file
'''
from __future__ import absolute_import

# Import Python Libs
import logging

# Import salt libs
import salt.utils.mac_utils
from salt.exceptions import CommandExecutionError

log = logging.getLogger(__name__)
__virtualname__ = "xattr"


def __virtual__():
    '''
    Only work on Mac OS
    '''
    if __grains__['os'] in ['MacOS', 'Darwin']:
        return __virtualname__
    return False


def list(path, hex=False):
    '''
    List all of the extended attributes on the given file/directory

    :param str path: The file(s) to get attributes from

    :param bool hex: return the values with forced hexadecimal values

    CLI Example:

    .. code-block:: bash

        salt '*' xattr.list /path/to/file
        salt '*' xattr.list /path/to/file hex=True
    '''
    hex_flag = ""
    if hex:
        hex_flag = "-x"
    cmd = 'xattr "{0}"'.format(path)
    try:
        ret = salt.utils.mac_utils.execute_return_result(cmd)
    except CommandExecutionError as exc:
        if 'No such file' in exc.strerror:
            raise CommandExecutionError('File not found: {0}'.format(path))
        return {'Unknown Error': format(exc.strerror)}

    if not ret:
        return {}

    attrs_ids = ret.split("\n")
    attrs = {}

    for id in attrs_ids:
        attrs[id] = read(path, id, hex)

    return attrs


def read(path, attribute, hex=False):
    '''
    Read the given attributes on the given file/directory

    :param str path: The file to get attributes from

    :param str attribute: The attribute to read

    :param bool hex: return the values with forced hexadecimal values

    CLI Example:

    .. code-block:: bash

        salt '*' xattr.read /path/to/file com.test.attr
        salt '*' xattr.read /path/to/file com.test.attr hex=True
    '''
    hex_flag = ""
    if hex:
        hex_flag = "-x"

    cmd = 'xattr -p {0} "{1}" "{2}"'.format(hex_flag, attribute, path)

    try:
        ret = salt.utils.mac_utils.execute_return_result(cmd)
    except CommandExecutionError as exc:
        if 'No such file' in exc.strerror:
            raise CommandExecutionError('File not found: {0}'.format(path))
        if 'No such xattr' in exc.strerror:
            raise CommandExecutionError('Attribute not found: {0}'.format(attribute))
        return 'Unknown Error: {0}'.format(exc.strerror)

    return ret


def write(path, attribute, value, hex=False):
    '''
    Causes the given attribute name to be assigned the given value

    :param str path: The file(s) to get attributes from

    :param str attribute: The attribute name to be written to the file/directory

    :param str value: The value to assign to the given attribute

    :param bool hex: return the values with forced hexadecimal values

    CLI Example:

    .. code-block:: bash

        salt '*' xattr.write /path/to/file "com.test.attr" "value"

    '''
    hex_flag = ""
    if hex:
        hex_flag = "-x"

    cmd = 'xattr -w {0} "{1}" "{2}" "{3}"'.format(hex_flag, attribute, value, path)
    try:
        salt.utils.mac_utils.execute_return_success(cmd)
    except CommandExecutionError as exc:
        if 'No such file' in exc.strerror:
            raise CommandExecutionError('File not found: {0}'.format(path))
        return False

    return True


def delete(path, attribute):
    '''
    Causes the given attribute name to be removed from the given value

    :param str path: The file(s) to get attributes from

    :param str attribute: The attribute name to be written to the file/directory

    CLI Example:

    .. code-block:: bash

        salt '*' xattr.delete /path/to/file "com.test.attr"
    '''
    cmd = 'xattr -d "{0}" "{1}"'.format(attribute, path)
    try:
        salt.utils.mac_utils.execute_return_success(cmd)
    except CommandExecutionError as exc:
        if 'such file' in exc.strerror:
            raise CommandExecutionError('File not found: {0}'.format(path))
        if 'such xattr' in exc.strerror:
            raise CommandExecutionError('Attribute not found: {0}'.format(attribute))
        return False

    return True


def clear(path):
    '''
    Causes the all attributes on the file/directory to be removed

    :param str path: The file(s) to get attributes from

    CLI Example:

    .. code-block:: bash

        salt '*' xattr.delete /path/to/file "com.test.attr"
    '''
    cmd = 'xattr -c "{0}"'.format(path)
    try:
        salt.utils.mac_utils.execute_return_success(cmd)
    except CommandExecutionError as exc:
        if 'No such file' in exc.strerror:
            raise CommandExecutionError('File not found: {0}'.format(path))
        return False

    return True
