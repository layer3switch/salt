# -*- coding: utf-8 -*-
'''
Homebrew for Mac OS X

.. important::
    If you feel that Salt should be using this module to manage packages on a
    minion, and it is using a different module (or gives an error similar to
    *'pkg.install' is not available*), see :ref:`here
    <module-provider-override>`.
'''
from __future__ import absolute_import

# Import python libs
import copy
import logging

# Import salt libs
import salt.utils
from salt.exceptions import CommandExecutionError, MinionError

# Import third party libs
import json

log = logging.getLogger(__name__)

# Define the module's virtual name
__virtualname__ = 'pkg'


def __virtual__():
    '''
    Confine this module to Mac OS with Homebrew.
    '''

    if salt.utils.which('brew') and __grains__['os'] == 'MacOS':
        return __virtualname__
    return (False, 'The brew module could not be loaded: brew not found or grain os != MacOS')


def _list_taps():
    '''
    List currently installed brew taps
    '''
    cmd = 'brew tap'
    return _call_brew(cmd)['stdout'].splitlines()


def _tap(tap, runas=None):
    '''
    Add unofficial GitHub repos to the list of formulas that brew tracks,
    updates, and installs from.
    '''
    if tap in _list_taps():
        return True

    cmd = 'brew tap {0}'.format(tap)
    try:
        _call_brew(cmd)
    except CommandExecutionError:
        log.error('Failed to tap "{0}"'.format(tap))
        return False

    return True


def _homebrew_bin():
    '''
    Returns the full path to the homebrew binary in the PATH
    '''
    ret = __salt__['cmd.run']('brew --prefix', output_loglevel='trace')
    ret += '/bin/brew'
    return ret


def _call_brew(cmd, redirect_stderr=False):
    '''
    Calls the brew command with the user account of brew
    '''
    user = __salt__['file.get_user'](_homebrew_bin())
    runas = user if user != __opts__['user'] else None
    ret = __salt__['cmd.run_all'](cmd,
                                  runas=runas,
                                  output_loglevel='trace',
                                  python_shell=False,
                                  redirect_stderr=redirect_stderr)
    if ret['retcode'] != 0:
        raise CommandExecutionError(
            'stdout: {stdout}\n'
            'stderr: {stderr}\n'
            'retcode: {retcode}\n'.format(**ret)
        )
    return ret


def list_pkgs(versions_as_list=False, **kwargs):
    '''
    List the packages currently installed in a dict::

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

    cmd = 'brew list --versions'
    ret = {}
    out = _call_brew(cmd)['stdout']
    for line in out.splitlines():
        try:
            name_and_versions = line.split(' ')
            name = name_and_versions[0]
            installed_versions = name_and_versions[1:]
            newest_version = sorted(installed_versions, cmp=salt.utils.version_cmp).pop()
        except ValueError:
            continue
        __salt__['pkg_resource.add_pkg'](ret, name, newest_version)

    __salt__['pkg_resource.sort_pkglist'](ret)
    __context__['pkg.list_pkgs'] = copy.deepcopy(ret)
    if not versions_as_list:
        __salt__['pkg_resource.stringify'](ret)
    return ret


def version(*names, **kwargs):
    '''
    Returns a string representing the package version or an empty string if not
    installed. If more than one package name is specified, a dict of
    name/version pairs is returned.

    CLI Example:

    .. code-block:: bash

        salt '*' pkg.version <package name>
        salt '*' pkg.version <package1> <package2> <package3>
    '''
    return __salt__['pkg_resource.version'](*names, **kwargs)


def latest_version(*names, **kwargs):
    '''
    Return the latest version of the named package available for upgrade or
    installation

    CLI Example:

    .. code-block:: bash

        salt '*' pkg.latest_version <package name>
        salt '*' pkg.latest_version <package1> <package2> <package3>
    '''
    refresh = salt.utils.is_true(kwargs.pop('refresh', True))
    if refresh:
        refresh_db()

    # Get dictionaries of installed and upgradeable packages
    installed = list_pkgs()
    upgrade = list_upgrades()

    if len(names) == 0:
        return ''
    ret = {}

    for name in names:
        if name in installed:
            if name in upgrade:
                ret[name] = upgrade[name]
            else:
                ret[name] = ''
        else:
            pkg_info = _info(name)

            # brew does not include the revision in the version string for
            # uninstalled packages, but it does for installed packages, so
            # append it here so that the pkg.uptodate function works
            version = pkg_info[name]['versions']['stable']
            revision = pkg_info[name]['revision']
            if revision > 0:
                version += '_{0}'.format(revision)
            ret[name] = version

    # Return a string if only one package name passed
    if len(names) == 1:
        return ret[names[0]]
    return ret

# available_version is being deprecated
available_version = salt.utils.alias_function(latest_version, 'available_version')


def remove(name=None, pkgs=None, **kwargs):
    '''
    Removes packages with ``brew uninstall``.

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
    try:
        pkg_params = __salt__['pkg_resource.parse_targets'](
            name, pkgs, **kwargs
        )[0]
    except MinionError as exc:
        raise CommandExecutionError(exc)

    old = list_pkgs()
    targets = [x for x in pkg_params if x in old]
    if not targets:
        return {}
    cmd = 'brew uninstall {0}'.format(' '.join(targets))

    out = _call_brew(cmd)
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


def refresh_db():
    '''
    Update the homebrew package repository.

    CLI Example:

    .. code-block:: bash

        salt '*' pkg.refresh_db
    '''
    cmd = 'brew update'
    if _call_brew(cmd)['retcode']:
        log.error('Failed to update')
        return False

    return True


def install(name=None, pkgs=None, taps=None, options=None, **kwargs):
    '''
    Install the passed package(s) with ``brew install``

    name
        The name of the formula to be installed. Note that this parameter is
        ignored if "pkgs" is passed.

        CLI Example:

        .. code-block:: bash

            salt '*' pkg.install <package name>

    taps
        Unofficial GitHub repos to use when updating and installing formulas.

        CLI Example:

        .. code-block:: bash

            salt '*' pkg.install <package name> tap='<tap>'
            salt '*' pkg.install zlib taps='homebrew/dupes'
            salt '*' pkg.install php54 taps='["josegonzalez/php", "homebrew/dupes"]'

    options
        Options to pass to brew. Only applies to initial install. Due to how brew
        works, modifying chosen options requires a full uninstall followed by a
        fresh install. Note that if "pkgs" is used, all options will be passed
        to all packages. Unrecognized options for a package will be silently
        ignored by brew.

        CLI Example:

        .. code-block:: bash

            salt '*' pkg.install <package name> tap='<tap>'
            salt '*' pkg.install php54 taps='["josegonzalez/php", "homebrew/dupes"]' options='["--with-fpm"]'

    Multiple Package Installation Options:

    pkgs
        A list of formulas to install. Must be passed as a python list.

        CLI Example:

        .. code-block:: bash

            salt '*' pkg.install pkgs='["foo","bar"]'


    Returns a dict containing the new package names and versions::

        {'<package>': {'old': '<old-version>',
                       'new': '<new-version>'}}

    CLI Example:

    .. code-block:: bash

        salt '*' pkg.install 'package package package'
    '''
    try:
        pkg_params, pkg_type = __salt__['pkg_resource.parse_targets'](
            name, pkgs, kwargs.get('sources', {})
        )
    except MinionError as exc:
        raise CommandExecutionError(exc)

    if pkg_params is None or len(pkg_params) == 0:
        return {}

    formulas = ' '.join(pkg_params)
    old = list_pkgs()

    # Ensure we've tapped the repo if necessary
    if taps:
        if not isinstance(taps, list):
            # Feels like there is a better way to allow for tap being
            # specified as both a string and a list
            taps = [taps]

        for tap in taps:
            _tap(tap)

    if options:
        cmd = 'brew install {0} {1}'.format(formulas, ' '.join(options))
    else:
        cmd = 'brew install {0}'.format(formulas)

    out = _call_brew(cmd)
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


def list_upgrades(refresh=True):
    '''
    Check whether or not an upgrade is available for all packages

    CLI Example:

    .. code-block:: bash

        salt '*' pkg.list_upgrades
    '''
    if refresh:
        refresh_db()

    res = _call_brew(['brew', 'outdated', '--json=v1'])
    ret = {}

    try:
        data = json.loads(res['stdout'])
    except ValueError as err:
        msg = 'unable to interpret output from "brew outdated": {0}'.format(err)
        log.error(msg)
        raise CommandExecutionError(msg)

    for pkg in data:
        # current means latest available to brew
        ret[pkg['name']] = pkg['current_version']
    return ret


def upgrade_available(pkg):
    '''
    Check whether or not an upgrade is available for a given package

    CLI Example:

    .. code-block:: bash

        salt '*' pkg.upgrade_available <package name>
    '''
    return pkg in list_upgrades()


def upgrade(refresh=True):
    '''
    Upgrade outdated, unpinned brews.

    refresh
        Fetch the newest version of Homebrew and all formulae from GitHub before installing.

    Return a dict containing the new package names and versions::

        {'<package>': {'old': '<old-version>',
                       'new': '<new-version>'}}

    CLI Example:

    .. code-block:: bash

        salt '*' pkg.upgrade
    '''
    ret = {'changes': {},
           'result': True,
           'comment': '',
           }

    old = list_pkgs()

    if salt.utils.is_true(refresh):
        refresh_db()

    cmd = 'brew upgrade'
    call = _call_brew(cmd, redirect_stderr=True)

    if call['retcode'] != 0:
        ret['result'] = False
        if call['stdout']:
            ret['comment'] = call['stdout']

    __context__.pop('pkg.list_pkgs', None)
    new = list_pkgs()
    ret['changes'] = salt.utils.compare_dicts(old, new)

    return ret


def _info(*names):
    '''
    Return the information of the named package(s)

    .. versionadded:: 2016.3.1

    names
        The names of the packages for which to return information.
    '''
    cmd = ['brew', 'info', '--json=v1']
    cmd.extend(names)
    res = _call_brew(cmd)
    ret = {}

    try:
        data = json.loads(res['stdout'])
    except ValueError as err:
        msg = 'unable to interpret output from "brew info": {0}'.format(err)
        log.error(msg)
        raise CommandExecutionError(msg)

    for pkg in data:
        ret[pkg['name']] = pkg

    return ret


def info_installed(*names):
    '''
    Return the information of the named package(s) installed on the system.

    .. versionadded:: 2016.3.1

    names
        The names of the packages for which to return information.

    CLI example:

    .. code-block:: bash

        salt '*' pkg.info_installed <package1>
        salt '*' pkg.info_installed <package1> <package2> <package3> ...
    '''
    return _info(*names)
