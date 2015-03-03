# -*- coding: utf-8 -*-
'''
Manage nspawn containers

.. versionadded:: Beryllium

`systemd-nspawn(1)`__ is a tool used to manage lightweight namespace
containers. This execution module provides several functions to help manage
these containers.

.. __: http://www.freedesktop.org/software/systemd/man/systemd-nspawn.html

Container root directories will live under /var/lib/container.

.. note:

    ``nsenter(1)`` is required to run commands within containers. It should
    already be present on any systemd host, as part of the **util-linux**
    package.
'''
# Import python libs
import errno
import fnmatch
import logging
import os
import re
import shutil

# Import Salt libs
import salt.defaults.exitcodes
import salt.ext.six as six
import salt.utils
import salt.utils.systemd
from salt.exceptions import CommandExecutionError, SaltInvocationError

log = logging.getLogger(__name__)

__func_alias__ = {
    'list_': 'list',
}
__virtualname__ = 'nspawn'
WANT = '/etc/systemd/system/multi-user.target.wants/systemd-nspawn@{0}.service'
PATH = 'PATH=/bin:/usr/bin:/sbin:/usr/sbin:/opt/bin:' \
       '/usr/local/bin:/usr/local/sbin'


def __virtual__():
    '''
    Only work on systems that have been booted with systemd
    '''
    if __grains__['kernel'] == 'Linux' \
            and salt.utils.systemd.booted(__context__):
        if salt.utils.systemd.version() is None:
            log.error('nspawn: Unable to determine systemd version')
        else:
            return __virtualname__
    return False


def _sd_version():
    '''
    Returns __context__.get('systemd.version', 0), avoiding duplication of the
    call to dict.get and making it easier to change how we handle this context
    var in the future
    '''
    return salt.utils.systemd.version(__context__)


def _root(name='', all_roots=False):
    '''
    Return the container root directory. Starting with systemd 219, new
    images go into /var/lib/machines.
    '''
    if _sd_version() >= 219:
        if all_roots:
            return [os.path.join(x, name)
                    for x in ('/var/lib/machines', '/var/lib/container')]
        else:
            return os.path.join('/var/lib/machines', name)
    else:
        ret = os.path.join('/var/lib/container', name)
        if all_roots:
            return [ret]
        else:
            return ret


def _make_container_root(name):
    '''
    Make the container root directory
    '''
    path = _root(name)
    if os.path.exists(path):
        __context__['retcode'] = salt.defaults.exitcodes.SALT_BUILD_FAIL
        raise CommandExecutionError(
            'Container {0} already exists'.format(name)
        )
    else:
        try:
            os.makedirs(path)
            return path
        except OSError as exc:
            raise CommandExecutionError(
                'Unable to make container root directory {0}: {1}'
                .format(name, exc)
            )


def _build_failed(dst, name):
    try:
        __context__['retcode'] = salt.defaults.exitcodes.SALT_BUILD_FAIL
        shutil.rmtree(dst)
    except OSError as exc:
        if exc.errno != errno.ENOENT:
            raise CommandExecutionError(
                'Unable to cleanup container root dir {0}'.format(dst)
            )
    raise CommandExecutionError(
        'Container {0} failed to build'.format(name)
    )


def _bootstrap_arch(name, **kwargs):
    '''
    Bootstrap an Arch Linux container
    '''
    if not salt.utils.which('pacstrap'):
        raise CommandExecutionError(
            'pacstrap not found, is the arch-install-scripts package '
            'installed?'
        )
    dst = _make_container_root(name)
    cmd = 'pacstrap -c -d {0} base'.format(dst)
    ret = __salt__['cmd.run_all'](cmd, python_shell=False)
    if ret['retcode'] != 0:
        _build_failed(dst, name)
    return ret


def _bootstrap_debian(name, **kwargs):
    '''
    Bootstrap a Debian Linux container (only unstable is currently supported)
    '''
    dst = _make_container_root(name)
    cmd = 'debootstrap --arch=amd64 unstable {0}'.format(dst)
    ret = __salt__['cmd.run_all'](cmd, python_shell=False)
    if ret['retcode'] != 0:
        _build_failed(dst, name)
    return ret


def _bootstrap_fedora(name, **kwargs):
    '''
    Bootstrap a Fedora container
    '''
    dst = _make_container_root(name)
    if not kwargs.get('version', False):
        if __grains__['os'].lower() == 'fedora':
            version = __grains__['osrelease']
        else:
            version = '21'
    else:
        version = '21'
    cmd = ('yum -y --releasever={0} --nogpg --installroot={1} '
           '--disablerepo="*" --enablerepo=fedora install systemd passwd yum '
           'fedora-release vim-minimal'.format(version, dst))
    ret = __salt__['cmd.run_all'](cmd, python_shell=False)
    if ret['retcode'] != 0:
        _build_failed(dst, name)
    return ret


def _clear_context():
    '''
    Clear any lxc variables set in __context__
    '''
    for var in [x for x in __context__ if x.startswith('nspawn.')]:
        log.trace('Clearing __context__[\'{0}\']'.format(var))
        __context__.pop(var, None)


def _ensure_running(name):
    '''
    Raise an exception if the container does not exist
    '''
    if state(name) != 'running':
        raise CommandExecutionError(
            'Container \'{0}\' is stopped'.format(name)
        )


def _ensure_exists(name):
    '''
    Raise an exception if the container does not exist
    '''
    contextkey = 'nspawn.exists.{0}'.format(name)
    if contextkey in __context__:
        # No need to return a value, this function is only here to raise an
        # exception if the container doesn't exist, and just dropping a key
        # into __context__ and returning early here will keep us from checking
        # if the container exists multiple times.
        return
    if exists(name):
        __context__[contextkey] = True
    else:
        raise CommandExecutionError(
            'Container \'{0}\' does not exist'.format(name)
        )


def _ensure_systemd(version):
    '''
    Raises an exception if the systemd version is not greater than the
    passed version.
    '''
    try:
        version = int(version)
    except ValueError:
        raise CommandExecutionError('Invalid version \'{0}\''.format(version))

    try:
        installed = _sd_version()
        log.debug('nspawn: detected systemd {0}'.format(installed))
    except (IndexError, ValueError):
        raise CommandExecutionError('nspawn: Unable to get systemd version')

    if installed < version:
        raise CommandExecutionError(
            'This function requires systemd >= {0} '
            '(Detected version: {1}).'.format(version, installed)
        )


def _machinectl(cmd, output_loglevel='debug', use_vt=False):
    '''
    Helper function to run machinectl
    '''
    prefix = 'machinectl --no-legend --no-pager'
    return __salt__['cmd.run_all']('{0} {1}'.format(prefix, cmd),
                                   output_loglevel=output_loglevel,
                                   use_vt=use_vt)


def _pid(name):
    '''
    Return container pid
    '''
    try:
        return int(info(name).get('PID'))
    except (TypeError, ValueError) as exc:
        raise CommandExecutionError(
            'Unable to get PID for container \'{0}\': {1}'.format(name, exc)
        )


def _nsenter(name):
    '''
    Return the nsenter command to attach to the named container
    '''
    return (
        'nsenter --target {0} --mount --uts --ipc --net --pid'
        .format(_pid(name))
    )


def _run(name,
         cmd,
         output=None,
         no_start=False,
         stdin=None,
         python_shell=True,
         preserve_state=False,
         output_loglevel='debug',
         ignore_retcode=False,
         use_vt=False,
         keep_env=None):
    '''
    Common logic for nspawn.run functions
    '''
    # No need to call _ensure_exists(), it will be called via _nsenter()
    full_cmd = _nsenter(name)
    if keep_env is not True:
        full_cmd += ' env -i'
    if keep_env is None:
        full_cmd += ' {0}'.format(PATH)
    elif isinstance(keep_env, six.string_types):
        for var in keep_env.split(','):
            if var in os.environ:
                full_cmd += ' {0}="{1}"'.format(var, os.environ[var])
    full_cmd += ' {0}'.format(cmd)

    orig_state = state(name)
    exc = None
    try:
        ret = __salt__['container_resource.run'](
            name,
            full_cmd,
            output=output,
            no_start=no_start,
            stdin=stdin,
            python_shell=python_shell,
            output_loglevel=output_loglevel,
            ignore_retcode=ignore_retcode,
            use_vt=use_vt)
    except Exception as exc:
        raise
    finally:
        # Make sure we stop the container if necessary, even if an exception
        # was raised.
        if preserve_state \
                and orig_state == 'stopped' \
                and state(name) != 'stopped':
            stop(name)

    if output in (None, 'all'):
        return ret
    else:
        return ret[output]


def _invalid_kwargs(*args, **kwargs):
    '''
    Raise an exception on bad kwarg input
    '''
    raise SaltInvocationError(
        'The following invalid keyword arguments were passed: {0}'
        .format(', '.join(['{0}={1}'.format(x, kwargs[x])
                            for x in args]))
    )


def run(name,
        cmd,
        no_start=False,
        preserve_state=True,
        stdin=None,
        python_shell=True,
        output_loglevel='debug',
        use_vt=False,
        ignore_retcode=False,
        keep_env=None):
    '''
    Run :mod:`cmd.run <salt.modules.cmdmod.run>` within a container

    name
        Name of the container in which to run the command

    cmd
        Command to run

    no_start : False
        If the container is not running, don't start it

    preserve_state : True
        After running the command, return the container to its previous state

    stdin : None
        Standard input to be used for the command

    output_loglevel : debug
        Level at which to log the output from the command. Set to ``quiet`` to
        suppress logging.

    use_vt : False
        Use SaltStack's utils.vt to stream output to console. Assumes
        ``output=all``.

    keep_env : None
        If not passed, only a sane default PATH environment variable will be
        set. If ``True``, all environment variables from the container's host
        will be kept. Otherwise, a comma-separated list (or Python list) of
        environment variable names can be passed, and those environment
        variables will be kept.


    CLI Example:

    .. code-block:: bash

        salt myminion nspawn.run mycontainer 'ifconfig -a'
    '''
    return _run(name,
                cmd,
                output=None,
                no_start=no_start,
                preserve_state=preserve_state,
                stdin=stdin,
                python_shell=python_shell,
                output_loglevel=output_loglevel,
                use_vt=use_vt,
                ignore_retcode=ignore_retcode,
                keep_env=keep_env)


def run_stdout(name,
               cmd,
               no_start=False,
               preserve_state=True,
               stdin=None,
               python_shell=True,
               output_loglevel='debug',
               use_vt=False,
               ignore_retcode=False,
               keep_env=None):
    '''
    Run :mod:`cmd.run_stdout <salt.modules.cmdmod.run_stdout>` within a container

    name
        Name of the container in which to run the command

    cmd
        Command to run

    no_start : False
        If the container is not running, don't start it

    preserve_state : True
        After running the command, return the container to its previous state

    stdin : None
        Standard input to be used for the command

    output_loglevel : debug
        Level at which to log the output from the command. Set to ``quiet`` to
        suppress logging.

    use_vt : False
        Use SaltStack's utils.vt to stream output to console. Assumes
        ``output=all``.

    keep_env : None
        If not passed, only a sane default PATH environment variable will be
        set. If ``True``, all environment variables from the container's host
        will be kept. Otherwise, a comma-separated list (or Python list) of
        environment variable names can be passed, and those environment
        variables will be kept.


    CLI Example:

    .. code-block:: bash

        salt myminion nspawn.run_stdout mycontainer 'ifconfig -a'
    '''
    return _run(name,
                cmd,
                output='stdout',
                no_start=no_start,
                preserve_state=preserve_state,
                stdin=stdin,
                python_shell=python_shell,
                output_loglevel=output_loglevel,
                use_vt=use_vt,
                ignore_retcode=ignore_retcode,
                keep_env=keep_env)


def run_stderr(name,
               cmd,
               no_start=False,
               preserve_state=True,
               stdin=None,
               python_shell=True,
               output_loglevel='debug',
               use_vt=False,
               ignore_retcode=False,
               keep_env=None):
    '''
    Run :mod:`cmd.run_stderr <salt.modules.cmdmod.run_stderr>` within a container

    name
        Name of the container in which to run the command

    cmd
        Command to run

    no_start : False
        If the container is not running, don't start it

    preserve_state : True
        After running the command, return the container to its previous state

    stdin : None
        Standard input to be used for the command

    output_loglevel : debug
        Level at which to log the output from the command. Set to ``quiet`` to
        suppress logging.

    use_vt : False
        Use SaltStack's utils.vt to stream output to console. Assumes
        ``output=all``.

    keep_env : None
        If not passed, only a sane default PATH environment variable will be
        set. If ``True``, all environment variables from the container's host
        will be kept. Otherwise, a comma-separated list (or Python list) of
        environment variable names can be passed, and those environment
        variables will be kept.


    CLI Example:

    .. code-block:: bash

        salt myminion nspawn.run_stderr mycontainer 'ip addr show'
    '''
    return _run(name,
                cmd,
                output='stderr',
                no_start=no_start,
                preserve_state=preserve_state,
                stdin=stdin,
                python_shell=python_shell,
                output_loglevel=output_loglevel,
                use_vt=use_vt,
                ignore_retcode=ignore_retcode,
                keep_env=keep_env)


def retcode(name,
            cmd,
            no_start=False,
            preserve_state=True,
            stdin=None,
            python_shell=True,
            output_loglevel='debug',
            use_vt=False,
            ignore_retcode=False,
            keep_env=None):
    '''
    Run :mod:`cmd.retcode <salt.modules.cmdmod.retcode>` within a container

    name
        Name of the container in which to run the command

    cmd
        Command to run

    no_start : False
        If the container is not running, don't start it

    preserve_state : True
        After running the command, return the container to its previous state

    stdin : None
        Standard input to be used for the command

    output_loglevel : debug
        Level at which to log the output from the command. Set to ``quiet`` to
        suppress logging.

    use_vt : False
        Use SaltStack's utils.vt to stream output to console. Assumes
        ``output=all``.

    keep_env : None
        If not passed, only a sane default PATH environment variable will be
        set. If ``True``, all environment variables from the container's host
        will be kept. Otherwise, a comma-separated list (or Python list) of
        environment variable names can be passed, and those environment
        variables will be kept.


    CLI Example:

    .. code-block:: bash

        salt myminion nspawn.retcode mycontainer 'ip addr show'
    '''
    return _run(name,
                cmd,
                output='retcode',
                no_start=no_start,
                preserve_state=preserve_state,
                stdin=stdin,
                python_shell=python_shell,
                output_loglevel=output_loglevel,
                use_vt=use_vt,
                ignore_retcode=ignore_retcode,
                keep_env=keep_env)


def run_all(name,
            cmd,
            no_start=False,
            preserve_state=True,
            stdin=None,
            python_shell=True,
            output_loglevel='debug',
            use_vt=False,
            ignore_retcode=False,
            keep_env=None):
    '''
    Run :mod:`cmd.run_all <salt.modules.cmdmod.run_all>` within a container

    name
        Name of the container in which to run the command

    cmd
        Command to run

    no_start : False
        If the container is not running, don't start it

    preserve_state : True
        After running the command, return the container to its previous state

    stdin : None
        Standard input to be used for the command

    output_loglevel : debug
        Level at which to log the output from the command. Set to ``quiet`` to
        suppress logging.

    use_vt : False
        Use SaltStack's utils.vt to stream output to console. Assumes
        ``output=all``.

    keep_env : None
        If not passed, only a sane default PATH environment variable will be
        set. If ``True``, all environment variables from the container's host
        will be kept. Otherwise, a comma-separated list (or Python list) of
        environment variable names can be passed, and those environment
        variables will be kept.


    CLI Example:

    .. code-block:: bash

        salt myminion nspawn.run_all mycontainer 'ip addr show'
    '''
    return _run(name,
                cmd,
                output='all',
                no_start=no_start,
                preserve_state=preserve_state,
                stdin=stdin,
                python_shell=python_shell,
                output_loglevel=output_loglevel,
                use_vt=use_vt,
                ignore_retcode=ignore_retcode,
                keep_env=keep_env)


def bootstrap_container(name, dist=None, version=None):
    '''
    Bootstrap a container from package servers, if dist is None the os the
    minion is running as will be created, otherwise the needed bootstrapping
    tools will need to be available on the host.

    CLI Example::

        salt myminion nspawn.bootstrap_container <name>
    '''
    if not dist:
        dist = __grains__['os'].lower()
        log.debug(
            'nspawn.bootstrap: no dist provided, defaulting to \'{0}\''
            .format(dist)
        )
    return globals()['_bootstrap_{0}'.format(dist)](name, version=version)


def list_all():
    '''
    Lists all nspawn containers

    CLI Example:

    .. code-block:: bash

        salt myminion nspawn.list_all
    '''
    ret = []
    if _sd_version() >= 219:
        for line in _machinectl('list-images')['stdout'].splitlines():
            try:
                ret.append(line.split()[0])
            except IndexError:
                continue
    else:
        rootdir = _root()
        try:
            for dirname in os.listdir(rootdir):
                if os.path.isdir(os.path.join(rootdir, dirname)):
                    ret.append(dirname)
        except OSError:
            pass
    return ret


def list_running():
    '''
    Lists running nspawn containers

    .. note::

        ``nspawn.list`` also works to list running containers

    CLI Example:

    .. code-block:: bash

        salt myminion nspawn.list_running
        salt myminion nspawn.list
    '''
    ret = []
    for line in _machinectl('list')['stdout'].splitlines():
        try:
            ret.append(line.split()[0])
        except IndexError:
            pass
    return sorted(ret)

# 'machinectl list' shows only running containers, so allow this to work as an
# alias to nspawn.list_running
list_ = list_running


def list_stopped():
    '''
    Lists stopped nspawn containers

    CLI Example:

    .. code-block:: bash

        salt myminion nspawn.list_stopped
    '''
    return sorted(set(list_all()) - set(list_running()))


def exists(name):
    '''
    Returns true if the named container exists
    '''
    return name in list_all()


def _get_state(name):
    try:
        cmd = 'show {0} --property=State'.format(name)
        return _machinectl(cmd)['stdout'].split('=')[1]
    except IndexError:
        return 'stopped'


def state(name):
    '''
    Return state of container
    '''
    _ensure_exists(name)
    return _get_state(name)


def info(name, **kwargs):
    '''
    Return info about a container

    .. note::

        The container must be running for ``machinectl`` to gather information
        about it. If the container is stopped, then this function will start
        it.

    start : False
        If ``True``, then the container will be started to retrieve the info. A
        ``Started`` key will be in the return data if the container was
        started.

    CLI Example:

    .. code-block:: bash

        salt myminion nspawn.info arch1
        salt myminion nspawn.info arch1 force_start=False
    '''
    # Use kwargs to
    start_ = kwargs.pop('start', False)
    bad_kwargs = [x for x in kwargs if not x.startswith('__')]
    if bad_kwargs:
        _invalid_kwargs(*bad_kwargs, **kwargs)

    if not start_:
        _ensure_running(name)
    elif name not in list_running():
        start(name)

    # Have to parse 'machinectl status' here since 'machinectl show' doesn't
    # contain IP address info or OS info. *shakes fist angrily*
    c_info = _machinectl('status {0}'.format(name))
    if c_info['retcode'] != 0:
        raise CommandExecutionError(
            'Unable to get info for container \'{0}\''.format(name)
        )
    # Better human-readable names. False means key should be ignored.
    key_name_map = {
        'Iface': 'Network Interface',
        'Leader': 'PID',
        'Service': False,
        'Since': 'Running Since',
    }
    ret = {}
    kv_pair = re.compile(r'^\s+([A-Za-z]+): (.+)$')
    tree = re.compile(r'[|`]')
    lines = c_info['stdout'].splitlines()
    multiline = False
    cur_key = None
    for idx in range(len(lines)):
        match = kv_pair.match(lines[idx])
        if match:
            key, val = match.groups()
            # Get a better key name if one exists
            key = key_name_map.get(key, key)
            if key is False:
                continue
            elif key == 'PID':
                try:
                    val = val.split()[0]
                except IndexError:
                    pass
            cur_key = key
            if multiline:
                multiline = False
            ret[key] = val
        else:
            if cur_key is None:
                continue
            if tree.search(lines[idx]):
                # We've reached the process tree, bail out
                break
            if multiline:
                ret[cur_key].append(lines[idx].strip())
            else:
                ret[cur_key] = [ret[key], lines[idx].strip()]
                multiline = True
    return ret


def enable(name):
    '''
    Set the named container to be launched at boot

    CLI Example:

    .. code-block:: bash

        salt myminion nspawn.enable <name>
    '''
    _ensure_exists(name)
    cmd = 'systemctl enable systemd-nspawn@{0}'.format(name)
    if __salt__['cmd.retcode'](cmd, python_shell=False) != 0:
        __context__['retcode'] = salt.defaults.exitcodes.EX_UNAVAILABLE
        return False
    return True


def disable(name):
    '''
    Set the named container to *not* be launched at boot

    CLI Example:

    .. code-block:: bash

        salt myminion nspawn.enable <name>
    '''
    _ensure_exists(name)
    cmd = 'systemctl disable systemd-nspawn@{0}'.format(name)
    if __salt__['cmd.retcode'](cmd, python_shell=False) != 0:
        __context__['retcode'] = salt.defaults.exitcodes.EX_UNAVAILABLE
        return False
    return True


def start(name):
    '''
    Start the named container

    CLI Example::

        salt myminion nspawn.start <name>
    '''
    _ensure_exists(name)
    if _sd_version() >= 219:
        ret = _machinectl('start {0}'.format(name))
    else:
        cmd = 'systemctl start systemd-nspawn@{0}'.format(name)
        ret = __salt__['cmd.run_all'](cmd, python_shell=False)

    if ret['retcode'] != 0:
        __context__['retcode'] = salt.defaults.exitcodes.EX_UNAVAILABLE
        return False
    return True


# This function is hidden from sphinx docs
def stop(name, kill=False):
    '''
    This is a compatibility function which provides the logic for
    nspawn.poweroff and nspawn.terminate.
    '''
    _ensure_exists(name)
    if _sd_version() >= 219:
        if kill:
            action = 'terminate'
        else:
            action = 'poweroff'
        ret = _machinectl('{0} {1}'.format(action, name))
    else:
        cmd = 'systemctl stop systemd-nspawn@{0}'.format(name)
        ret = __salt__['cmd.run_all'](cmd, python_shell=False)

    if ret['retcode'] != 0:
        __context__['retcode'] = salt.defaults.exitcodes.EX_UNAVAILABLE
        return False
    return True


def poweroff(name):
    '''
    Issue a clean shutdown to the container.  Equivalent to running
    ``machinectl poweroff`` on the named container.

    For convenience, running ``nspawn.stop``(as shown in the CLI examples
    below) is equivalent to running ``nspawn.poweroff``.

    .. note::

        ``machinectl poweroff`` is only supported in systemd >= 219. On earlier
        systemd versions, running this function will simply issue a clean
        shutdown via ``systemctl``.

    CLI Examples:

    .. code-block:: bash

        salt myminion nspawn.poweroff arch1
        salt myminion nspawn.stop arch1
    '''
    return stop(name, kill=False)


def terminate(name):
    '''
    Kill all processes in the container without issuing a clean shutdown.
    Equivalent to running ``machinectl terminate`` on the named container.

    For convenience, running ``nspawn.stop`` and passing ``kill=True`` (as
    shown in the CLI examples below) is equivalent to running
    ``nspawn.terminate``.

    .. note::

        ``machinectl terminate`` is only supported in systemd >= 219. On
        earlier systemd versions, running this function will simply issue a
        clean shutdown via ``systemctl``.

    CLI Examples:

    .. code-block:: bash

        salt myminion nspawn.terminate arch1
        salt myminion nspawn.stop arch1 kill=True
    '''
    return stop(name, kill=True)


# This function is hidden from sphinx docs
def restart(name):
    '''
    This is a compatibility function which simply calls nspawn.reboot.
    '''
    return reboot(name)


def reboot(name, kill=False):
    '''
    Reboot the container by sending a SIGINT to its init process. Equivalent
    to running ``machinectl reboot`` on the named container.

    For convenience, running ``nspawn.restart`` (as shown in the CLI examples
    below) is equivalent to running ``nspawn.reboot``.

    .. note::

        ``machinectl reboot`` is only supported in systemd >= 219. On earlier
        systemd versions, running this function will instead restart the
        container via ``systemctl``.

    CLI Examples:

    .. code-block:: bash

        salt myminion nspawn.reboot arch1
        salt myminion nspawn.restart arch1
    '''
    _ensure_exists(name)
    if _sd_version() >= 219:
        if state(name) == 'running':
            ret = _machinectl('reboot {0}'.format(name))
        else:
            # 'machinectl reboot' will fail on a stopped container
            return start(name)
    else:
        # 'systemctl restart' did not work, at least in my testing. Running
        # 'uptime' in the container afterwards showed it had not rebooted. So,
        # we need stop and start the container in separate actions.

        # First stop the container
        cmd = 'systemctl stop systemd-nspawn@{0}'.format(name)
        ret = __salt__['cmd.run_all'](cmd, python_shell=False)
        # Now check if successful
        if ret['retcode'] != 0:
            __context__['retcode'] = salt.defaults.exitcodes.EX_UNAVAILABLE
            return False
        # Finally, start the container back up. No need to check the retcode a
        # second time, it'll be checked below once we exit the if/else block.
        cmd = 'systemctl start systemd-nspawn@{0}'.format(name)
        ret = __salt__['cmd.run_all'](cmd, python_shell=False)

    if ret['retcode'] != 0:
        __context__['retcode'] = salt.defaults.exitcodes.EX_UNAVAILABLE
        return False
    return True


# Everything below requres systemd >= 219
# TODO: Write a decorator to keep these functions from being available to older
#       systemd versions.
def _pull_image(pull_type, image, name, **kwargs):
    '''
    Common logic for machinectl pull-* commands
    '''
    _ensure_systemd(219)
    if exists(name):
        raise SaltInvocationError(
            'Container \'{0}\' already exists'.format(name)
        )
    if pull_type in ('raw', 'tar'):
        valid_kwargs = ('verify',)
    elif pull_type == 'dkr':
        valid_kwargs = 'index'
    else:
        raise SaltInvocationError(
            'Unsupported image type \'{0}\''.format(pull_type)
        )

    bad_kwargs = [x for x in kwargs
                  if not x.startswith('__')
                  or x not in valid_kwargs]

    if bad_kwargs:
        _invalid_kwargs(*bad_kwargs, **kwargs)

    pull_opts = []

    if pull_type in ('raw', 'tar'):
        verify = kwargs.get('verify', False)
        if not verify:
            pull_opts.append('--verify=no')
        else:
            def _bad_verify():
                raise SaltInvocationEror(
                    '\'verify\' must be one of the following: '
                    'signature, checksum'
                )
            try:
                verify = verify.lower()
            except AttributeError:
                _bad_verify()
            else:
                if verify not in ('signature', 'checksum'):
                    _bad_verify()
                pull_opts.append('--verify={0}'.format(verify))

    elif pull_type == 'dkr':
        # No need to validate the index URL, machinectl will take care of this
        # for us.
        if 'index' in kwargs:
            pull_opts.append('--dkr-index-url={0}'.format(kwargs['index']))

    cmd = 'pull-{0} {1} {2} {3}'.format(
        pull_type, ' '.join(pull_opts), image, name
    )
    result = _machinectl(cmd, use_vt=True)
    if result['retcode'] != 0:
        msg = 'Error occurred pulling image. Stderr from the pull command ' \
              '(if any) follows: '
        if result['stderr']:
            msg += '\n\n{0}'.format(result['stderr'])
        raise CommandExecutionError(msg)
    return True


def pull_raw(url, name, verify=False):
    '''
    Execute a ``machinectl pull-raw`` to download a .qcow2 or raw disk image,
    and add it to /var/lib/machines as a new container.

    .. note::

        **Requires systemd >= 219**

    url
        URL from which to download the container

    name
        Name for the new container

    verify : False
        Perform signature or checksum verification on the container. See the
        ``machinectl(1)`` man page (section titled "Image Transfer Commands")
        for more information on requirements for image verification. To perform
        signature verification, use ``verify=signature``. For checksum
        verification, use ``verify=checksum``. By default, no verification will
        be performed.

    CLI Examples:

    .. code-block:: bash

        salt myminion nspawn.pull_raw http://ftp.halifax.rwth-aachen.de/fedora/linux/releases/21/Cloud/Images/x86_64/Fedora-Cloud-Base-20141203-21.x86_64.raw.xz fedora21
    '''
    return _pull_image('raw', url, name, verify)


def pull_tar(url, name, verify=False):
    '''
    Execute a ``machinectl pull-raw`` to download a .tar container image,
    and add it to /var/lib/machines as a new container.

    .. note::

        **Requires systemd >= 219**

    url
        URL from which to download the container

    name
        Name for the new container

    verify : False
        Perform signature or checksum verification on the container. See the
        ``machinectl(1)`` man page (section titled "Image Transfer Commands")
        for more information on requirements for image verification. To perform
        signature verification, use ``verify=signature``. For checksum
        verification, use ``verify=checksum``. By default, no verification will
        be performed.

    CLI Examples:

    .. code-block:: bash

        salt myminion nspawn.pull_tar http://foo.domain.tld/containers/archlinux-2015.02.01.tar.gz arch2
    '''
    return _pull_image('tar', url, name, verify)


def pull_dkr(url, name, index=False):
    '''
    Execute a ``machinectl pull-dkr`` to download a docker image and add it to
    /var/lib/machines as a new container.

    .. note::

        **Requires systemd >= 219**

    url
        URL from which to download the container

    name
        Name for the new container

    index : None
        URL of the Docker index server from which to pull (must be an
        ``http://`` or ``https://`` URL).

    CLI Examples:

    .. code-block:: bash

        salt myminion nspawn.pull_dkr
        salt myminion nspawn.pull_docker
    '''
    return _pull_image('dkr', url, name, verify)

pull_docker = pull_dkr
