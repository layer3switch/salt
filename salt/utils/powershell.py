# -*- coding: utf-8 -*-
'''
Common functions for working with powershell

.. note:: The PSModulePath environment variable should be set to the default
    location for PowerShell modules. This applies to all OS'es that support
    powershell. If not set, then Salt will attempt to use some default paths.
    If Salt can't find your modules, ensure that the PSModulePath is set and
    pointing to all locations of your Powershell modules.
'''
# Import Python libs
from __future__ import absolute_import
import logging
import os

log = logging.getLogger(__name__)


def module_exists(name):
    '''
    Check if a module exists on the system.

    Use this utility instead of attempting to import the module with powershell.
    Using powershell to try to import the module is expensive.

    Args:

        name (str):
            The name of the module to check

    Returns:
        bool: True if present, otherwise returns False

    Example:

    .. code-block:: python

        import salt.utils.powershell
        exists = salt.utils.powershell.module_exists('ServerManager')
    '''
    return name in get_modules()


def get_modules():
    '''
    Get a list of the PowerShell modules which are potentially available to be
    imported. The intent is to mimic the functionality of ``Get-Module
    -ListAvailable | Select-Object -Expand Name``, without the delay of loading
    PowerShell to do so.

    Returns:
        list: A list of modules available to Powershell

    Example:

    .. code-block:: python

        import salt.utils.powershell
        modules = salt.utils.powershell.get_modules()
    '''
    ret = list()
    valid_extensions = ('.psd1', '.psm1', '.cdxml', '.xaml', '.dll')
    env_var = 'PSModulePath'

    # See if PSModulePath is defined in the system environment
    if env_var not in os.environ:
        # Once we determine how to find the PSVersion outside of powershell in
        # other OS'es (non Windows), we'll add additional paths here
        default_paths = [
            '{0}/.local/share/powershell/Modules'.format(os.environ.get('HOME')),
            '/usr/local/share/powershell/Modules']

        # Check if defaults exist, add them if they do
        root_paths = []
        for item in default_paths:
            if os.path.exists(item):
                root_paths.append(item)

        # Did we find any, if not log the error and return
        if not root_paths:
            log.error('Environment variable not present: %s', env_var)
            log.error('Default paths not found')
            return ret

    else:
        # Use PSModulePaths
        root_paths = [
            str(path) for path in os.environ[env_var].split(';') if path]

    for root_path in root_paths:

        # only recurse directories
        if not os.path.isdir(root_path):
            continue

        # get a list of all files in the root_path
        for root_dir, sub_dirs, file_names in os.walk(root_path):
            for file_name in file_names:
                base_name, file_extension = os.path.splitext(file_name)

                # If a module file or module manifest is present, check if
                # the base name matches the directory name.

                if file_extension.lower() in valid_extensions:
                    dir_name = os.path.basename(os.path.normpath(root_dir))

                    # Stop recursion once we find a match, and use
                    # the capitalization from the directory name.
                    if dir_name not in ret and \
                            base_name.lower() == dir_name.lower():
                        del sub_dirs[:]
                        ret.append(dir_name)

    return ret
