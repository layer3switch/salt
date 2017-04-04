# -*- coding: utf-8 -*-
'''
Module for managing Solaris logadm based log rotations.
'''
from __future__ import absolute_import

# Import python libs
import logging
import shlex

# Import salt libs
import salt.utils

log = logging.getLogger(__name__)
default_conf = '/etc/logadm.conf'
option_toggles = {
    '-c': 'copy_and_truncate',
    '-l': 'localtime',
    '-N': 'skip_missing',
}
option_flags = {
    '-A': 'age',
    '-C': 'count',
    '-a': 'post_command',
    '-b': 'pre_command',
    '-e': 'mail_addr',
    '-E': 'expire_command',
    '-g': 'group',
    '-m': 'mode',
    '-M': 'rename_command',
    '-o': 'owner',
    '-p': 'period',
    '-P': 'timestmp',
    '-R': 'old_created_command',
    '-s': 'size',
    '-S': 'max_size',
    '-t': 'template',
    '-T': 'pattern',
    '-w': 'entryname',
    '-z': 'compress_count',
}


def __virtual__():
    '''
    Only work on Solaris based systems
    '''
    if 'Solaris' in __grains__['os_family']:
        return True
    return (False, 'The logadm execution module cannot be loaded: only available on Solaris.')


def _parse_conf(conf_file=default_conf):
    '''
    Parse a logadm configuration file.
    '''
    ret = {}
    # ret = []
    with salt.utils.fopen(conf_file, 'r') as ifile:
        for line in ifile:
            line = line.strip()
            if not line:
                continue
            if line.startswith('#'):
                continue
            splitline = line.split(' ', 1)
            ret[splitline[0]] = splitline[1]
    return ret


def show_conf(conf_file=default_conf, name=None):
    '''
    Show configuration

    .. versionchanged:: Nitrogen

    conf_file : string
        path to logadm.conf, defaults to /etc/logadm.conf
    name : string
        optional show only a single entry

    CLI Example:

    .. code-block:: bash

        salt '*' logadm.show_conf
        salt '*' logadm.show_conf name=/var/log/syslog
    '''
    cfg = _parse_conf(conf_file)

    ## filter
    if name and name in cfg:
        return {name: cfg[name]}
    elif name:
        return {name: 'not found in {}'.format(conf_file)}
    else:
        return cfg


def list_conf(conf_file=default_conf, log_file=None):
    '''
    Show parsed configuration

    .. versionadded:: Nitrogen

    conf_file : string
        path to logadm.conf, defaults to /etc/logadm.conf
    log_file : string
        optional show only one log file

    CLI Example:

    .. code-block:: bash

        salt '*' logadm.list_conf
        salt '*' logadm.list_conf log=/var/log/syslog
    '''
    cfg = _parse_conf(conf_file)
    cfg_parsed = {}

    ## parse all options
    for log in cfg:
        log_cfg = {}
        options = shlex.split(cfg[log])
        if len(options) == 0:
            continue

        # handle toggle options
        for opt in option_toggles:
            log_cfg[option_toggles[opt]] = opt in options
            if opt in options:
                options.remove(opt)

        # handle flag options
        for opt in option_flags:
            opt_val = None
            if opt in options:
                if len(options) > options.index(opt):
                    opt_val = options[options.index(opt)+1]
                options.remove(opt)

            log_cfg[option_flags[opt]] = opt_val
            if opt_val:
                options.remove(opt_val)

        # handle log file
        if log.startswith('/'):
            log_cfg['log_file'] = log
        else:
            log_cfg['entryname'] = log
            if options[0].startswith('/'):
                log_cfg['log_file'] = options[0]
                del options[0]

        # handle unknown options
        if len(options) > 0:
            log_cfg['additional_options'] = " ".join(options)

        cfg_parsed[log_cfg['log_file'] if log_cfg['log_file'] else log_cfg['entryname']] = log_cfg

    ## filter
    if log_file and log_file in cfg_parsed:
        return {log_file: cfg_parsed[log_file]}
    elif log_file:
        return {log_file: 'not found in {}'.format(conf_file)}
    else:
        return cfg_parsed


def rotate(name,
           pattern=False,
           count=False,
           age=False,
           size=False,
           copy=True,
           conf_file=default_conf):
    '''
    Set up pattern for logging.

    CLI Example:

    .. code-block:: bash

      salt '*' logadm.rotate myapplog pattern='/var/log/myapp/*.log' count=7
    '''
    command = "logadm -f {0} -w {1}".format(conf_file, name)
    if count:
        command += " -C {0}".format(count)
    if age:
        command += " -A {0}".format(age)
    if copy:
        command += " -c"
    if size:
        command += " -s {0}".format(size)
    if pattern:
        command += " {0}".format(pattern)

    result = __salt__['cmd.run_all'](command, python_shell=False)
    if result['retcode'] != 0:
        return dict(Error='Failed in adding log', Output=result['stderr'])

    return dict(Result='Success')


def remove(name, conf_file=default_conf):
    '''
    Remove log pattern from logadm

    CLI Example:

    .. code-block:: bash

      salt '*' logadm.remove myapplog
    '''
    command = "logadm -f {0} -r {1}".format(conf_file, name)
    result = __salt__['cmd.run_all'](command, python_shell=False)
    if result['retcode'] != 0:
        return dict(
            Error='Failure in removing log. Possibly already removed?',
            Output=result['stderr']
        )
    return dict(Result='Success')
