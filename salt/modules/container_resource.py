# -*- coding: utf-8 -*-
'''
Common resources for LXC and systemd-nspawn containers

These functions are not designed to be called directly, but instead from the
:mod:`lxc <salt.modules.lxc>` and the (future) :mod:`nspawn
<salt.modules.nspawn>` execution modules.
'''

# Import python libs
from __future__ import absolute_import
import functools
import logging
import os
import pipes
import time
import traceback

# Import salt libs
import salt.utils
import salt.ext.six as six
from salt.exceptions import CommandExecutionError, SaltInvocationError
from salt.utils import vt

log = logging.getLogger(__name__)

PATH = 'PATH=/bin:/usr/bin:/sbin:/usr/sbin:/opt/bin:' \
       '/usr/local/bin:/usr/local/sbin'


def _validate(wrapped):
    '''
    Decorator for common function argument validation
    '''
    @functools.wraps(wrapped)
    def check_valid_input(*args, **kwargs):
        container_type = kwargs.get('container_type')
        exec_method = kwargs.get('exec_method')
        valid_method = {
            'docker-ng': ('lxc-attach', 'nsenter'),
            'lxc': ('lxc-attach',),
            'nspawn': ('nsenter',),
        }
        if container_type not in valid_method:
            raise SaltInvocationError(
                'Invalid container type \'{0}\'. Valid types are: {1}'
                .format(container_type, ', '.join(sorted(valid_method)))
            )
        if exec_method not in valid_method[container_type]:
            raise SaltInvocationError(
                'Invalid command execution method. Valid methods are: {0}'
                .format(', '.join(valid_method[container_type]))
            )
        return wrapped(*args, **salt.utils.clean_kwargs(**kwargs))
    return check_valid_input


def _nsenter(pid):
    '''
    Return the nsenter command to attach to the named container
    '''
    return (
        'nsenter --target {0} --mount --uts --ipc --net --pid'
        .format(pid)
    )


def _get_md5(name, path, run_func):
    '''
    Get the MD5 checksum of a file from a container
    '''
    output = run_func(name,
                      'md5sum {0}'.format(pipes.quote(path)),
                      ignore_retcode=True)['stdout']
    try:
        return output.split()[0]
    except IndexError:
        # Destination file does not exist or could not be accessed
        return None


@_validate
def run(name,
        cmd,
        container_type=None,
        exec_method=None,
        output=None,
        no_start=False,
        stdin=None,
        python_shell=True,
        output_loglevel='debug',
        ignore_retcode=False,
        use_vt=False,
        keep_env=None):
    '''
    Common logic for running shell commands in containers
    '''
    valid_output = ('stdout', 'stderr', 'retcode', 'all')
    if output is None:
        cmd_func = 'cmd.run'
    elif output not in valid_output:
        raise SaltInvocationError(
            '\'output\' param must be one of the following: {0}'
            .format(', '.join(valid_output))
        )
    else:
        cmd_func = 'cmd.run_all'

    if keep_env is None or isinstance(keep_env, bool):
        to_keep = []
    elif not isinstance(keep_env, (list, tuple)):
        try:
            to_keep = keep_env.split(',')
        except AttributeError:
            log.warning('Invalid keep_env value, ignoring')
            to_keep = []
    else:
        to_keep = keep_env

    if exec_method == 'lxc-attach':
        full_cmd = 'lxc-attach '
        if keep_env is not True:
            full_cmd += '--clear-env '
            if 'PATH' not in to_keep:
                full_cmd += '--set-var {0} '.format(PATH)
                # --clear-env results in a very restrictive PATH
                # (/bin:/usr/bin), use a good fallback.
        full_cmd += ' '.join(
            ['--set-var {0}={1}'.format(x, pipes.quote(os.environ[x]))
                for x in to_keep
                if x in os.environ]
        )
        full_cmd += ' -n {0} -- {1}'.format(pipes.quote(name), cmd)
    elif exec_method == 'nsenter':
        pid = __salt__['{0}.pid'.format(container_type)](name)
        full_cmd = (
            'nsenter --target {0} --mount --uts --ipc --net --pid -- '
            .format(pid)
        )
        if keep_env is not True:
            full_cmd += 'env -i '
            if 'PATH' not in to_keep:
                full_cmd += '{0} '.format(PATH)
        full_cmd += ' '.join(
            ['{0}={1}'.format(x, pipes.quote(os.environ[x]))
                for x in to_keep
                if x in os.environ]
        )
        full_cmd += ' {0}'.format(cmd)

    if not use_vt:
        ret = __salt__[cmd_func](full_cmd,
                                 stdin=stdin,
                                 python_shell=python_shell,
                                 output_loglevel=output_loglevel,
                                 ignore_retcode=ignore_retcode)
    else:
        stdout, stderr = '', ''
        try:
            proc = vt.Terminal(full_cmd,
                               shell=python_shell,
                               log_stdin_level=output_loglevel if
                                               output_loglevel == 'quiet'
                                               else 'info',
                               log_stdout_level=output_loglevel,
                               log_stderr_level=output_loglevel,
                               log_stdout=True,
                               log_stderr=True,
                               stream_stdout=False,
                               stream_stderr=False)
            # Consume output
            while proc.has_unread_data:
                try:
                    cstdout, cstderr = proc.recv()
                    if cstdout:
                        stdout += cstdout
                    if cstderr:
                        if output is None:
                            stdout += cstderr
                        else:
                            stderr += cstderr
                    time.sleep(0.5)
                except KeyboardInterrupt:
                    break
            ret = stdout if output is None \
                else {'retcode': proc.exitstatus,
                      'pid': 2,
                      'stdout': stdout,
                      'stderr': stderr}
        except vt.TerminalException:
            trace = traceback.format_exc()
            log.error(trace)
            ret = stdout if output is None \
                else {'retcode': 127,
                      'pid': 2,
                      'stdout': stdout,
                      'stderr': stderr}
        finally:
            proc.terminate()

    return ret


@_validate
def copy_to(name,
            source,
            dest,
            container_type=None,
            exec_method=None,
            overwrite=False,
            makedirs=False):
    '''
    Common logic for copying files to containers
    '''
    # Get the appropriate functions
    state = __salt__['{0}.state'.format(container_type)]
    run_all = __salt__['{0}.run_all'.format(container_type)]

    c_state = state(name)
    if c_state != 'running':
        raise CommandExecutionError(
            'Container \'{0}\' is not running'.format(name)
        )

    source_dir, source_name = os.path.split(source)

    # Source file sanity checks
    if not os.path.isabs(source):
        raise SaltInvocationError('Source path must be absolute')
    elif not os.path.exists(source):
        raise SaltInvocationError(
            'Source file {0} does not exist'.format(source)
        )
    elif not os.path.isfile(source):
        raise SaltInvocationError('Source must be a regular file')

    # Destination file sanity checks
    if not os.path.isabs(dest):
        raise SaltInvocationError('Destination path must be absolute')
    if run_all(name,
               'test -d {0}'.format(pipes.quote(dest)),
               ignore_retcode=True)['retcode'] == 0:
        # Destination is a directory, full path to dest file will include the
        # basename of the source file.
        dest = os.path.join(dest, source_name)
    else:
        # Destination was not a directory. We will check to see if the parent
        # dir is a directory, and then (if makedirs=True) attempt to create the
        # parent directory.
        dest_dir, dest_name = os.path.split(dest)
        if run_all(name,
                   'test -d {0}'.format(pipes.quote(dest_dir)),
                   ignore_retcode=True)['retcode'] != 0:
            if makedirs:
                result = run_all(name,
                                 'mkdir -p {0}'.format(pipes.quote(dest_dir)))
                if result['retcode'] != 0:
                    error = ('Unable to create destination directory {0} in '
                             'container \'{1}\''.format(dest_dir, name))
                    if result['stderr']:
                        error += ': {0}'.format(result['stderr'])
                    raise CommandExecutionError(error)
            else:
                raise SaltInvocationError(
                    'Directory {0} does not exist on {1} container \'{2}\''
                    .format(dest_dir, container_type, name)
                )
    if not overwrite and run_all(name,
                                 'test -e {0}'.format(pipes.quote(dest)),
                                 ignore_retcode=True)['retcode'] == 0:
        raise CommandExecutionError(
            'Destination path {0} already exists. Use overwrite=True to '
            'overwrite it'.format(dest)
        )

    # Before we try to replace the file, compare checksums.
    source_md5 = __salt__['file.get_sum'](source, 'md5')
    if source_md5 == _get_md5(name, dest, run_all):
        log.debug('{0} and {1}:{2} are the same file, skipping copy'
                  .format(source, name, dest))
        return True

    log.debug('Copying {0} to {1} container \'{2}\' as {3}'
              .format(source, container_type, name, dest))

    # Using cat here instead of opening the file, reading it into memory,
    # and passing it as stdin to run(). This will keep down memory
    # usage for the minion and make the operation run quicker.
    if exec_method == 'lxc-attach':
        __salt__['cmd.run_stdout'](
            'cat "{0}" | lxc-attach --clear-env --set-var {1} -n {2} -- '
            'tee "{3}"'.format(source, PATH, name, dest),
            python_shell=True
        )
    elif exec_method == 'nsenter':
        pid = __salt__['{0}.pid'.format(container_type)](name)
        __salt__['cmd.run_stdout'](
            'cat "{0}" | {1} env -i {2} tee "{3}"'
            .format(source, _nsenter(pid), PATH, dest),
            python_shell=True
        )
    return source_md5 == _get_md5(name, dest, run_all)
