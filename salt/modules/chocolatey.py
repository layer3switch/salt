# -*- coding: utf-8 -*-
'''
A dead simple module wrapping calls to the Chocolatey package manager
(http://chocolatey.org)

.. versionadded:: 2014.1.0
'''
from __future__ import absolute_import

# Import python libs
import logging
import os.path
import re
import tempfile
from distutils.version import LooseVersion as _LooseVersion  # pylint: disable=import-error,no-name-in-module

# Import salt libs
import salt.utils
from salt.exceptions import CommandExecutionError, CommandNotFoundError, \
    SaltInvocationError


log = logging.getLogger(__name__)

__func_alias__ = {
    'list_': 'list'
}


def __virtual__():
    '''
    Confirm this module is on a Windows system running Vista or later.

    While it is possible to make Chocolatey run under XP and Server 2003 with
    an awful lot of hassle (e.g. SSL is completely broken), the PowerShell shim
    for simulating UAC forces a GUI prompt, and is not compatible with
    salt-minion running as SYSTEM.
    '''
    if not salt.utils.is_windows():
        return (False, 'Cannot load module chocolatey: Chocolatey requires '
                       'Windows')

    if __grains__['osrelease'] in ('XP', '2003Server'):
        return (False, 'Cannot load module chocolatey: Chocolatey requires '
                       'Windows Vista or later')

    return 'chocolatey'


def _clear_context(context):
    '''
    Clear variables stored in __context__. Run this function when a new version
    of chocolatey is installed.
    '''
    for var in (x for x in __context__ if x.startswith('chocolatey.')):
        context.pop(var)


def _yes(context):
    '''
    Returns ['--yes'] if on v0.9.9.0 or later, otherwise returns an empty list
    '''
    if 'chocolatey._yes' in __context__:
        return context['chocolatey._yes']
    if _LooseVersion(chocolatey_version()) >= _LooseVersion('0.9.9'):
        answer = ['--yes']
    else:
        answer = []
    context['chocolatey._yes'] = answer
    return answer


def _find_chocolatey(context, salt):
    '''
    Returns the full path to chocolatey.bat on the host.
    '''
    if 'chocolatey._path' in context:
        return context['chocolatey._path']
    choc_defaults = ['C:\\Chocolatey\\bin\\chocolatey.bat',
                     'C:\\ProgramData\\Chocolatey\\bin\\chocolatey.exe', ]

    choc_path = salt['cmd.which']('chocolatey.exe')
    if not choc_path:
        for choc_dir in choc_defaults:
            if salt['cmd.has_exec'](choc_dir):
                choc_path = choc_dir
    if not choc_path:
        err = ('Chocolatey not installed. Use chocolatey.bootstrap to '
                'install the Chocolatey package manager.')
        raise CommandExecutionError(err)
    context['chocolatey._path'] = choc_path
    return choc_path


def chocolatey_version():
    '''
    Returns the version of Chocolatey installed on the minion.

    CLI Example:

    .. code-block:: bash

        salt '*' chocolatey.chocolatey_version
    '''
    if 'chocolatey._version' in __context__:
        return __context__['chocolatey._version']

    cmd = [_find_chocolatey(__context__, __salt__)]
    cmd.append('-v')
    out = __salt__['cmd.run'](cmd, python_shell=False)
    __context__['chocolatey._version'] = out

    return __context__['chocolatey._version']


def bootstrap(force=False):
    '''
    Download and install the latest version of the Chocolatey package manager
    via the official bootstrap.

    Chocolatey requires Windows PowerShell and the .NET v4.0 runtime. Depending
    on the host's version of Windows, chocolatey.bootstrap will attempt to
    ensure these prerequisites are met by downloading and executing the
    appropriate installers from Microsoft.

    Note that if PowerShell is installed, you may have to restart the host
    machine for Chocolatey to work.

    force
        Run the bootstrap process even if Chocolatey is found in the path.

    CLI Example:

    .. code-block:: bash

        salt '*' chocolatey.bootstrap
        salt '*' chocolatey.bootstrap force=True
    '''
    # Check if Chocolatey is already present in the path
    try:
        choc_path = _find_chocolatey(__context__, __salt__)
    except CommandExecutionError:
        choc_path = None
    if choc_path and not force:
        return 'Chocolatey found at {0}'.format(choc_path)

    # The following lookup tables are required to determine the correct
    # download required to install PowerShell. That's right, there's more
    # than one! You're welcome.
    ps_downloads = {
        ('Vista', 'x86'): 'http://download.microsoft.com/download/A/7/5/A75BC017-63CE-47D6-8FA4-AFB5C21BAC54/Windows6.0-KB968930-x86.msu',
        ('Vista', 'AMD64'): 'http://download.microsoft.com/download/3/C/8/3C8CF51E-1D9D-4DAA-AAEA-5C48D1CD055C/Windows6.0-KB968930-x64.msu',
        ('2008Server', 'x86'): 'http://download.microsoft.com/download/F/9/E/F9EF6ACB-2BA8-4845-9C10-85FC4A69B207/Windows6.0-KB968930-x86.msu',
        ('2008Server', 'AMD64'): 'http://download.microsoft.com/download/2/8/6/28686477-3242-4E96-9009-30B16BED89AF/Windows6.0-KB968930-x64.msu'
    }

    # It took until .NET v4.0 for Microsoft got the hang of making installers,
    # this should work under any version of Windows
    net4_url = 'http://download.microsoft.com/download/1/B/E/1BE39E79-7E39-46A3-96FF-047F95396215/dotNetFx40_Full_setup.exe'

    temp_dir = tempfile.gettempdir()

    # Check if PowerShell is installed. This should be the case for every
    # Windows release following Server 2008.
    ps_path = 'C:\\Windows\\SYSTEM32\\WindowsPowerShell\\v1.0\\powershell.exe'

    if not __salt__['cmd.has_exec'](ps_path):
        if (__grains__['osrelease'], __grains__['cpuarch']) in ps_downloads:
            # Install the appropriate release of PowerShell v2.0
            url = ps_downloads[(__grains__['osrelease'], __grains__['cpuarch'])]
            dest = os.path.join(temp_dir, 'powershell.exe')
            __salt__['cp.get_url'](url, dest)
            cmd = [dest, '/quiet', '/norestart']
            result = __salt__['cmd.run_all'](cmd, python_shell=False)
            if result['retcode'] != 0:
                err = ('Installing Windows PowerShell failed. Please run the '
                       'installer GUI on the host to get a more specific '
                       'reason.')
                raise CommandExecutionError(err)
        else:
            err = 'Windows PowerShell not found'
            raise CommandNotFoundError(err)

    # Run the .NET Framework 4 web installer
    dest = os.path.join(temp_dir, 'dotnet4.exe')
    __salt__['cp.get_url'](net4_url, dest)
    cmd = [dest, '/q', '/norestart']
    result = __salt__['cmd.run_all'](cmd, python_shell=False)
    if result['retcode'] != 0:
        err = ('Installing .NET v4.0 failed. Please run the installer GUI on '
               'the host to get a more specific reason.')
        raise CommandExecutionError(err)

    # Run the Chocolatey bootstrap.
    cmd = (
        '{0} -NoProfile -ExecutionPolicy unrestricted '
        '-Command "iex ((new-object net.webclient).'
        'DownloadString(\'https://chocolatey.org/install.ps1\'))" '
        '&& SET PATH=%PATH%;%systemdrive%\\chocolatey\\bin'
        .format(ps_path)
    )
    result = __salt__['cmd.run_all'](cmd, python_shell=True)

    if result['retcode'] != 0:
        err = 'Bootstrapping Chocolatey failed: {0}'.format(result['stderr'])
        raise CommandExecutionError(err)

    return result['stdout']


def list_(narrow=None,
          all_versions=False,
          pre_versions=False,
          source=None,
          local_only=False,
          exact=False):
    '''
    Instructs Chocolatey to pull a vague package list from the repository.

    Args:

        narrow (str):
            Term used to narrow down results. Searches against
            name/description/tag. Default is None.

        all_versions (bool):
            Display all available package versions in results. Default is False.

        pre_versions (bool):
            Display pre-release packages in results. Default is False.

        source (str):
            Chocolatey repository (directory, share or remote URL feed) the
            package comes from. Defaults to the official Chocolatey feed if
            None is passed. Default is None.

        local_only (bool):
            Display packages only installed locally. Default is False.

        exact (bool):
            Display only packages that match ``narrow`` exactly. Default is
            False.

            .. versionadded:: Nitrogen

    Returns:
        dict: A dictionary of results.

    CLI Example:

    .. code-block:: bash

        salt '*' chocolatey.list <narrow>
        salt '*' chocolatey.list <narrow> all_versions=True
    '''
    choc_path = _find_chocolatey(__context__, __salt__)
    cmd = [choc_path, 'list']
    if narrow:
        cmd.append(narrow)
    if salt.utils.is_true(all_versions):
        cmd.append('-allversions')
    if salt.utils.is_true(pre_versions):
        cmd.append('-prerelease')
    if source:
        cmd.extend(['-source', source])
    if local_only:
        cmd.append('--local-only')
    if exact:
        cmd.append('--exact')

    # This is needed to parse the output correctly
    cmd.append('--limit-output')

    result = __salt__['cmd.run_all'](cmd, python_shell=False)

    if result['retcode'] != 0:
        err = 'Running chocolatey failed: {0}'.format(result['stdout'])
        raise CommandExecutionError(err)

    ret = {}
    pkg_re = re.compile(r'(\S+)\|(\S+)')
    for line in result['stdout'].split('\n'):
        if line.startswith("No packages"):
            return ret
        for name, ver in pkg_re.findall(line):
            if 'chocolatey' in name:
                continue
            if name not in ret:
                ret[name] = []
            ret[name].append(ver)

    return ret


def list_webpi():
    '''
    Instructs Chocolatey to pull a full package list from the Microsoft Web PI
    repository.

    Returns:
        str: List of webpi packages

    CLI Example:

    .. code-block:: bash

        salt '*' chocolatey.list_webpi
    '''
    choc_path = _find_chocolatey(__context__, __salt__)
    cmd = [choc_path, 'list', '-source', 'webpi']
    result = __salt__['cmd.run_all'](cmd, python_shell=False)

    if result['retcode'] != 0:
        err = 'Running chocolatey failed: {0}'.format(result['stdout'])
        raise CommandExecutionError(err)

    return result['stdout']


def list_windowsfeatures():
    '''
    Instructs Chocolatey to pull a full package list from the Windows Features
    list, via the Deployment Image Servicing and Management tool.

    Returns:
        str: List of Windows Features

    CLI Example:

    .. code-block:: bash

        salt '*' chocolatey.list_windowsfeatures
    '''
    choc_path = _find_chocolatey(__context__, __salt__)
    cmd = [choc_path, 'list', '-source', 'windowsfeatures']
    result = __salt__['cmd.run_all'](cmd, python_shell=False)

    if result['retcode'] != 0:
        err = 'Running chocolatey failed: {0}'.format(result['stdout'])
        raise CommandExecutionError(err)

    return result['stdout']


def install(name,
            version=None,
            source=None,
            force=False,
            pre_versions=False,
            install_args=None,
            override_args=False,
            force_x86=False,
            package_args=None,
            allow_multiple=False):
    '''
    Instructs Chocolatey to install a package.

    Args:

        name (str):
            The name of the package to be installed. Only accepts a single
            argument. Required.

        version (str):
            Install a specific version of the package. Defaults to latest
            version. Default is None.

        source (str):
            Chocolatey repository (directory, share or remote URL feed) the
            package comes from. Defaults to the official Chocolatey feed.
            Default is None.

            Alternate Sources:

            - cygwin
            - python
            - ruby
            - webpi
            - windowsfeatures

        force (bool):
            Reinstall the current version of an existing package. Do not use
            with ``allow_multiple``. Default is False.

        pre_versions (bool):
            Include pre-release packages. Default is False.

        install_args (str):
            A list of install arguments you want to pass to the installation
            process i.e product key or feature list. Default is None.

        override_args (bool):
            Set to true if you want to override the original install arguments
            (for the native installer) in the package and use your own. When
            this is set to False install_args will be appended to the end of the
            default arguments. Default is None.

        force_x86 (bool):
            Force x86 (32bit) installation on 64 bit systems. Default is False.

        package_args (str):
            Arguments you want to pass to the package. Default is None.

        allow_multiple (bool):
            Allow multiple versions of the package to be installed. Do not use
            with ``force``. Does not work with all packages. Default is False.

            .. versionadded:: Nitrogen

    Returns:
        str: The output of the ``chocolatey`` command

    CLI Example:

    .. code-block:: bash

        salt '*' chocolatey.install <package name>
        salt '*' chocolatey.install <package name> version=<package version>
        salt '*' chocolatey.install <package name> install_args=<args> override_args=True
    '''
    if force and allow_multiple:
        raise SaltInvocationError(
            'Cannot use \'force\' in conjunction with \'allow_multiple\'')

    choc_path = _find_chocolatey(__context__, __salt__)
    # chocolatey helpfully only supports a single package argument
    cmd = [choc_path, 'install', name]
    if version:
        cmd.extend(['--version', version])
    if source:
        cmd.extend(['--source', source])
    if salt.utils.is_true(force):
        cmd.append('--force')
    if salt.utils.is_true(pre_versions):
        cmd.append('--prerelease')
    if install_args:
        cmd.extend(['--installarguments', install_args])
    if override_args:
        cmd.append('--overridearguments')
    if force_x86:
        cmd.append('--forcex86')
    if package_args:
        cmd.extend(['--packageparameters', package_args])
    if allow_multiple:
        cmd.append('--allow-multiple')
    cmd.extend(_yes(__context__))
    result = __salt__['cmd.run_all'](cmd, python_shell=False)

    if result['retcode'] not in [0, 1641, 3010]:
        err = 'Running chocolatey failed: {0}'.format(result['stdout'])
        raise CommandExecutionError(err)

    if name == 'chocolatey':
        _clear_context(__context__)

    return result['stdout']


def install_cygwin(name, install_args=None, override_args=False):
    '''
    Instructs Chocolatey to install a package via Cygwin.

    name
        The name of the package to be installed. Only accepts a single argument.

    install_args
        A list of install arguments you want to pass to the installation process
        i.e product key or feature list

    override_args
        Set to true if you want to override the original install arguments (for
        the native installer) in the package and use your own. When this is set
        to False install_args will be appended to the end of the default
        arguments

    CLI Example:

    .. code-block:: bash

        salt '*' chocolatey.install_cygwin <package name>
        salt '*' chocolatey.install_cygwin <package name> install_args=<args> override_args=True
    '''
    return install(name,
                   source='cygwin',
                   install_args=install_args,
                   override_args=override_args)


def install_gem(name, version=None, install_args=None, override_args=False):
    '''
    Instructs Chocolatey to install a package via Ruby's Gems.

    name
        The name of the package to be installed. Only accepts a single argument.

    version
        Install a specific version of the package. Defaults to latest version
        available.

    install_args
        A list of install arguments you want to pass to the installation process
        i.e product key or feature list

    override_args
        Set to true if you want to override the original install arguments (for
        the native installer) in the package and use your own. When this is set
        to False install_args will be appended to the end of the default
        arguments


    CLI Example:

    .. code-block:: bash

        salt '*' chocolatey.install_gem <package name>
        salt '*' chocolatey.install_gem <package name> version=<package version>
        salt '*' chocolatey.install_gem <package name> install_args=<args> override_args=True
    '''
    return install(name,
                   version=version,
                   source='ruby',
                   install_args=install_args,
                   override_args=override_args)


def install_missing(name, version=None, source=None):
    '''
    Instructs Chocolatey to install a package if it doesn't already exist.

    .. versionchanged:: 2014.7.0
        If the minion has Chocolatey >= 0.9.8.24 installed, this function calls
        :mod:`chocolatey.install <salt.modules.chocolatey.install>` instead, as
        ``installmissing`` is deprecated as of that version and will be removed
        in Chocolatey 1.0.

    name
        The name of the package to be installed. Only accepts a single argument.

    version
        Install a specific version of the package. Defaults to latest version
        available.

    source
        Chocolatey repository (directory, share or remote URL feed) the package
        comes from. Defaults to the official Chocolatey feed.

    CLI Example:

    .. code-block:: bash

        salt '*' chocolatey.install_missing <package name>
        salt '*' chocolatey.install_missing <package name> version=<package version>
    '''
    choc_path = _find_chocolatey(__context__, __salt__)
    if _LooseVersion(chocolatey_version()) >= _LooseVersion('0.9.8.24'):
        log.warning('installmissing is deprecated, using install')
        return install(name, version=version)

    # chocolatey helpfully only supports a single package argument
    cmd = [choc_path, 'installmissing', name]
    if version:
        cmd.extend(['-version', version])
    if source:
        cmd.extend(['-source', source])
    # Shouldn't need this as this code should never run on v0.9.9 and newer
    cmd.extend(_yes(__context__))
    result = __salt__['cmd.run_all'](cmd, python_shell=False)

    if result['retcode'] != 0:
        err = 'Running chocolatey failed: {0}'.format(result['stdout'])
        raise CommandExecutionError(err)

    return result['stdout']


def install_python(name, version=None, install_args=None, override_args=False):
    '''
    Instructs Chocolatey to install a package via Python's easy_install.

    name
        The name of the package to be installed. Only accepts a single argument.

    version
        Install a specific version of the package. Defaults to latest version
        available.

    install_args
        A list of install arguments you want to pass to the installation process
        i.e product key or feature list

    override_args
        Set to true if you want to override the original install arguments (for
        the native installer) in the package and use your own. When this is set
        to False install_args will be appended to the end of the default
        arguments

    CLI Example:

    .. code-block:: bash

        salt '*' chocolatey.install_python <package name>
        salt '*' chocolatey.install_python <package name> version=<package version>
        salt '*' chocolatey.install_python <package name> install_args=<args> override_args=True
    '''
    return install(name,
                   version=version,
                   source='python',
                   install_args=install_args,
                   override_args=override_args)


def install_windowsfeatures(name):
    '''
    Instructs Chocolatey to install a Windows Feature via the Deployment Image
    Servicing and Management tool.

    name
        The name of the feature to be installed. Only accepts a single argument.

    CLI Example:

    .. code-block:: bash

        salt '*' chocolatey.install_windowsfeatures <package name>
    '''
    return install(name, source='windowsfeatures')


def install_webpi(name, install_args=None, override_args=False):
    '''
    Instructs Chocolatey to install a package via the Microsoft Web PI service.

    name
        The name of the package to be installed. Only accepts a single argument.

    install_args
        A list of install arguments you want to pass to the installation process
        i.e product key or feature list

    override_args
        Set to true if you want to override the original install arguments (for
        the native installer) in the package and use your own. When this is set
        to False install_args will be appended to the end of the default
        arguments

    CLI Example:

    .. code-block:: bash

        salt '*' chocolatey.install_webpi <package name>
        salt '*' chocolatey.install_webpi <package name> install_args=<args> override_args=True
    '''
    return install(name,
                   source='webpi',
                   install_args=install_args,
                   override_args=override_args)


def uninstall(name, version=None, uninstall_args=None, override_args=False):
    '''
    Instructs Chocolatey to uninstall a package.

    name
        The name of the package to be uninstalled. Only accepts a single
        argument.

    version
        Uninstalls a specific version of the package. Defaults to latest version
        installed.

    uninstall_args
        A list of uninstall arguments you want to pass to the uninstallation
        process i.e product key or feature list

    override_args
        Set to true if you want to override the original uninstall arguments
        (for the native uninstaller) in the package and use your own. When this
        is set to False uninstall_args will be appended to the end of the
        default arguments

    CLI Example:

    .. code-block:: bash

        salt '*' chocolatey.uninstall <package name>
        salt '*' chocolatey.uninstall <package name> version=<package version>
        salt '*' chocolatey.uninstall <package name> version=<package version> uninstall_args=<args> override_args=True
    '''
    choc_path = _find_chocolatey(__context__, __salt__)
    # chocolatey helpfully only supports a single package argument
    cmd = [choc_path, 'uninstall', name]
    if version:
        cmd.extend(['-version', version])
    if uninstall_args:
        cmd.extend(['-uninstallarguments', uninstall_args])
    if override_args:
        cmd.extend(['-overridearguments'])
    cmd.extend(_yes(__context__))
    result = __salt__['cmd.run_all'](cmd, python_shell=False)

    if result['retcode'] not in [0, 1605, 1614, 1641]:
        err = 'Running chocolatey failed: {0}'.format(result['stdout'])
        raise CommandExecutionError(err)

    return result['stdout']


def upgrade(name,
            version=None,
            source=None,
            force=False,
            pre_versions=False,
            install_args=None,
            override_args=False,
            force_x86=False,
            package_args=None):
    '''
    .. versionadded:: 2016.3.4

    Instructs Chocolatey to upgrade packages on the system. (update is being
    deprecated)

    Args:

        name (str):
            The name of the package to update, or "all" to update everything
            installed on the system.

        version (str):
            Install a specific version of the package. Defaults to latest
            version.

        source (str):
            Chocolatey repository (directory, share or remote URL feed) the
            package comes from. Defaults to the official Chocolatey feed.

        force (bool):
            Reinstall the **same** version already installed

        pre_versions (bool):
            Include pre-release packages in comparison. Defaults to False.

        install_args (str):
            A list of install arguments you want to pass to the installation
            process i.e product key or feature list

        override_args (str):
            Set to true if you want to override the original install arguments
            (for the native installer) in the package and use your own. When
            this is set to False install_args will be appended to the end of the
            default arguments

        force_x86
            Force x86 (32bit) installation on 64 bit systems. Defaults to false.

        package_args
            A list of arguments you want to pass to the package

    Returns:
        str: Results of the ``chocolatey`` command

    CLI Example:

    .. code-block:: bash

        salt "*" chocolatey.upgrade all
        salt "*" chocolatey.upgrade <package name> pre_versions=True
    '''
    # chocolatey helpfully only supports a single package argument
    choc_path = _find_chocolatey(__context__, __salt__)
    cmd = [choc_path, 'upgrade', name]
    if version:
        cmd.extend(['-version', version])
    if source:
        cmd.extend(['-source', source])
    if salt.utils.is_true(force):
        cmd.append('-force')
    if salt.utils.is_true(pre_versions):
        cmd.append('-prerelease')
    if install_args:
        cmd.extend(['-installarguments', install_args])
    if override_args:
        cmd.append('-overridearguments')
    if force_x86:
        cmd.append('-forcex86')
    if package_args:
        cmd.extend(['-packageparameters', package_args])
    cmd.extend(_yes(__context__))

    result = __salt__['cmd.run_all'](cmd, python_shell=False)

    if result['retcode'] not in [0, 1641, 3010]:
        err = 'Running chocolatey failed: {0}'.format(result['stdout'])
        raise CommandExecutionError(err)

    return result['stdout']


def update(name, source=None, pre_versions=False):
    '''
    Instructs Chocolatey to update packages on the system.

    name
        The name of the package to update, or "all" to update everything
        installed on the system.

    source
        Chocolatey repository (directory, share or remote URL feed) the package
        comes from. Defaults to the official Chocolatey feed.

    pre_versions
        Include pre-release packages in comparison. Defaults to False.

    CLI Example:

    .. code-block:: bash

        salt "*" chocolatey.update all
        salt "*" chocolatey.update <package name> pre_versions=True
    '''
    # chocolatey helpfully only supports a single package argument
    choc_path = _find_chocolatey(__context__, __salt__)
    if _LooseVersion(chocolatey_version()) >= _LooseVersion('0.9.8.24'):
        log.warning('update is deprecated, using upgrade')
        return upgrade(name, source=source, pre_versions=pre_versions)

    cmd = [choc_path, 'update', name]
    if source:
        cmd.extend(['-source', source])
    if salt.utils.is_true(pre_versions):
        cmd.append('-prerelease')
    cmd.extend(_yes(__context__))
    result = __salt__['cmd.run_all'](cmd, python_shell=False)

    if result['retcode'] not in [0, 1641, 3010]:
        err = 'Running chocolatey failed: {0}'.format(result['stdout'])
        raise CommandExecutionError(err)

    return result['stdout']


def version(name, check_remote=False, source=None, pre_versions=False):
    '''
    Instructs Chocolatey to check an installed package version, and optionally
    compare it to one available from a remote feed.

    Args:

        name (str):
            The name of the package to check. Required.

        check_remote (bool):
            Get the version number of the latest package from the remote feed.
            Default is False.

        source (str):
            Chocolatey repository (directory, share or remote URL feed) the
            package comes from. Defaults to the official Chocolatey feed.
            Default is None.

        pre_versions (bool):
            Include pre-release packages in comparison. Default is False.

    Returns:
        dict: A dictionary of currently installed software and versions

    CLI Example:

    .. code-block:: bash

        salt "*" chocolatey.version <package name>
        salt "*" chocolatey.version <package name> check_remote=True
    '''
    installed = list_(narrow=name, local_only=True)

    packages = {}
    for pkg in installed:
        if name.lower() in pkg.lower():
            packages[pkg] = installed[pkg]

    if check_remote:
        available = list_(narrow=name, pre_versions=pre_versions, source=source)

        for pkg in packages:
            packages[pkg] = {'installed': installed[pkg],
                             'available': available[pkg]}

    return packages


def add_source(name, source_location, username=None, password=None):
    '''
    Instructs Chocolatey to add a source.

    name
        The name of the source to be added as a chocolatey repository.

    source
        Location of the source you want to work with.

    username
        Provide username for chocolatey sources that need authentication
        credentials.

    password
        Provide password for chocolatey sources that need authentication
        credentials.

    CLI Example:

    .. code-block:: bash

        salt '*' chocolatey.add_source <source name> <source_location>
        salt '*' chocolatey.add_source <source name> <source_location> user=<user> password=<password>

    '''
    choc_path = _find_chocolatey(__context__, __salt__)
    cmd = [choc_path, 'sources', 'add', '-name', name, "-source", source_location]
    if username:
        cmd.extend(['-u', username])
    if password:
        cmd.extend(['-p', password])
    result = __salt__['cmd.run_all'](cmd, python_shell=False)

    if result['retcode'] != 0:
        err = 'Running chocolatey failed: {0}'.format(result['stdout'])
        raise CommandExecutionError(err)

    return result['stdout']


def _change_source_state(name, state):
    '''
    Instructs Chocolatey to change the state of a source.

    name
        Name of the repository to affect.

    state
        State in which you want the chocolatey repository.

    '''
    choc_path = _find_chocolatey(__context__, __salt__)
    cmd = [choc_path, 'source', state, "-name", name]
    result = __salt__['cmd.run_all'](cmd, python_shell=False)

    if result['retcode'] != 0:
        err = 'Running chocolatey failed: {0}'.format(result['stdout'])
        raise CommandExecutionError(err)

    return result['stdout']


def enable_source(name):
    '''
    Instructs Chocolatey to enable a source.

    name
        Name of the source repository to enable.

    CLI Example:

    .. code-block:: bash

        salt '*' chocolatey.enable_source <name>

    '''
    return _change_source_state(name, "enable")


def disable_source(name):
    '''
    Instructs Chocolatey to disable a source.

    name
        Name of the source repository to disable.

    CLI Example:

    .. code-block:: bash

        salt '*' chocolatey.disable_source <name>
    '''
    return _change_source_state(name, "disable")
