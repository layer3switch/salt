# -*- coding: utf-8 -*-
'''
A module to wrap pacman calls, since Arch is the best
(https://wiki.archlinux.org/index.php/Arch_is_the_best)

.. important::
    If you feel that Salt should be using this module to manage packages on a
    minion, and it is using a different module (or gives an error similar to
    *'pkg.install' is not available*), see :ref:`here
    <module-provider-override>`.
'''

# Import python libs
from __future__ import absolute_import
import copy
import logging
import re
import os.path

# Import salt libs
import salt.utils
import salt.utils.itertools
import salt.utils.systemd
from salt.exceptions import CommandExecutionError, MinionError

# Import 3rd-party libs
import salt.ext.six as six

log = logging.getLogger(__name__)

# Define the module's virtual name
__virtualname__ = 'pkg'


def __virtual__():
    '''
    Set the virtual pkg module if the os is Arch
    '''
    if __grains__['os'] in ('Arch', 'Arch ARM', 'Antergos', 'ManjaroLinux'):
        return __virtualname__
    return (False, 'The pacman module could not be loaded: unsupported OS family.')


def _list_removed(old, new):
    '''
    List the packages which have been removed between the two package objects
    '''
    return [x for x in old if x not in new]


def latest_version(*names, **kwargs):
    '''
    Return the latest version of the named package available for upgrade or
    installation. If more than one package name is specified, a dict of
    name/version pairs is returned.

    If the latest version of a given package is already installed, an empty
    string will be returned for that package.

    CLI Example:

    .. code-block:: bash

        salt '*' pkg.latest_version <package name>
        salt '*' pkg.latest_version <package1> <package2> <package3> ...
    '''
    refresh = salt.utils.is_true(kwargs.pop('refresh', False))

    if len(names) == 0:
        return ''

    # Refresh before looking for the latest version available
    if refresh:
        refresh_db()

    ret = {}
    # Initialize the dict with empty strings
    for name in names:
        ret[name] = ''
    cmd = ['pacman', '-Sp', '--needed', '--print-format', '%n %v']
    cmd.extend(names)

    if 'root' in kwargs:
        cmd.extend(('-r', kwargs['root']))

    out = __salt__['cmd.run_stdout'](cmd,
                                     output_loglevel='trace',
                                     python_shell=False)
    for line in salt.utils.itertools.split(out, '\n'):
        try:
            name, version_num = line.split()
            # Only add to return dict if package is in the list of packages
            # passed, otherwise dependencies will make their way into the
            # return data.
            if name in names:
                ret[name] = version_num
        except (ValueError, IndexError):
            pass

    # Return a string if only one package name passed
    if len(names) == 1:
        return ret[names[0]]
    return ret

# available_version is being deprecated
available_version = salt.utils.alias_function(latest_version, 'available_version')


def upgrade_available(name):
    '''
    Check whether or not an upgrade is available for a given package

    CLI Example:

    .. code-block:: bash

        salt '*' pkg.upgrade_available <package name>
    '''
    return latest_version(name) != ''


def list_upgrades(refresh=False, root=None, **kwargs):  # pylint: disable=W0613
    '''
    List all available package upgrades on this system

    CLI Example:

    .. code-block:: bash

        salt '*' pkg.list_upgrades
    '''
    upgrades = {}
    cmd = ['pacman', '-S', '-p', '-u', '--print-format', '%n %v']

    if root is not None:
        cmd.extend(('-r', root))

    if refresh:
        cmd.append('-y')

    call = __salt__['cmd.run_all'](cmd,
                                   python_shell=False,
                                   output_loglevel='trace')

    if call['retcode'] != 0:
        comment = ''
        if 'stderr' in call:
            comment += call['stderr']
        if 'stdout' in call:
            comment += call['stdout']
        if comment:
            comment = ': ' + comment
        raise CommandExecutionError('Error listing upgrades' + comment)
    else:
        out = call['stdout']

    for line in salt.utils.itertools.split(out, '\n'):
        comps = line.split(' ')
        if len(comps) != 2:
            continue
        upgrades[comps[0]] = comps[1]
    return upgrades


def version(*names, **kwargs):
    '''
    Returns a string representing the package version or an empty string if not
    installed. If more than one package name is specified, a dict of
    name/version pairs is returned.

    CLI Example:

    .. code-block:: bash

        salt '*' pkg.version <package name>
        salt '*' pkg.version <package1> <package2> <package3> ...
    '''
    return __salt__['pkg_resource.version'](*names, **kwargs)


def list_pkgs(versions_as_list=False, **kwargs):
    '''
    List the packages currently installed as a dict::

        {'<package_name>': '<version>'}

    CLI Example:

    .. code-block:: bash

        salt '*' pkg.list_pkgs
    '''
    versions_as_list = salt.utils.is_true(versions_as_list)
    # not yet implemented or not applicable
    if any([salt.utils.is_true(kwargs.get(x))
            for x in ('removed', 'purge_desired')]):
        return {}

    if 'pkg.list_pkgs' in __context__:
        if versions_as_list:
            return __context__['pkg.list_pkgs']
        else:
            ret = copy.deepcopy(__context__['pkg.list_pkgs'])
            __salt__['pkg_resource.stringify'](ret)
            return ret

    cmd = ['pacman', '-Q']

    if 'root' in kwargs:
        cmd.extend(('-r', kwargs['root']))

    ret = {}
    out = __salt__['cmd.run'](cmd, output_loglevel='trace', python_shell=False)
    for line in salt.utils.itertools.split(out, '\n'):
        if not line:
            continue
        try:
            name, version_num = line.split()[0:2]
        except ValueError:
            log.error('Problem parsing pacman -Q: Unexpected formatting in '
                      'line: \'{0}\''.format(line))
        else:
            __salt__['pkg_resource.add_pkg'](ret, name, version_num)

    __salt__['pkg_resource.sort_pkglist'](ret)
    __context__['pkg.list_pkgs'] = copy.deepcopy(ret)
    if not versions_as_list:
        __salt__['pkg_resource.stringify'](ret)
    return ret


def group_list():
    '''
    .. versionadded:: Carbon

    Lists all groups known by pacman on this system

    CLI Example:

    .. code-block:: bash

        salt '*' pkg.group_list
    '''

    ret = {'installed': [],
        'partially_installed': [],
        'available': []}

    # find out what's available

    cmd = ['pacman', '-Sgg']
    out = __salt__['cmd.run'](cmd, output_loglevel='trace', python_shell=False)

    available = {}

    for line in salt.utils.itertools.split(out, '\n'):
        if not line:
            continue
        try:
            group, pkg = line.split()[0:2]
        except ValueError:
            log.error('Problem parsing pacman -Sgg: Unexpected formatting in '
                      'line: \'{0}\''.format(line))
        else:
            available.setdefault(group, []).append(pkg)

    # now get what's installed

    cmd = ['pacman', '-Qg']
    out = __salt__['cmd.run'](cmd, output_loglevel='trace', python_shell=False)
    installed = {}
    for line in salt.utils.itertools.split(out, '\n'):
        if not line:
            continue
        try:
            group, pkg = line.split()[0:2]
        except ValueError:
            log.error('Problem parsing pacman -Qg: Unexpected formatting in '
                      'line: \'{0}\''.format(line))
        else:
            installed.setdefault(group, []).append(pkg)

    # move installed and partially-installed items from available to appropriate other places

    for group in installed:
        if group not in available:
            log.error('Pacman reports group {0} installed, but it is not in the available list ({1})!'.format(group, available))
            continue
        if len(installed[group]) == len(available[group]):
            ret['installed'].append(group)
        else:
            ret['partially_installed'].append(group)
        available.pop(group)

    ret['installed'].sort()
    ret['partially_installed'].sort()

    # Now installed and partially installed are set, whatever is left is the available list.
    # In Python 3, .keys() returns an iterable view instead of a list. sort() cannot be
    # called on views. Use sorted() instead. Plus it's just as efficient as sort().
    ret['available'] = sorted(available.keys())

    return ret


def group_info(name):
    '''
    .. versionadded:: Carbon

    Lists all packages in the specified group

    CLI Example:

    .. code-block:: bash

        salt '*' pkg.group_info 'xorg'
    '''

    pkgtypes = ('mandatory', 'optional', 'default', 'conditional')
    ret = {}
    for pkgtype in pkgtypes:
        ret[pkgtype] = set()

    cmd = ['pacman', '-Sgg', name]
    out = __salt__['cmd.run'](cmd, output_loglevel='trace', python_shell=False)

    for line in salt.utils.itertools.split(out, '\n'):
        if not line:
            continue
        try:
            pkg = line.split()[1]
        except ValueError:
            log.error('Problem parsing pacman -Sgg: Unexpected formatting in '
                      'line: \'{0}\''.format(line))
        else:
            ret['default'].add(pkg)

    for pkgtype in pkgtypes:
        ret[pkgtype] = sorted(ret[pkgtype])

    return ret


def group_diff(name):

    '''
    .. versionadded:: Carbon

    Lists which of a group's packages are installed and which are not
    installed

    Compatible with yumpkg.group_diff for easy support of state.pkg.group_installed

    CLI Example:

    .. code-block:: bash

        salt '*' pkg.group_diff 'xorg'
    '''

    # Use a compatible structure with yum, so we can leverage the existing state.group_installed
    # In pacmanworld, everything is the default, but nothing is mandatory

    pkgtypes = ('mandatory', 'optional', 'default', 'conditional')
    ret = {}
    for pkgtype in pkgtypes:
        ret[pkgtype] = {'installed': [], 'not installed': []}

    # use indirect references to simplify unit testing
    pkgs = __salt__['pkg.list_pkgs']()
    group_pkgs = __salt__['pkg.group_info'](name)
    for pkgtype in pkgtypes:
        for member in group_pkgs.get(pkgtype, []):
            if member in pkgs:
                ret[pkgtype]['installed'].append(member)
            else:
                ret[pkgtype]['not installed'].append(member)
    return ret


def refresh_db(root=None):
    '''
    Just run a ``pacman -Sy``, return a dict::

        {'<database name>': Bool}

    CLI Example:

    .. code-block:: bash

        salt '*' pkg.refresh_db
    '''
    cmd = ['pacman', '-Sy']

    if root is not None:
        cmd.extend(('-r', root))

    ret = {}
    call = __salt__['cmd.run_all'](cmd,
                                   output_loglevel='trace',
                                   env={'LANG': 'C'},
                                   python_shell=False)
    if call['retcode'] != 0:
        comment = ''
        if 'stderr' in call:
            comment += ': ' + call['stderr']
        raise CommandExecutionError(
            'Error refreshing package database' + comment
        )
    else:
        out = call['stdout']

    for line in salt.utils.itertools.split(out, '\n'):
        if line.strip().startswith('::'):
            continue
        if not line:
            continue
        key = line.strip().split()[0]
        if 'is up to date' in line:
            ret[key] = False
        elif 'downloading' in line:
            key = line.strip().split()[1].split('.')[0]
            ret[key] = True
    return ret


def install(name=None,
            refresh=False,
            sysupgrade=False,
            pkgs=None,
            sources=None,
            **kwargs):
    '''
    .. versionchanged:: 2015.8.12,2016.3.3,Carbon
        On minions running systemd>=205, `systemd-run(1)`_ is now used to
        isolate commands which modify installed packages from the
        ``salt-minion`` daemon's control group. This is done to keep systemd
        from killing any pacman commands spawned by Salt when the
        ``salt-minion`` service is restarted. (see ``KillMode`` in the
        `systemd.kill(5)`_ manpage for more information). If desired, usage of
        `systemd-run(1)`_ can be suppressed by setting a :mod:`config option
        <salt.modules.config.get>` called ``systemd.scope``, with a value of
        ``False`` (no quotes).

    .. _`systemd-run(1)`: https://www.freedesktop.org/software/systemd/man/systemd-run.html
    .. _`systemd.kill(5)`: https://www.freedesktop.org/software/systemd/man/systemd.kill.html

    Install (``pacman -S``) the specified packag(s). Add ``refresh=True`` to
    install with ``-y``, add ``sysupgrade=True`` to install with ``-u``.

    name
        The name of the package to be installed. Note that this parameter is
        ignored if either ``pkgs`` or ``sources`` is passed. Additionally,
        please note that this option can only be used to install packages from
        a software repository. To install a package file manually, use the
        ``sources`` option.

        CLI Example:

        .. code-block:: bash

            salt '*' pkg.install <package name>

    refresh
        Whether or not to refresh the package database before installing.

    sysupgrade
        Whether or not to upgrade the system packages before installing.


    Multiple Package Installation Options:

    pkgs
        A list of packages to install from a software repository. Must be
        passed as a python list. A specific version number can be specified
        by using a single-element dict representing the package and its
        version. As with the ``version`` parameter above, comparison operators
        can be used to target a specific version of a package.

        CLI Examples:

        .. code-block:: bash

            salt '*' pkg.install pkgs='["foo", "bar"]'
            salt '*' pkg.install pkgs='["foo", {"bar": "1.2.3-4"}]'
            salt '*' pkg.install pkgs='["foo", {"bar": "<1.2.3-4"}]'

    sources
        A list of packages to install. Must be passed as a list of dicts,
        with the keys being package names, and the values being the source URI
        or local path to the package.

        CLI Example:

        .. code-block:: bash

            salt '*' pkg.install \
                sources='[{"foo": "salt://foo.pkg.tar.xz"}, \
                {"bar": "salt://bar.pkg.tar.xz"}]'


    Returns a dict containing the new package names and versions::

        {'<package>': {'old': '<old-version>',
                       'new': '<new-version>'}}
    '''
    try:
        pkg_params, pkg_type = __salt__['pkg_resource.parse_targets'](
            name, pkgs, sources, **kwargs
        )
    except MinionError as exc:
        raise CommandExecutionError(exc)

    if pkg_params is None or len(pkg_params) == 0:
        return {}

    version_num = kwargs.get('version')
    if version_num:
        if pkgs is None and sources is None:
            # Allow 'version' to work for single package target
            pkg_params = {name: version_num}
        else:
            log.warning('\'version\' parameter will be ignored for multiple '
                        'package targets')

    if 'root' in kwargs:
        pkg_params['-r'] = kwargs['root']

    cmd = []
    if salt.utils.systemd.has_scope(__context__) \
            and __salt__['config.get']('systemd.scope', True):
        cmd.extend(['systemd-run', '--scope'])
    cmd.append('pacman')

    if pkg_type == 'file':
        cmd.extend(['-U', '--noprogressbar', '--noconfirm'])
        cmd.extend(pkg_params)
    elif pkg_type == 'repository':
        cmd.append('-S')
        if salt.utils.is_true(refresh):
            cmd.append('-y')
        if salt.utils.is_true(sysupgrade):
            cmd.append('-u')
        cmd.extend(['--noprogressbar', '--noconfirm', '--needed'])
        targets = []
        problems = []
        for param, version_num in six.iteritems(pkg_params):
            if version_num is None:
                targets.append(param)
            else:
                match = re.match('^([<>])?(=)?([^<>=]+)$', version_num)
                if match:
                    gt_lt, eq, verstr = match.groups()
                    prefix = gt_lt or ''
                    prefix += eq or ''
                    # If no prefix characters were supplied, use '='
                    prefix = prefix or '='
                    targets.append('{0}{1}{2}'.format(param, prefix, verstr))
                else:
                    msg = ('Invalid version string \'{0}\' for package '
                           '\'{1}\''.format(version_num, name))
                    problems.append(msg)
        if problems:
            for problem in problems:
                log.error(problem)
            return {}

        cmd.extend(targets)

    old = list_pkgs()
    out = __salt__['cmd.run_all'](
        cmd,
        output_loglevel='trace',
        python_shell=False
    )

    if out['retcode'] != 0 and out['stderr']:
        errors = [out['stderr']]
    else:
        errors = []

    __context__.pop('pkg.list_pkgs', None)
    new = list_pkgs()
    ret = salt.utils.compare_dicts(old, new)

    if errors:
        raise CommandExecutionError(
            'Problem encountered installing package(s)',
            info={'errors': errors, 'changes': ret}
        )

    return ret


def upgrade(refresh=False, root=None, **kwargs):
    '''
    .. versionchanged:: 2015.8.12,2016.3.3,Carbon
        On minions running systemd>=205, `systemd-run(1)`_ is now used to
        isolate commands which modify installed packages from the
        ``salt-minion`` daemon's control group. This is done to keep systemd
        from killing any pacman commands spawned by Salt when the
        ``salt-minion`` service is restarted. (see ``KillMode`` in the
        `systemd.kill(5)`_ manpage for more information). If desired, usage of
        `systemd-run(1)`_ can be suppressed by setting a :mod:`config option
        <salt.modules.config.get>` called ``systemd.scope``, with a value of
        ``False`` (no quotes).

    .. _`systemd-run(1)`: https://www.freedesktop.org/software/systemd/man/systemd-run.html
    .. _`systemd.kill(5)`: https://www.freedesktop.org/software/systemd/man/systemd.kill.html

    Run a full system upgrade, a pacman -Syu

    refresh
        Whether or not to refresh the package database before installing.

    Returns a dictionary containing the changes:

    .. code-block:: python

        {'<package>':  {'old': '<old-version>',
                        'new': '<new-version>'}}


    CLI Example:

    .. code-block:: bash

        salt '*' pkg.upgrade
    '''
    ret = {'changes': {},
           'result': True,
           'comment': ''}

    old = list_pkgs()

    cmd = []
    if salt.utils.systemd.has_scope(__context__) \
            and __salt__['config.get']('systemd.scope', True):
        cmd.extend(['systemd-run', '--scope'])
    cmd.extend(['pacman', '-Su', '--noprogressbar', '--noconfirm'])
    if salt.utils.is_true(refresh):
        cmd.append('-y')

    if root is not None:
        cmd.extend(('-r', root))

    result = __salt__['cmd.run_all'](cmd,
                                     output_loglevel='trace',
                                     python_shell=False)
    __context__.pop('pkg.list_pkgs', None)
    new = list_pkgs()
    ret = salt.utils.compare_dicts(old, new)

    if result['retcode'] != 0:
        raise CommandExecutionError(
            'Problem encountered upgrading packages',
            info={'changes': ret, 'result': result}
        )

    return ret


def _uninstall(action='remove', name=None, pkgs=None, **kwargs):
    '''
    remove and purge do identical things but with different pacman commands,
    this function performs the common logic.
    '''
    try:
        pkg_params = __salt__['pkg_resource.parse_targets'](name, pkgs)[0]
    except MinionError as exc:
        raise CommandExecutionError(exc)

    old = list_pkgs()
    targets = [x for x in pkg_params if x in old]
    if not targets:
        return {}

    remove_arg = '-Rsc' if action == 'purge' else '-R'

    cmd = []
    if salt.utils.systemd.has_scope(__context__) \
            and __salt__['config.get']('systemd.scope', True):
        cmd.extend(['systemd-run', '--scope'])
    cmd.extend(['pacman', remove_arg, '--noprogressbar', '--noconfirm'])
    cmd.extend(targets)

    if 'root' in kwargs:
        cmd.extend(('-r', kwargs['root']))

    out = __salt__['cmd.run_all'](
        cmd,
        output_loglevel='trace',
        python_shell=False
    )

    if out['retcode'] != 0 and out['stderr']:
        errors = [out['stderr']]
    else:
        errors = []

    __context__.pop('pkg.list_pkgs', None)
    new = list_pkgs()
    ret = salt.utils.compare_dicts(old, new)

    if errors:
        raise CommandExecutionError(
            'Problem encountered removing package(s)',
            info={'errors': errors, 'changes': ret}
        )

    return ret


def remove(name=None, pkgs=None, **kwargs):
    '''
    .. versionchanged:: 2015.8.12,2016.3.3,Carbon
        On minions running systemd>=205, `systemd-run(1)`_ is now used to
        isolate commands which modify installed packages from the
        ``salt-minion`` daemon's control group. This is done to keep systemd
        from killing any pacman commands spawned by Salt when the
        ``salt-minion`` service is restarted. (see ``KillMode`` in the
        `systemd.kill(5)`_ manpage for more information). If desired, usage of
        `systemd-run(1)`_ can be suppressed by setting a :mod:`config option
        <salt.modules.config.get>` called ``systemd.scope``, with a value of
        ``False`` (no quotes).

    .. _`systemd-run(1)`: https://www.freedesktop.org/software/systemd/man/systemd-run.html
    .. _`systemd.kill(5)`: https://www.freedesktop.org/software/systemd/man/systemd.kill.html

    Remove packages with ``pacman -R``.

    name
        The name of the package to be deleted.


    Multiple Package Options:

    pkgs
        A list of packages to delete. Must be passed as a python list. The
        ``name`` parameter will be ignored if this option is passed.

    .. versionadded:: 0.16.0


    Returns a dict containing the changes.

    CLI Example:

    .. code-block:: bash

        salt '*' pkg.remove <package name>
        salt '*' pkg.remove <package1>,<package2>,<package3>
        salt '*' pkg.remove pkgs='["foo", "bar"]'
    '''
    return _uninstall(action='remove', name=name, pkgs=pkgs)


def purge(name=None, pkgs=None, **kwargs):
    '''
    .. versionchanged:: 2015.8.12,2016.3.3,Carbon
        On minions running systemd>=205, `systemd-run(1)`_ is now used to
        isolate commands which modify installed packages from the
        ``salt-minion`` daemon's control group. This is done to keep systemd
        from killing any pacman commands spawned by Salt when the
        ``salt-minion`` service is restarted. (see ``KillMode`` in the
        `systemd.kill(5)`_ manpage for more information). If desired, usage of
        `systemd-run(1)`_ can be suppressed by setting a :mod:`config option
        <salt.modules.config.get>` called ``systemd.scope``, with a value of
        ``False`` (no quotes).

    .. _`systemd-run(1)`: https://www.freedesktop.org/software/systemd/man/systemd-run.html
    .. _`systemd.kill(5)`: https://www.freedesktop.org/software/systemd/man/systemd.kill.html

    Recursively remove a package and all dependencies which were installed
    with it, this will call a ``pacman -Rsc``

    name
        The name of the package to be deleted.


    Multiple Package Options:

    pkgs
        A list of packages to delete. Must be passed as a python list. The
        ``name`` parameter will be ignored if this option is passed.

    .. versionadded:: 0.16.0


    Returns a dict containing the changes.

    CLI Example:

    .. code-block:: bash

        salt '*' pkg.purge <package name>
        salt '*' pkg.purge <package1>,<package2>,<package3>
        salt '*' pkg.purge pkgs='["foo", "bar"]'
    '''
    return _uninstall(action='purge', name=name, pkgs=pkgs)


def file_list(*packages):
    '''
    List the files that belong to a package. Not specifying any packages will
    return a list of _every_ file on the system's package database (not
    generally recommended).

    CLI Examples:

    .. code-block:: bash

        salt '*' pkg.file_list httpd
        salt '*' pkg.file_list httpd postfix
        salt '*' pkg.file_list
    '''
    errors = []
    ret = []
    cmd = ['pacman', '-Ql']

    if len(packages) > 0 and os.path.exists(packages[0]):
        packages = list(packages)
        cmd.extend(('-r', packages.pop(0)))

    cmd.extend(packages)

    out = __salt__['cmd.run'](cmd, output_loglevel='trace', python_shell=False)
    for line in salt.utils.itertools.split(out, '\n'):
        if line.startswith('error'):
            errors.append(line)
        else:
            comps = line.split()
            ret.append(' '.join(comps[1:]))
    return {'errors': errors, 'files': ret}


def file_dict(*packages):
    '''
    List the files that belong to a package, grouped by package. Not
    specifying any packages will return a list of _every_ file on the system's
    package database (not generally recommended).

    CLI Examples:

    .. code-block:: bash

        salt '*' pkg.file_list httpd
        salt '*' pkg.file_list httpd postfix
        salt '*' pkg.file_list
    '''
    errors = []
    ret = {}
    cmd = ['pacman', '-Ql']

    if len(packages) > 0 and os.path.exists(packages[0]):
        packages = list(packages)
        cmd.extend(('-r', packages.pop(0)))

    cmd.extend(packages)

    out = __salt__['cmd.run'](cmd, output_loglevel='trace', python_shell=False)
    for line in salt.utils.itertools.split(out, '\n'):
        if line.startswith('error'):
            errors.append(line)
        else:
            comps = line.split()
            if not comps[0] in ret:
                ret[comps[0]] = []
            ret[comps[0]].append((' '.join(comps[1:])))
    return {'errors': errors, 'packages': ret}


def owner(*paths):
    '''
    .. versionadded:: 2014.7.0

    Return the name of the package that owns the file. Multiple file paths can
    be passed. Like :mod:`pkg.version <salt.modules.yumpkg.version`, if a
    single path is passed, a string will be returned, and if multiple paths are
    passed, a dictionary of file/package name pairs will be returned.

    If the file is not owned by a package, or is not present on the minion,
    then an empty string will be returned for that path.

    CLI Example:

        salt '*' pkg.owner /usr/bin/apachectl
        salt '*' pkg.owner /usr/bin/apachectl /usr/bin/zsh
    '''
    if not paths:
        return ''
    ret = {}
    cmd_prefix = ['pacman', '-Qqo']

    for path in paths:
        ret[path] = __salt__['cmd.run_stdout'](cmd_prefix + [path],
                                               python_shell=False)
    if len(ret) == 1:
        return next(six.itervalues(ret))
    return ret
