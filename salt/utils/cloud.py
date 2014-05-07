# -*- coding: utf-8 -*-
'''
Utility functions for salt.cloud
'''

# Import python libs
import os
import sys
import codecs
import shutil
import socket
import tempfile
import time
import subprocess
import multiprocessing
import logging
import pipes
import json
import traceback
import copy
import re


# Let's import pwd and catch the ImportError. We'll raise it if this is not
# Windows
try:
    import pwd
except ImportError:
    if not sys.platform.lower().startswith('win'):
        # We can't use salt.utils.is_windows() from the import a little down
        # because that will cause issues under windows at install time.
        raise

# Import salt libs
import salt.crypt
import salt.client
import salt.config
import salt.utils
import salt.utils.event
from salt import syspaths
from salt.utils import vt
from salt.utils.nb_popen import NonBlockingPopen
from salt.utils.yamldumper import SafeOrderedDumper
from salt.utils.validate.path import is_writeable

# Import salt cloud libs
import salt.cloud
from salt.cloud.exceptions import (
    SaltCloudConfigError,
    SaltCloudException,
    SaltCloudSystemExit,
    SaltCloudExecutionTimeout,
    SaltCloudExecutionFailure,
    SaltCloudPasswordError
)

# Import third party libs
from jinja2 import Template
import yaml

try:
    import getpass
    HAS_GETPASS = True
except ImportError:
    HAS_GETPASS = False

NSTATES = {
    0: 'running',
    1: 'rebooting',
    2: 'terminated',
    3: 'pending',
}

SSH_PASSWORD_PROMP_RE = re.compile(r'(?:.*)[Pp]assword(?: for .*)?:', re.M)

# Get logging started
log = logging.getLogger(__name__)


def __render_script(path, vm_=None, opts=None, minion=''):
    '''
    Return the rendered script
    '''
    log.info('Rendering deploy script: {0}'.format(path))
    try:
        with salt.utils.fopen(path, 'r') as fp_:
            template = Template(fp_.read())
            return str(template.render(opts=opts, vm=vm_, minion=minion))
    except AttributeError:
        # Specified renderer was not found
        with salt.utils.fopen(path, 'r') as fp_:
            return fp_.read()


def os_script(os_, vm_=None, opts=None, minion=''):
    '''
    Return the script as a string for the specific os
    '''
    if os.path.isabs(os_):
        # The user provided an absolute path to the deploy script, let's use it
        return __render_script(os_, vm_, opts, minion)

    if os.path.isabs('{0}.sh'.format(os_)):
        # The user provided an absolute path to the deploy script, although no
        # extension was provided. Let's use it anyway.
        return __render_script('{0}.sh'.format(os_), vm_, opts, minion)

    for search_path in opts['deploy_scripts_search_path']:
        if os.path.isfile(os.path.join(search_path, os_)):
            return __render_script(
                os.path.join(search_path, os_), vm_, opts, minion
            )

        if os.path.isfile(os.path.join(search_path, '{0}.sh'.format(os_))):
            return __render_script(
                os.path.join(search_path, '{0}.sh'.format(os_)),
                vm_, opts, minion
            )
    # No deploy script was found, return an empty string
    return ''


def gen_keys(keysize=2048):
    '''
    Generate Salt minion keys and return them as PEM file strings
    '''
    # Mandate that keys are at least 2048 in size
    if keysize < 2048:
        keysize = 2048
    tdir = tempfile.mkdtemp()

    salt.crypt.gen_keys(tdir, 'minion', keysize)
    priv_path = os.path.join(tdir, 'minion.pem')
    pub_path = os.path.join(tdir, 'minion.pub')
    with salt.utils.fopen(priv_path) as fp_:
        priv = fp_.read()
    with salt.utils.fopen(pub_path) as fp_:
        pub = fp_.read()
    shutil.rmtree(tdir)
    return priv, pub


def accept_key(pki_dir, pub, id_):
    '''
    If the master config was available then we will have a pki_dir key in
    the opts directory, this method places the pub key in the accepted
    keys dir and removes it from the unaccepted keys dir if that is the case.
    '''
    for key_dir in ('minions', 'minions_pre', 'minions_rejected'):
        key_path = os.path.join(pki_dir, key_dir)
        if not os.path.exists(key_path):
            os.makedirs(key_path)

    key = os.path.join(pki_dir, 'minions', id_)
    with salt.utils.fopen(key, 'w+') as fp_:
        fp_.write(pub)

    oldkey = os.path.join(pki_dir, 'minions_pre', id_)
    if os.path.isfile(oldkey):
        with salt.utils.fopen(oldkey) as fp_:
            if fp_.read() == pub:
                os.remove(oldkey)


def remove_key(pki_dir, id_):
    '''
    This method removes a specified key from the accepted keys dir
    '''
    key = os.path.join(pki_dir, 'minions', id_)
    if os.path.isfile(key):
        os.remove(key)
        log.debug('Deleted {0!r}'.format(key))


def rename_key(pki_dir, id_, new_id):
    '''
    Rename a key, when an instance has also been renamed
    '''
    oldkey = os.path.join(pki_dir, 'minions', id_)
    newkey = os.path.join(pki_dir, 'minions', new_id)
    if os.path.isfile(oldkey):
        os.rename(oldkey, newkey)


def minion_config(opts, vm_):
    '''
    Return a minion's configuration for the provided options and VM
    '''

    # Let's get a copy of the salt minion default options
    minion = salt.config.DEFAULT_MINION_OPTS.copy()
    # Some default options are Null, let's set a reasonable default
    minion.update(
        log_level='info',
        log_level_logfile='info'
    )

    # Now, let's update it to our needs
    minion['id'] = vm_['name']
    master_finger = salt.config.get_cloud_config_value('master_finger', vm_, opts)
    if master_finger is not None:
        minion['master_finger'] = master_finger
    minion.update(
        # Get ANY defined minion settings, merging data, in the following order
        # 1. VM config
        # 2. Profile config
        # 3. Global configuration
        salt.config.get_cloud_config_value(
            'minion', vm_, opts, default={}, search_global=True
        )
    )

    make_master = salt.config.get_cloud_config_value('make_master', vm_, opts)
    if 'master' not in minion and make_master is not True:
        raise SaltCloudConfigError(
            'A master setting was not defined in the minion\'s configuration.'
        )

    # Get ANY defined grains settings, merging data, in the following order
    # 1. VM config
    # 2. Profile config
    # 3. Global configuration
    minion.setdefault('grains', {}).update(
        salt.config.get_cloud_config_value(
            'grains', vm_, opts, default={}, search_global=True
        )
    )
    return minion


def master_config(opts, vm_):
    '''
    Return a master's configuration for the provided options and VM
    '''
    # Let's get a copy of the salt master default options
    master = salt.config.DEFAULT_MASTER_OPTS.copy()
    # Some default options are Null, let's set a reasonable default
    master.update(
        log_level='info',
        log_level_logfile='info'
    )

    # Get ANY defined master setting, merging data, in the following order
    # 1. VM config
    # 2. Profile config
    # 3. Global configuration
    master.update(
        salt.config.get_cloud_config_value(
            'master', vm_, opts, default={}, search_global=True
        )
    )
    return master


def salt_config_to_yaml(configuration, line_break='\n'):
    '''
    Return a salt configuration dictionary, master or minion, as a yaml dump
    '''
    return yaml.dump(configuration,
                     line_break=line_break,
                     default_flow_style=False,
                     Dumper=SafeOrderedDumper)


def bootstrap(vm_, opts):
    '''
    This is the primary entry point for logging into any system (POSIX or
    Windows) to install Salt. It will make the decision on its own as to which
    deploy function to call.
    '''
    if salt.config.get_cloud_config_value('deploy', vm_, opts) is False:
        return {
            'Error': {
                'No Deploy': '\'deploy\' is not enabled. Not deploying.'
            }
        }
    key_filename = salt.config.get_cloud_config_value(
        'key_filename', vm_, opts, search_global=False, default=None
    )
    if key_filename is not None and not os.path.isfile(key_filename):
        raise SaltCloudConfigError(
            'The defined ssh_keyfile {0!r} does not exist'.format(
                key_filename
            )
        )

    if key_filename is None and salt.utils.which('sshpass') is None:
        raise SaltCloudSystemExit(
            'Cannot deploy salt in a VM if the \'ssh_keyfile\' setting '
            'is not set and \'sshpass\' binary is not present on the '
            'system for the password.'
        )

    ret = {}

    deploy_script_code = os_script(
        salt.config.get_cloud_config_value(
            'os', vm_, opts, default='bootstrap-salt'
        ),
        vm_, opts
    )

    ssh_username = salt.config.get_cloud_config_value(
        'ssh_username', vm_, opts, default='root'
    )

    deploy_kwargs = {
        'opts': opts,
        'host': vm_['ssh_host'],
        'username': ssh_username,
        'script': deploy_script_code,
        'name': vm_['name'],
        'tmp_dir': salt.config.get_cloud_config_value(
            'tmp_dir', vm_, opts, default='/tmp/.saltcloud'
        ),
        'deploy_command': salt.config.get_cloud_config_value(
            'deploy_command', vm_, opts,
            default='/tmp/.saltcloud/deploy.sh',
        ),
        'start_action': opts['start_action'],
        'parallel': opts['parallel'],
        'sock_dir': opts['sock_dir'],
        'conf_file': opts['conf_file'],
        'minion_pem': vm_['priv_key'],
        'minion_pub': vm_['pub_key'],
        'keep_tmp': opts['keep_tmp'],
        'sudo': salt.config.get_cloud_config_value(
            'sudo', vm_, opts, default=(ssh_username != 'root')
        ),
        'sudo_password': salt.config.get_cloud_config_value(
            'sudo_password', vm_, opts, default=None
        ),
        'tty': salt.config.get_cloud_config_value(
            'tty', vm_, opts, default=True
        ),
        'password': salt.config.get_cloud_config_value(
            'password', vm_, opts, search_global=False
        ),
        'key_filename': key_filename,
        'script_args': salt.config.get_cloud_config_value(
            'script_args', vm_, opts
        ),
        'script_env': salt.config.get_cloud_config_value(
            'script_env', vm_, opts
        ),
        'minion_conf': salt.utils.cloud.minion_config(opts, vm_),
        'preseed_minion_keys': vm_.get('preseed_minion_keys', None),
        'display_ssh_output': salt.config.get_cloud_config_value(
            'display_ssh_output', vm_, opts, default=True
        )
    }
    # forward any info about possible ssh gateway to deploy script
    # as some providers need also a 'gateway' configuration
    if 'gateway' in vm_:
        deploy_kwargs.update({'gateway': vm_['gateway']})

    # Deploy salt-master files, if necessary
    if salt.config.get_cloud_config_value('make_master', vm_, opts) is True:
        deploy_kwargs['make_master'] = True
        deploy_kwargs['master_pub'] = vm_['master_pub']
        deploy_kwargs['master_pem'] = vm_['master_pem']
        master_conf = salt.utils.cloud.master_config(opts, vm_)
        deploy_kwargs['master_conf'] = master_conf

        if master_conf.get('syndic_master', None):
            deploy_kwargs['make_syndic'] = True

    deploy_kwargs['make_minion'] = salt.config.get_cloud_config_value(
        'make_minion', vm_, opts, default=True
    )

    win_installer = salt.config.get_cloud_config_value(
        'win_installer', vm_, opts
    )
    if win_installer:
        deploy_kwargs['win_installer'] = win_installer
        minion = salt.utils.cloud.minion_config(opts, vm_)
        deploy_kwargs['master'] = minion['master']
        deploy_kwargs['username'] = salt.config.get_cloud_config_value(
            'win_username', vm_, opts, default='Administrator'
        )
        deploy_kwargs['password'] = salt.config.get_cloud_config_value(
            'win_password', vm_, opts, default=''
        )

    # Store what was used to the deploy the VM
    event_kwargs = copy.deepcopy(deploy_kwargs)
    del event_kwargs['opts']
    del event_kwargs['minion_pem']
    del event_kwargs['minion_pub']
    del event_kwargs['sudo_password']
    if 'password' in event_kwargs:
        del event_kwargs['password']
    ret['deploy_kwargs'] = event_kwargs

    fire_event(
        'event',
        'executing deploy script',
        'salt/cloud/{0}/deploying'.format(vm_['name']),
        {'kwargs': event_kwargs},
        transport=opts.get('transport', 'zeromq')
    )

    deployed = False
    if win_installer:
        deployed = deploy_windows(**deploy_kwargs)
    else:
        deployed = deploy_script(**deploy_kwargs)

    if deployed:
        ret['deployed'] = deployed
        log.info('Salt installed on {0}'.format(vm_['name']))
        return ret

    log.error('Failed to start Salt on host {0}'.format(vm_['name']))
    return {
        'Error': {
            'Not Deployed': 'Failed to start Salt on host {0}'.format(
                vm_['name']
            )
        }
    }


def ssh_usernames(vm_, opts, default_users=None):
    '''
    Return the ssh_usernames. Defaults to a built-in list of users for trying.
    '''
    if default_users is None:
        default_users = ['root']

    usernames = salt.config.get_cloud_config_value(
        'ssh_username', vm_, opts
    )

    if not isinstance(usernames, list):
        usernames = [usernames]

    # get rid of None's or empty names
    usernames = filter(lambda x: x, usernames)
    # Keep a copy of the usernames the user might have provided
    initial = usernames[:]

    # Add common usernames to the list to be tested
    for name in default_users:
        if name not in usernames:
            usernames.append(name)
    # Add the user provided usernames to the end of the list since enough time
    # might need to pass before the remote service is available for logins and
    # the proper username might have passed its iteration.
    # This has detected in a CentOS 5.7 EC2 image
    usernames.extend(initial)
    return usernames


def wait_for_fun(fun, timeout=900, **kwargs):
    '''
    Wait until a function finishes, or times out
    '''
    start = time.time()
    log.debug('Attempting function {0}'.format(fun))
    trycount = 0
    while True:
        trycount += 1
        try:
            response = fun(**kwargs)
            if type(response) is not bool:
                return response
        except Exception as exc:
            log.debug('Caught exception in wait_for_fun: {0}'.format(exc))
            time.sleep(1)
            if time.time() - start > timeout:
                log.error('Function timed out: {0}'.format(timeout))
                return False

            log.debug(
                'Retrying function {0} on  (try {1})'.format(
                    fun, trycount
                )
            )


def wait_for_port(host, port=22, timeout=900, gateway=None):
    '''
    Wait until a connection to the specified port can be made on a specified
    host. This is usually port 22 (for SSH), but in the case of Windows
    installations, it might be port 445 (for winexe). It may also be an
    alternate port for SSH, depending on the base image.
    '''
    start = time.time()
    # Assign test ports because if a gateway is defined
    # we first want to test the gateway before the host.
    test_ssh_host = host
    test_ssh_port = port
    if gateway:
        ssh_gateway = gateway['ssh_gateway']
        ssh_gateway_port = 22
        if ':' in ssh_gateway:
            ssh_gateway, ssh_gateway_port = ssh_gateway.split(':')
        if 'ssh_gateway_port' in gateway:
            ssh_gateway_port = gateway['ssh_gateway_port']
        test_ssh_host = ssh_gateway
        test_ssh_port = ssh_gateway_port
        log.debug(
            'Attempting connection to host {0} on port {1} '
            'via gateway {2} on port {3}'.format(
                host, port, ssh_gateway, ssh_gateway_port
            )
        )
    else:
        log.debug(
            'Attempting connection to host {0} on port {1}'.format(
                host, port
            )
        )
    trycount = 0
    while True:
        trycount += 1
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(30)
            sock.connect((test_ssh_host, test_ssh_port))
            # Stop any remaining reads/writes on the socket
            sock.shutdown(socket.SHUT_RDWR)
            # Close it!
            sock.close()
            break
        except socket.error as exc:
            log.debug('Caught exception in wait_for_port: {0}'.format(exc))
            time.sleep(1)
            if time.time() - start > timeout:
                log.error('Port connection timed out: {0}'.format(timeout))
                return False
            if not gateway:
                log.debug(
                    'Retrying connection to host {0} on port {1} '
                    '(try {2})'.format(
                        test_ssh_host, test_ssh_port, trycount
                    )
                )
            else:
                log.debug(
                    'Retrying connection to Gateway {0} on port {1} '
                    '(try {2})'.format(
                        test_ssh_host, test_ssh_port, trycount
                    )
                )
    if not gateway:
        return True
    # Let the user know that his gateway is good!
    log.debug(
        'Gateway {0} on port {1} '
        'is reachable.'.format(
            test_ssh_host, test_ssh_port
        )
    )

    # Now we need to test the host via the gateway.
    # We will use netcat on the gateway to test the port
    ssh_args = []
    ssh_args.extend([
        # Don't add new hosts to the host key database
        '-oStrictHostKeyChecking=no',
        # Set hosts key database path to /dev/null, ie, non-existing
        '-oUserKnownHostsFile=/dev/null',
        # Don't re-use the SSH connection. Less failures.
        '-oControlPath=none'
    ])
    # There should never be both a password and an ssh key passed in, so
    if 'ssh_gateway_key' in gateway:
        ssh_args.extend([
            # tell SSH to skip password authentication
            '-oPasswordAuthentication=no',
            '-oChallengeResponseAuthentication=no',
            # Make sure public key authentication is enabled
            '-oPubkeyAuthentication=yes',
            # No Keyboard interaction!
            '-oKbdInteractiveAuthentication=no',
            # Also, specify the location of the key file
            '-i {0}'.format(gateway['ssh_gateway_key'])
        ])
    # Netcat command testing remote port
    command = 'nc -z -w5 -q0 {0} {1}'.format(host, port)
    # SSH command
    pcmd = 'ssh {0} {1}@{2} -p {3} {4}'.format(
        ' '.join(ssh_args), gateway['ssh_gateway_user'], ssh_gateway,
        ssh_gateway_port, pipes.quote('date')
    )
    cmd = 'ssh {0} {1}@{2} -p {3} {4}'.format(
        ' '.join(ssh_args), gateway['ssh_gateway_user'], ssh_gateway,
        ssh_gateway_port, pipes.quote(command)
    )
    log.debug('SSH command: {0!r}'.format(cmd))

    kwargs = {'display_ssh_output': False,
              'password': gateway.get('ssh_gateway_password', None)}
    trycount = 0
    usable_gateway = False
    gateway_retries = 5
    while True:
        trycount += 1
        # test gateway usage
        if not usable_gateway:
            pstatus = _exec_ssh_cmd(pcmd, **kwargs)
            if pstatus == 0:
                usable_gateway = True
            else:
                gateway_retries -= 1
                log.error(
                    'Gateway usage seems to be broken, '
                    'password error ? Tries left: {0}'.format(gateway_retries))
            if not gateway_retries:
                raise SaltCloudExecutionFailure(
                    'SSH gateway is reachable but we can not login')
        # then try to reach out the target
        if usable_gateway:
            status = _exec_ssh_cmd(cmd, **kwargs)
            # Get the exit code of the SSH command.
            # If 0 then the port is open.
            if status == 0:
                return True
        time.sleep(1)
        if time.time() - start > timeout:
            log.error('Port connection timed out: {0}'.format(timeout))
            return False
        log.debug(
            'Retrying connection to host {0} on port {1} '
            'via gateway {2} on port {3}. (try {4})'.format(
                host, port, ssh_gateway, ssh_gateway_port,
                trycount
            )
        )


def wait_for_winexesvc(host, port, username, password, timeout=900, gateway=None):
    '''
    Wait until winexe connection can be established.
    '''
    start = time.time()
    log.debug(
        'Attempting winexe connection to host {0} on port {1}'.format(
            host, port
        )
    )
    creds = '-U {0}%{1} //{2}'.format(
            username, password, host)
    trycount = 0
    while True:
        trycount += 1
        try:
            # Shell out to winexe to check %TEMP%
            ret_code = win_cmd('winexe {0} "sc query winexesvc"'.format(creds))
            if ret_code == 0:
                log.debug('winexe connected...')
                return True
            log.debug('Return code was {0}'.format(ret_code))
            time.sleep(1)
        except socket.error as exc:
            log.debug('Caught exception in wait_for_winexesvc: {0}'.format(exc))
            time.sleep(1)
            if time.time() - start > timeout:
                log.error('winexe connection timed out: {0}'.format(timeout))
                return False
            log.debug(
                'Retrying winexe connection to host {0} on port {1} '
                '(try {2})'.format(
                    host, port, trycount
                )
            )


def validate_windows_cred(host, username='Administrator', password=None):
    '''
    Check if the windows credentials are valid
    '''
    retcode = win_cmd('winexe -U {0}%{1} //{2} "hostname"'.format(
        username, password, host
    ))
    return retcode == 0


def wait_for_passwd(host, port=22, ssh_timeout=15, username='root',
                    password=None, key_filename=None, maxtries=15,
                    trysleep=1, display_ssh_output=True, gateway=None):
    '''
    Wait until ssh connection can be accessed via password or ssh key
    '''
    trycount = 0
    while trycount < maxtries:
        connectfail = False
        try:
            kwargs = {'hostname': host,
                      'port': port,
                      'username': username,
                      'password_retries': maxtries,
                      'timeout': ssh_timeout,
                      'display_ssh_output': display_ssh_output}
            if gateway:
                kwargs['ssh_gateway'] = gateway['ssh_gateway']
                kwargs['ssh_gateway_key'] = gateway['ssh_gateway_key']
                kwargs['ssh_gateway_user'] = gateway['ssh_gateway_user']

            if key_filename:
                if not os.path.isfile(key_filename):
                    raise SaltCloudConfigError(
                        'The defined key_filename {0!r} does not exist'.format(
                            key_filename
                        )
                    )
                kwargs['key_filename'] = key_filename
                log.debug('Using {0} as the key_filename'.format(key_filename))
            elif password:
                kwargs['password'] = password
                log.debug('Using password authentication'.format(password))

            trycount += 1
            log.debug(
                'Attempting to authenticate as {0} (try {1} of {2})'.format(
                    username, trycount, maxtries
                )
            )

            status = root_cmd('date', tty=False, sudo=False, **kwargs)
            if status != 0:
                connectfail = True
                if trycount < maxtries:
                    time.sleep(trysleep)
                    continue

                log.error(
                    'Authentication failed: status code {0}'.format(
                        status
                    )
                )
                return False
            if connectfail is False:
                return True
            return False
        except SaltCloudPasswordError:
            raise
        except Exception:
            if trycount >= maxtries:
                return False
            time.sleep(trysleep)


def deploy_windows(host,
                   port=445,
                   timeout=900,
                   username='Administrator',
                   password=None,
                   name=None,
                   pub_key=None,
                   sock_dir=None,
                   conf_file=None,
                   start_action=None,
                   parallel=False,
                   minion_pub=None,
                   minion_pem=None,
                   minion_conf=None,
                   keep_tmp=False,
                   script_args=None,
                   script_env=None,
                   port_timeout=15,
                   preseed_minion_keys=None,
                   win_installer=None,
                   master=None,
                   tmp_dir='C:\\salttmp',
                   opts=None,
                   **kwargs):
    '''
    Copy the install files to a remote Windows box, and execute them
    '''
    if not isinstance(opts, dict):
        opts = {}

    starttime = time.mktime(time.localtime())
    log.debug('Deploying {0} at {1} (Windows)'.format(host, starttime))
    if wait_for_port(host=host, port=port, timeout=port_timeout * 60) and \
                wait_for_winexesvc(host=host, port=port,
                             username=username, password=password,
                             timeout=port_timeout * 60):
        log.debug('SMB port {0} on {1} is available'.format(port, host))
        newtimeout = timeout - (time.mktime(time.localtime()) - starttime)
        log.debug(
            'Logging into {0}:{1} as {2}'.format(
                host, port, username
            )
        )
        newtimeout = timeout - (time.mktime(time.localtime()) - starttime)
        creds = '-U {0}%{1} //{2}'.format(
            username, password, host)
        # Shell out to smbclient to create C:\salttmp\
        win_cmd('smbclient {0}/c$ -c "mkdir salttemp; exit;"'.format(creds))
        # Shell out to smbclient to create C:\salt\conf\pki\minion
        win_cmd('smbclient {0}/c$ -c "mkdir salt; mkdir salt\\conf; mkdir salt\\conf\\pki; mkdir salt\\conf\\pki\\minion; exit;"'.format(creds))
        # Shell out to smbclient to copy over minion keys
        ## minion_pub, minion_pem
        kwargs = {'hostname': host,
                  'creds': creds}

        if minion_pub:
            smb_file('salt\\conf\\pki\\minion\\minion.pub', minion_pub, kwargs)

        if minion_pem:
            smb_file('salt\\conf\\pki\\minion\\minion.pem', minion_pem, kwargs)

        # Shell out to smbclient to copy over win_installer
        ## win_installer refers to a file such as:
        ## /root/Salt-Minion-0.17.0-win32-Setup.exe
        ## ..which exists on the same machine as salt-cloud
        comps = win_installer.split('/')
        local_path = '/'.join(comps[:-1])
        installer = comps[-1]
        win_cmd('smbclient {0}/c$ -c "cd salttemp; prompt; lcd {1}; mput {2}; exit;"'.format(
            creds, local_path, installer
        ))
        # Shell out to winexe to execute win_installer
        ## We don't actually need to set the master and the minion here since
        ## the minion config file will be set next via smb_file
        win_cmd('winexe {0} "c:\\salttemp\\{1} /S /master={2} /minion-name={3}"'.format(
            creds, installer, master, name
        ))

        # Shell out to smbclient to copy over minion_conf
        if minion_conf:
            if not isinstance(minion_conf, dict):
                # Let's not just fail regarding this change, specially
                # since we can handle it
                raise DeprecationWarning(
                    '`salt.utils.cloud.deploy_windows` now only accepts '
                    'dictionaries for its `minion_conf` parameter. '
                    'Loading YAML...'
                )
            minion_grains = minion_conf.pop('grains', {})
            if minion_grains:
                smb_file(
                    'salt\\conf\\grains',
                    salt_config_to_yaml(minion_grains, line_break='\r\n'),
                    kwargs
                )
            # Add special windows minion configuration
            # that must be in the minion config file
            windows_minion_conf = {
                'ipc_mode': 'tcp',
                'root_dir': 'c:\\salt',
                'pki_dir': '/conf/pki/minion',
                'multiprocessing': False,
            }
            minion_conf = dict(minion_conf, **windows_minion_conf)
            smb_file(
                'salt\\conf\\minion',
                salt_config_to_yaml(minion_conf, line_break='\r\n'),
                kwargs
            )
        # Shell out to smbclient to delete C:\salttmp\ and installer file
        ## Unless keep_tmp is True
        if not keep_tmp:
            win_cmd('smbclient {0}/c$ -c "del salttemp\\{1}; prompt; exit;"'.format(
                creds,
                installer,
            ))
            win_cmd('smbclient {0}/c$ -c "rmdir salttemp; prompt; exit;"'.format(
                creds,
            ))
        # Shell out to winexe to ensure salt-minion service started
        win_cmd('winexe {0} "sc stop salt-minion"'.format(
            creds,
        ))
        win_cmd('winexe {0} "sc start salt-minion"'.format(
            creds,
        ))

        # Fire deploy action
        fire_event(
            'event',
            '{0} has been deployed at {1}'.format(name, host),
            'salt/cloud/{0}/deploy_windows'.format(name),
            {'name': name},
            transport=opts.get('transport', 'zeromq')
        )

        return True
    return False


def deploy_script(host,
                  port=22,
                  timeout=900,
                  username='root',
                  password=None,
                  key_filename=None,
                  script=None,
                  name=None,
                  pub_key=None,
                  sock_dir=None,
                  provider=None,
                  conf_file=None,
                  start_action=None,
                  make_master=False,
                  master_pub=None,
                  master_pem=None,
                  master_conf=None,
                  minion_pub=None,
                  minion_pem=None,
                  minion_conf=None,
                  keep_tmp=False,
                  script_args=None,
                  script_env=None,
                  ssh_timeout=15,
                  make_syndic=False,
                  make_minion=True,
                  display_ssh_output=True,
                  preseed_minion_keys=None,
                  parallel=False,
                  sudo_password=None,
                  sudo=False,
                  tty=None,
                  deploy_command='/tmp/.saltcloud/deploy.sh',
                  opts=None,
                  tmp_dir='/tmp/.saltcloud',
                  **kwargs):
    '''
    Copy a deploy script to a remote server, execute it, and remove it
    '''
    if not isinstance(opts, dict):
        opts = {}

    if key_filename is not None and not os.path.isfile(key_filename):
        raise SaltCloudConfigError(
            'The defined key_filename {0!r} does not exist'.format(
                key_filename
            )
        )

    gateway = None
    if 'gateway' in kwargs:
        gateway = kwargs['gateway']

    starttime = time.mktime(time.localtime())
    log.debug('Deploying {0} at {1}'.format(host, starttime))

    if wait_for_port(host=host, port=port, gateway=gateway):
        log.debug('SSH port {0} on {1} is available'.format(port, host))
        newtimeout = timeout - (time.mktime(time.localtime()) - starttime)
        if wait_for_passwd(host, port=port, username=username,
                           password=password, key_filename=key_filename,
                           ssh_timeout=ssh_timeout,
                           display_ssh_output=display_ssh_output,
                           gateway=gateway):

            def remote_exists(path):
                return not root_cmd('test -e \\"{0}\\"'.format(path),
                                    tty, sudo, **kwargs)
            log.debug(
                'Logging into {0}:{1} as {2}'.format(
                    host, port, username
                )
            )
            newtimeout = timeout - (time.mktime(time.localtime()) - starttime)
            kwargs = {
                'hostname': host,
                'port': port,
                'username': username,
                'timeout': ssh_timeout,
                'display_ssh_output': display_ssh_output,
                'sudo_password': sudo_password,
            }
            if gateway:
                kwargs['ssh_gateway'] = gateway['ssh_gateway']
                kwargs['ssh_gateway_key'] = gateway['ssh_gateway_key']
                kwargs['ssh_gateway_user'] = gateway['ssh_gateway_user']
            if key_filename:
                log.debug('Using {0} as the key_filename'.format(key_filename))
                kwargs['key_filename'] = key_filename
            elif password:
                log.debug('Using {0} as the password'.format(password))
                kwargs['password'] = password

            if not remote_exists(tmp_dir):
                ret = root_cmd(('sh -c "( mkdir -p \\"{0}\\" &&'
                                ' chmod 700 \\"{0}\\" )"').format(tmp_dir),
                               tty, sudo, **kwargs)
                if ret:
                    raise SaltCloudSystemExit(
                        'Cant create temporary '
                        'directory in {0} !'.format(tmp_dir)
                    )
            if sudo:
                comps = tmp_dir.lstrip('/').rstrip('/').split('/')
                if len(comps) > 0:
                    if len(comps) > 1 or comps[0] != 'tmp':
                        ret = root_cmd(
                            'chown {0}. {1}'.format(username, tmp_dir),
                            tty, sudo, **kwargs
                        )
                        if ret:
                            raise SaltCloudSystemExit(
                                'Cant set {0} ownership on {1}'.format(
                                    username, tmp_dir))

            # Minion configuration
            if minion_pem:
                scp_file('{0}/minion.pem'.format(tmp_dir), minion_pem, kwargs)
                ret = root_cmd('chmod 600 {0}/minion.pem'.format(tmp_dir),
                               tty, sudo, **kwargs)
                if ret:
                    raise SaltCloudSystemExit(
                        'Cant set perms on {0}/minion.pem'.format(tmp_dir))
            if minion_pub:
                scp_file('{0}/minion.pub'.format(tmp_dir), minion_pub, kwargs)

            if minion_conf:
                if not isinstance(minion_conf, dict):
                    # Let's not just fail regarding this change, specially
                    # since we can handle it
                    raise DeprecationWarning(
                        '`salt.utils.cloud.deploy_script now only accepts '
                        'dictionaries for it\'s `minion_conf` parameter. '
                        'Loading YAML...'
                    )
                minion_grains = minion_conf.pop('grains', {})
                if minion_grains:
                    scp_file(
                        '{0}/grains'.format(tmp_dir),
                        salt_config_to_yaml(minion_grains),
                        kwargs
                    )
                scp_file(
                    '{0}/minion'.format(tmp_dir),
                    salt_config_to_yaml(minion_conf),
                    kwargs
                )

            # Master configuration
            if master_pem:
                scp_file('{0}/master.pem'.format(tmp_dir), master_pem, kwargs)
                ret = root_cmd('chmod 600 {0}/master.pem'.format(tmp_dir),
                               tty, sudo, **kwargs)
                if ret:
                    raise SaltCloudSystemExit(
                        'Cant set perms on {0}/master.pem'.format(tmp_dir))

            if master_pub:
                scp_file('{0}/master.pub'.format(tmp_dir), master_pub, kwargs)

            if master_conf:
                if not isinstance(master_conf, dict):
                    # Let's not just fail regarding this change, specially
                    # since we can handle it
                    raise DeprecationWarning(
                        '`salt.utils.cloud.deploy_script now only accepts '
                        'dictionaries for it\'s `master_conf` parameter. '
                        'Loading from YAML ...'
                    )

                scp_file(
                    '{0}/master'.format(tmp_dir),
                    salt_config_to_yaml(master_conf),
                    kwargs
                )

            # XXX: We need to make these paths configurable
            preseed_minion_keys_tempdir = '{0}/preseed-minion-keys'.format(
                tmp_dir)
            if preseed_minion_keys is not None:
                # Create remote temp dir
                ret = root_cmd(
                    'mkdir "{0}"'.format(preseed_minion_keys_tempdir),
                    tty, sudo, **kwargs
                )
                if ret:
                    raise SaltCloudSystemExit(
                        'Cant create {0}'.format(preseed_minion_keys_tempdir))
                ret = root_cmd(
                    'chmod 700 "{0}"'.format(preseed_minion_keys_tempdir),
                    tty, sudo, **kwargs
                )
                if ret:
                    raise SaltCloudSystemExit(
                        'Cant set perms on {0}'.format(
                            preseed_minion_keys_tempdir))
                if kwargs['username'] != 'root':
                    root_cmd(
                        'chown {0} "{1}"'.format(
                            kwargs['username'], preseed_minion_keys_tempdir
                        ),
                        tty, sudo, **kwargs
                    )

                # Copy pre-seed minion keys
                for minion_id, minion_key in preseed_minion_keys.iteritems():
                    rpath = os.path.join(
                        preseed_minion_keys_tempdir, minion_id
                    )
                    scp_file(rpath, minion_key, kwargs)

                if kwargs['username'] != 'root':
                    root_cmd(
                        'chown -R root \\"{0}\\"'.format(
                            preseed_minion_keys_tempdir
                        ),
                        tty, sudo, **kwargs
                    )
                    if ret:
                        raise SaltCloudSystemExit(
                            'Cant set owneship for {0}'.format(
                                preseed_minion_keys_tempdir))

            # The actual deploy script
            if script:
                # got strange escaping issues with sudoer, going onto a
                # subshell fixes that
                scp_file('{0}/deploy.sh'.format(tmp_dir), script, kwargs)
                ret = root_cmd(
                    ('sh -c "( chmod +x \\"{0}/deploy.sh\\" )";'
                     'exit $?').format(tmp_dir),
                    tty, sudo, **kwargs)
                if ret:
                    raise SaltCloudSystemExit(
                        'Cant set perms on {0}/deploy.sh'.format(tmp_dir))

            newtimeout = timeout - (time.mktime(time.localtime()) - starttime)
            queue = None
            process = None
            # Consider this code experimental. It causes Salt Cloud to wait
            # for the minion to check in, and then fire a startup event.
            # Disabled if parallel because it doesn't work!
            if start_action and not parallel:
                queue = multiprocessing.Queue()
                process = multiprocessing.Process(
                    target=check_auth, kwargs=dict(
                        name=name, pub_key=pub_key, sock_dir=sock_dir,
                        timeout=newtimeout, queue=queue
                    )
                )
                log.debug('Starting new process to wait for salt-minion')
                process.start()

            # Run the deploy script
            if script:
                if 'bootstrap-salt' in script:
                    deploy_command += ' -c {0}'.format(tmp_dir)
                    if make_syndic is True:
                        deploy_command += ' -S'
                    if make_master is True:
                        deploy_command += ' -M'
                    if make_minion is False:
                        deploy_command += ' -N'
                    if keep_tmp is True:
                        deploy_command += ' -K'
                    if preseed_minion_keys is not None:
                        deploy_command += ' -k {0}'.format(
                            preseed_minion_keys_tempdir
                        )
                if script_args:
                    deploy_command += ' {0}'.format(script_args)

                if script_env:
                    if not isinstance(script_env, dict):
                        raise SaltCloudSystemExit(
                            'The \'script_env\' configuration setting NEEDS '
                            'to be a dictionary not a {0}'.format(
                                type(script_env)
                            )
                        )
                    environ_script_contents = ['#!/bin/sh']
                    for key, value in script_env.iteritems():
                        environ_script_contents.append(
                            'setenv {0} \'{1}\' >/dev/null 2>&1 || '
                            'export {0}=\'{1}\''.format(key, value)
                        )
                    environ_script_contents.append(deploy_command)

                    # Upload our environ setter wrapper
                    scp_file(
                        '{0}/environ-deploy-wrapper.sh'.format(tmp_dir),
                        '\n'.join(environ_script_contents),
                        kwargs
                    )
                    root_cmd(
                        'chmod +x {0}/environ-deploy-wrapper.sh'.format(tmp_dir),
                        tty, sudo, **kwargs
                    )
                    # The deploy command is now our wrapper
                    deploy_command = '{0}/environ-deploy-wrapper.sh'.format(
                        tmp_dir,
                    )
                if root_cmd(deploy_command, tty, sudo, **kwargs) != 0:
                    raise SaltCloudSystemExit(
                        'Executing the command {0!r} failed'.format(
                            deploy_command
                        )
                    )
                log.debug('Executed command {0!r}'.format(deploy_command))

                # Remove the deploy script
                if not keep_tmp:
                    root_cmd('rm -f {0}/deploy.sh'.format(tmp_dir),
                             tty, sudo, **kwargs)
                    log.debug('Removed {0}/deploy.sh'.format(tmp_dir))
                    if script_env:
                        root_cmd(
                            'rm -f {0}/environ-deploy-wrapper.sh'.format(
                                tmp_dir
                            ),
                            tty, sudo, **kwargs
                        )
                        log.debug(
                            'Removed {0}/environ-deploy-wrapper.sh'.format(
                                tmp_dir
                            )
                        )

            if keep_tmp:
                log.debug(
                    'Not removing deployment files from {0}/'.format(tmp_dir)
                )
            else:
                # Remove minion configuration
                if minion_pub:
                    root_cmd('rm -f {0}/minion.pub'.format(tmp_dir),
                             tty, sudo, **kwargs)
                    log.debug('Removed {0}/minion.pub'.format(tmp_dir))
                if minion_pem:
                    root_cmd('rm -f {0}/minion.pem'.format(tmp_dir),
                             tty, sudo, **kwargs)
                    log.debug('Removed {0}/minion.pem'.format(tmp_dir))
                if minion_conf:
                    root_cmd('rm -f {0}/grains'.format(tmp_dir),
                             tty, sudo, **kwargs)
                    log.debug('Removed {0}/grains'.format(tmp_dir))
                    root_cmd('rm -f {0}/minion'.format(tmp_dir),
                             tty, sudo, **kwargs)
                    log.debug('Removed {0}/minion'.format(tmp_dir))

                # Remove master configuration
                if master_pub:
                    root_cmd('rm -f {0}/master.pub'.format(tmp_dir),
                             tty, sudo, **kwargs)
                    log.debug('Removed {0}/master.pub'.format(tmp_dir))
                if master_pem:
                    root_cmd('rm -f {0}/master.pem'.format(tmp_dir),
                             tty, sudo, **kwargs)
                    log.debug('Removed {0}/master.pem'.format(tmp_dir))
                if master_conf:
                    root_cmd('rm -f {0}/master'.format(tmp_dir),
                             tty, sudo, **kwargs)
                    log.debug('Removed {0}/master'.format(tmp_dir))

                # Remove pre-seed keys directory
                if preseed_minion_keys is not None:
                    root_cmd(
                        'rm -rf {0}'.format(
                            preseed_minion_keys_tempdir
                        ), tty, sudo, **kwargs
                    )
                    log.debug(
                        'Removed {0}'.format(preseed_minion_keys_tempdir)
                    )

            if start_action and not parallel:
                queuereturn = queue.get()
                process.join()
                if queuereturn and start_action:
                    #client = salt.client.LocalClient(conf_file)
                    #output = client.cmd_iter(
                    #    host, 'state.highstate', timeout=timeout
                    #)
                    #for line in output:
                    #    print(line)
                    log.info(
                        'Executing {0} on the salt-minion'.format(
                            start_action
                        )
                    )
                    root_cmd(
                        'salt-call {0}'.format(start_action),
                        tty, sudo, **kwargs
                    )
                    log.info(
                        'Finished executing {0} on the salt-minion'.format(
                            start_action
                        )
                    )
            # Fire deploy action
            fire_event(
                'event',
                '{0} has been deployed at {1}'.format(name, host),
                'salt/cloud/{0}/deploy_script'.format(name),
                {
                    'name': name,
                    'host': host
                },
                transport=opts.get('transport', 'zeromq')
            )
            return True
    return False


def fire_event(key, msg, tag, args=None, sock_dir=None, transport='zeromq'):
    # Fire deploy action
    if sock_dir is None:
        sock_dir = os.path.join(syspaths.SOCK_DIR, 'master')
    event = salt.utils.event.get_event(
            'master',
            sock_dir,
            transport,
            listen=False)
    try:
        event.fire_event(msg, tag)
    except ValueError:
        # We're using develop or a 0.17.x version of salt
        if type(args) is dict:
            args[key] = msg
        else:
            args = {key: msg}
        event.fire_event(args, tag)

    # https://github.com/zeromq/pyzmq/issues/173#issuecomment-4037083
    # Assertion failed: get_load () == 0 (poller_base.cpp:32)
    time.sleep(0.025)


def _exec_ssh_cmd(cmd,
                  error_msg='Failed to execute command {0!r}: {1}\n{2}',
                  **kwargs):
    password_retries = kwargs.get('password_retries', 3)
    error_msg = (
        'A wrong password has been issued while establishing ssh session')
    try:
        stdout, stderr = None, None
        proc = vt.Terminal(
            cmd,
            shell=True,
            log_stdout=True,
            log_stderr=True,
            stream_stdout=kwargs.get('display_ssh_output', True),
            stream_stderr=kwargs.get('display_ssh_output', True))
        sent_password = 0
        while proc.isalive():
            stdout, stderr = proc.recv()
            if stdout and SSH_PASSWORD_PROMP_RE.search(stdout):
                if (
                    kwargs.get('password', None)
                    and (sent_password < password_retries)
                ):
                    sent_password += 1
                    proc.sendline(kwargs['password'])
                else:
                    raise SaltCloudPasswordError(error_msg)
            # 0.0125 is really too fast on some systems
            time.sleep(0.5)
        return proc.exitstatus
    except vt.TerminalException as err:
        trace = traceback.format_exc()
        log.error(error_msg.format(cmd, err, trace))
    finally:
        proc.terminate()
    # Signal an error
    return 1


def scp_file(dest_path, contents, kwargs):
    '''
    Use scp to copy a file to a server
    '''
    tmpfh, tmppath = tempfile.mkstemp()
    with salt.utils.fopen(tmppath, 'w') as tmpfile:
        tmpfile.write(contents)

    log.debug('Uploading {0} to {1} (scp)'.format(dest_path, kwargs['hostname']))

    ssh_args = [
        # Don't add new hosts to the host key database
        '-oStrictHostKeyChecking=no',
        # Set hosts key database path to /dev/null, ie, non-existing
        '-oUserKnownHostsFile=/dev/null',
        # Don't re-use the SSH connection. Less failures.
        '-oControlPath=none'
    ]
    if 'key_filename' in kwargs:
        # There should never be both a password and an ssh key passed in, so
        ssh_args.extend([
            # tell SSH to skip password authentication
            '-oPasswordAuthentication=no',
            '-oChallengeResponseAuthentication=no',
            # Make sure public key authentication is enabled
            '-oPubkeyAuthentication=yes',
            # No Keyboard interaction!
            '-oKbdInteractiveAuthentication=no',
            # Also, specify the location of the key file
            '-i {0}'.format(kwargs['key_filename'])
        ])

    if 'port' in kwargs:
        ssh_args.extend(['-P {0}'.format(kwargs['port'])])

    if 'ssh_gateway' in kwargs:
        ssh_gateway = kwargs['ssh_gateway']
        ssh_gateway_port = 22
        ssh_gateway_key = ''
        ssh_gateway_user = 'root'
        if ':' in ssh_gateway:
            ssh_gateway, ssh_gateway_port = ssh_gateway.split(':')
        if 'ssh_gateway_port' in kwargs:
            ssh_gateway_port = kwargs['ssh_gateway_port']
        if 'ssh_gateway_key' in kwargs:
            ssh_gateway_key = '-i {0}'.format(kwargs['ssh_gateway_key'])
        if 'ssh_gateway_user' in kwargs:
            ssh_gateway_user = kwargs['ssh_gateway_user']

        ssh_args.extend([
            # Setup ProxyCommand
            '-oProxyCommand="ssh {0} {1} {2} {3} {4}@{5} -p {6} nc -q0 %h %p"'.format(
            # Don't add new hosts to the host key database
            '-oStrictHostKeyChecking=no',
            # Set hosts key database path to /dev/null, ie, non-existing
            '-oUserKnownHostsFile=/dev/null',
            # Don't re-use the SSH connection. Less failures.
            '-oControlPath=none',
                ssh_gateway_key,
                ssh_gateway_user,
                ssh_gateway,
                ssh_gateway_port
            )
        ])

    cmd = 'scp {0} {1} {2[username]}@{2[hostname]}:{3}'.format(
        ' '.join(ssh_args), tmppath, kwargs, dest_path
    )
    log.debug('SCP command: {0!r}'.format(cmd))
    retcode = _exec_ssh_cmd(cmd,
                            error_msg='Failed to upload file {0!r}: {1}\n{2}',
                            **kwargs)
    return retcode


def smb_file(dest_path, contents, kwargs):
    '''
    Use smbclient to copy a file to a server
    '''
    tmpfh, tmppath = tempfile.mkstemp()
    with salt.utils.fopen(tmppath, 'w') as tmpfile:
        tmpfile.write(contents)

    log.debug('Uploading {0} to {1} (smbclient)'.format(
        dest_path, kwargs['hostname'])
    )

    # Shell out to smbclient
    comps = tmppath.split('/')
    src_dir = '/'.join(comps[:-1])
    src_file = comps[-1]
    comps = dest_path.split('\\')
    dest_dir = '\\'.join(comps[:-1])
    dest_file = comps[-1]
    cmd = 'smbclient {0}/c$ -c "cd {3}; prompt; lcd {1}; del {4}; mput {2}; rename {2} {4}; exit;"'.format(
        kwargs['creds'], src_dir, src_file, dest_dir, dest_file
    )
    log.debug('SCP command: {0!r}'.format(cmd))
    win_cmd(cmd)


def win_cmd(command, **kwargs):
    '''
    Wrapper for commands to be run against Windows boxes
    '''
    try:
        proc = NonBlockingPopen(
            command,
            shell=True,
            stderr=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stream_stds=kwargs.get('display_ssh_output', True),
        )
        log.debug(
            'Executing command(PID {0}): {1!r}'.format(
                proc.pid, command
            )
        )
        proc.poll_and_read_until_finish()
        proc.communicate()
        return proc.returncode
    except Exception as err:
        log.error(
            'Failed to execute command {0!r}: {1}\n'.format(
                command, err
            ),
            exc_info=True
        )
    # Signal an error
    return 1


def root_cmd(command, tty, sudo, **kwargs):
    '''
    Wrapper for commands to be run as root
    '''
    if sudo:
        if 'sudo_password' in kwargs and kwargs['sudo_password'] is not None:
            command = 'echo "{1}" | sudo -S {0}'.format(
                command,
                kwargs['sudo_password'],
            )
        else:
            command = 'sudo {0}'.format(command)
        log.debug('Using sudo to run command {0}'.format(command))

    ssh_args = []

    if tty:
        # Use double `-t` on the `ssh` command, it's necessary when `sudo` has
        # `requiretty` enforced.
        ssh_args.extend(['-t', '-t'])

    ssh_args.extend([
        # Don't add new hosts to the host key database
        '-oStrictHostKeyChecking=no',
        # Set hosts key database path to /dev/null, ie, non-existing
        '-oUserKnownHostsFile=/dev/null',
        # Don't re-use the SSH connection. Less failures.
        '-oControlPath=none'
    ])

    if 'key_filename' in kwargs:
        # There should never be both a password and an ssh key passed in, so
        ssh_args.extend([
            # tell SSH to skip password authentication
            '-oPasswordAuthentication=no',
            '-oChallengeResponseAuthentication=no',
            # Make sure public key authentication is enabled
            '-oPubkeyAuthentication=yes',
            # No Keyboard interaction!
            '-oKbdInteractiveAuthentication=no',
            # Also, specify the location of the key file
            '-i {0}'.format(kwargs['key_filename'])
        ])

    if 'ssh_gateway' in kwargs:
        ssh_gateway = kwargs['ssh_gateway']
        ssh_gateway_port = 22
        ssh_gateway_key = ''
        ssh_gateway_user = 'root'
        if ':' in ssh_gateway:
            ssh_gateway, ssh_gateway_port = ssh_gateway.split(':')
        if 'ssh_gateway_port' in kwargs:
            ssh_gateway_port = kwargs['ssh_gateway_port']
        if 'ssh_gateway_key' in kwargs:
            ssh_gateway_key = '-i {0}'.format(kwargs['ssh_gateway_key'])
        if 'ssh_gateway_user' in kwargs:
            ssh_gateway_user = kwargs['ssh_gateway_user']

        ssh_args.extend([
            # Setup ProxyCommand
            '-oProxyCommand="ssh {0} {1} {2} {3} {4}@{5} -p {6} nc -q0 %h %p"'.format(
                # Don't add new hosts to the host key database
                '-oStrictHostKeyChecking=no',
                # Set hosts key database path to /dev/null, ie, non-existing
                '-oUserKnownHostsFile=/dev/null',
                # Don't re-use the SSH connection. Less failures.
                '-oControlPath=none',
                ssh_gateway_key,
                ssh_gateway_user,
                ssh_gateway,
                ssh_gateway_port
            )
        ])
        log.info(
            'Using SSH gateway {0}@{1}:{2}'.format(
                ssh_gateway_user, ssh_gateway, ssh_gateway_port
            )
        )

    if 'port' in kwargs:
        ssh_args.extend(['-p {0}'.format(kwargs['port'])])

    cmd = 'ssh {0} {1[username]}@{1[hostname]} {2}'.format(
        ' '.join(ssh_args), kwargs, pipes.quote(command)
    )
    log.debug('SSH command: {0!r}'.format(cmd))
    retcode = _exec_ssh_cmd(cmd, **kwargs)
    return retcode


def check_auth(name, pub_key=None, sock_dir=None, queue=None, timeout=300):
    '''
    This function is called from a multiprocess instance, to wait for a minion
    to become available to receive salt commands
    '''
    event = salt.utils.event.SaltEvent('master', sock_dir)
    starttime = time.mktime(time.localtime())
    newtimeout = timeout
    log.debug(
        'In check_auth, waiting for {0} to become available'.format(
            name
        )
    )
    while newtimeout > 0:
        newtimeout = timeout - (time.mktime(time.localtime()) - starttime)
        ret = event.get_event(full=True)
        if ret is None:
            continue
        if ret['tag'] == 'minion_start' and ret['data']['id'] == name:
            queue.put(name)
            newtimeout = 0
            log.debug('Minion {0} is ready to receive commands'.format(name))


def ip_to_int(ip):
    '''
    Converts an IP address to an integer
    '''
    ret = 0
    for octet in ip.split('.'):
        ret = ret * 256 + int(octet)
    return ret


def is_public_ip(ip):
    '''
    Determines whether an IP address falls within one of the private IP ranges
    '''
    addr = ip_to_int(ip)
    if addr > 167772160 and addr < 184549375:
        # 10.0.0.0/24
        return False
    elif addr > 3232235520 and addr < 3232301055:
        # 192.168.0.0/16
        return False
    elif addr > 2886729728 and addr < 2887778303:
        # 172.16.0.0/12
        return False
    return True


def check_name(name, safe_chars):
    '''
    Check whether the specified name contains invalid characters
    '''
    regexp = re.compile('[^{0}]'.format(safe_chars))
    if regexp.search(name):
        raise SaltCloudException(
            '{0} contains characters not supported by this cloud provider. '
            'Valid characters are: {1}'.format(
                name, safe_chars
            )
        )


def remove_sshkey(host, known_hosts=None):
    '''
    Remove a host from the known_hosts file
    '''
    if known_hosts is None:
        if 'HOME' in os.environ:
            known_hosts = '{0}/.ssh/known_hosts'.format(os.environ['HOME'])
        else:
            try:
                known_hosts = '{0}/.ssh/known_hosts'.format(
                    pwd.getpwuid(os.getuid()).pwd_dir
                )
            except Exception:
                pass

    if known_hosts is not None:
        log.debug(
            'Removing ssh key for {0} from known hosts file {1}'.format(
                host, known_hosts
            )
        )
    else:
        log.debug(
            'Removing ssh key for {0} from known hosts file'.format(host)
        )

    cmd = 'ssh-keygen -R {0}'.format(host)
    subprocess.call(cmd, shell=True)


def wait_for_ip(update_callback,
                update_args=None,
                update_kwargs=None,
                timeout=5 * 60,
                interval=5,
                interval_multiplier=1,
                max_failures=10):
    '''
    Helper function that waits for an IP address for a specific maximum amount
    of time.

    :param update_callback: callback function which queries the cloud provider
                            for the VM ip address. It must return None if the
                            required data, IP included, is not available yet.
    :param update_args: Arguments to pass to update_callback
    :param update_kwargs: Keyword arguments to pass to update_callback
    :param timeout: The maximum amount of time(in seconds) to wait for the IP
                    address.
    :param interval: The looping interval, ie, the amount of time to sleep
                     before the next iteration.
    :param interval_multiplier: Increase the interval by this multiplier after
                                each request; helps with throttling
    :param max_failures: If update_callback returns ``False`` it's considered
                         query failure. This value is the amount of failures
                         accepted before giving up.
    :returns: The update_callback returned data
    :raises: SaltCloudExecutionTimeout

    '''
    if update_args is None:
        update_args = ()
    if update_kwargs is None:
        update_kwargs = {}

    duration = timeout
    while True:
        log.debug(
            'Waiting for VM IP. Giving up in 00:{0:02d}:{1:02d}'.format(
                int(timeout // 60),
                int(timeout % 60)
            )
        )
        data = update_callback(*update_args, **update_kwargs)
        if data is False:
            log.debug(
                'update_callback has returned False which is considered a '
                'failure. Remaining Failures: {0}'.format(max_failures)
            )
            max_failures -= 1
            if max_failures <= 0:
                raise SaltCloudExecutionFailure(
                    'Too much failures occurred while waiting for '
                    'the IP address'
                )
        elif data is not None:
            return data

        if timeout < 0:
            raise SaltCloudExecutionTimeout(
                'Unable to get IP for 00:{0:02d}:{1:02d}'.format(
                    int(duration // 60),
                    int(duration % 60)
                )
            )
        time.sleep(interval)
        timeout -= interval

        if interval_multiplier > 1:
            interval *= interval_multiplier
            if interval > timeout:
                interval = timeout + 1
            log.info('Interval multiplier in effect; interval is '
                     'now {0}s'.format(interval))


def simple_types_filter(datadict):
    '''
    Convert the data dictionary into simple types, ie, int, float, string,
    bool, etc.
    '''
    if not isinstance(datadict, dict):
        # This function is only supposed to work on dictionaries
        return datadict

    simpletypes_keys = (str, unicode, int, long, float, bool)
    simpletypes_values = tuple(list(simpletypes_keys) + [list, tuple])
    simpledict = {}
    for key, value in datadict.iteritems():
        if key is not None and not isinstance(key, simpletypes_keys):
            key = repr(key)
        if value is not None and isinstance(value, dict):
            value = simple_types_filter(value)
        elif value is not None and not isinstance(value, simpletypes_values):
            value = repr(value)
        simpledict[key] = value
    return simpledict


def list_nodes_select(nodes, selection, call=None):
    '''
    Return a list of the VMs that are on the provider, with select fields
    '''
    if call == 'action':
        raise SaltCloudSystemExit(
            'The list_nodes_select function must be called '
            'with -f or --function.'
        )

    if 'error' in nodes:
        raise SaltCloudSystemExit(
            'An error occurred while listing nodes: {0}'.format(
                nodes['error']['Errors']['Error']['Message']
            )
        )

    ret = {}
    for node in nodes:
        pairs = {}
        data = nodes[node]
        for key in data:
            if str(key) in selection:
                value = data[key]
                pairs[key] = value
        ret[node] = pairs

    return ret


def init_cachedir(base=None):
    '''
    Initialize the cachedir needed for Salt Cloud to keep track of minions
    '''
    if base is None:
        base = os.path.join(syspaths.CACHE_DIR, 'cloud')
    needed_dirs = (base,
                   os.path.join(base, 'requested'),
                   os.path.join(base, 'active'))
    for dir_ in needed_dirs:
        if not os.path.exists(dir_):
            os.makedirs(dir_)
        os.chmod(base, 0755)


def request_minion_cachedir(
        minion_id,
        fingerprint='',
        pubkey=None,
        provider=None,
        base=None,
    ):
    '''
    Creates an entry in the requested/ cachedir. This means that Salt Cloud has
    made a request to a cloud provider to create an instance, but it has not
    yet verified that the instance properly exists.

    If the fingerprint is unknown, a raw pubkey can be passed in, and a
    fingerprint will be calculated. If both are empty, then the fingerprint
    will be set to None.
    '''
    if base is None:
        base = os.path.join(syspaths.CACHE_DIR, 'cloud')

    if not fingerprint:
        if pubkey is not None:
            fingerprint = salt.utils.pem_finger(key=pubkey)

    init_cachedir(base)

    data = {
        'minion_id': minion_id,
        'fingerprint': fingerprint,
        'provider': provider,
    }

    fname = '{0}.json'.format(minion_id)
    path = os.path.join(base, 'requested', fname)
    with salt.utils.fopen(path, 'w') as fh_:
        json.dump(data, fh_)


def change_minion_cachedir(
        minion_id,
        cachedir,
        data=None,
        base=None,
    ):
    '''
    Changes the info inside a minion's cachedir entry. The type of cachedir
    must be specified (i.e., 'requested' or 'active'). A dict is also passed in
    which contains the data to be changed.

    Example:

        change_minion_cachedir(
            'myminion',
            'requested',
            {'fingerprint': '26:5c:8c:de:be:fe:89:c0:02:ed:27:65:0e:bb:be:60'},
        )
    '''
    if not isinstance(data, dict):
        return False

    if base is None:
        base = os.path.join(syspaths.CACHE_DIR, 'cloud')

    fname = '{0}.json'.format(minion_id)
    path = os.path.join(base, cachedir, fname)

    with salt.utils.fopen(path, 'r') as fh_:
        cache_data = json.load(fh_)

    cache_data.update(data)

    with salt.utils.fopen(path, 'w') as fh_:
        json.dump(cache_data, fh_)


def activate_minion_cachedir(minion_id, base=None):
    '''
    Moves a minion from the requested/ cachedir into the active/ cachedir. This
    means that Salt Cloud has verified that a requested instance properly
    exists, and should be expected to exist from here on out.
    '''
    if base is None:
        base = os.path.join(syspaths.CACHE_DIR, 'cloud')

    fname = '{0}.json'.format(minion_id)
    src = os.path.join(base, 'requested', fname)
    dst = os.path.join(base, 'active')
    shutil.move(src, dst)


def delete_minion_cachedir(minion_id, base=None):
    '''
    Deletes a minion's entry from the cloud cachedir. It will search through
    all cachedirs to find the minion's cache file.
    '''
    if base is None:
        base = os.path.join(syspaths.CACHE_DIR, 'cloud')

    fname = '{0}.json'.format(minion_id)
    for cachedir in ('requested', 'active'):
        path = os.path.join(base, cachedir, fname)
        if os.path.exists(path):
            os.remove(path)


def update_bootstrap(config):
    '''
    Update the salt-bootstrap script
    '''
    log.debug('Updating the bootstrap-salt.sh script to latest stable')
    try:
        import requests
    except ImportError:
        return {'error': (
            'Updating the bootstrap-salt.sh script requires the '
            'Python requests library to be installed'
        )}
    url = 'https://raw.githubusercontent.com/saltstack/salt-bootstrap/stable/bootstrap-salt.sh'
    req = requests.get(url)
    if req.status_code != 200:
        return {'error': (
            'Failed to download the latest stable version of the '
            'bootstrap-salt.sh script from {0}. HTTP error: '
            '{1}'.format(
                url, req.status_code
            )
        )}

    # Get the path to the built-in deploy scripts directory
    builtin_deploy_dir = os.path.join(
        os.path.dirname(__file__),
        'deploy'
    )

    # Compute the search path from the current loaded opts conf_file
    # value
    deploy_d_from_conf_file = os.path.join(
        os.path.dirname(config['conf_file']),
        'cloud.deploy.d'
    )

    # Compute the search path using the install time defined
    # syspaths.CONF_DIR
    deploy_d_from_syspaths = os.path.join(
        syspaths.CONFIG_DIR,
        'cloud.deploy.d'
    )

    # Get a copy of any defined search paths, flagging them not to
    # create parent
    deploy_scripts_search_paths = []
    for entry in config.get('deploy_scripts_search_path', []):
        if entry.startswith(builtin_deploy_dir):
            # We won't write the updated script to the built-in deploy
            # directory
            continue

        if entry in (deploy_d_from_conf_file, deploy_d_from_syspaths):
            # Allow parent directories to be made
            deploy_scripts_search_paths.append((entry, True))
        else:
            deploy_scripts_search_paths.append((entry, False))

    # In case the user is not using defaults and the computed
    # 'cloud.deploy.d' from conf_file and syspaths is not included, add
    # them
    if deploy_d_from_conf_file not in deploy_scripts_search_paths:
        deploy_scripts_search_paths.append(
            (deploy_d_from_conf_file, True)
        )
    if deploy_d_from_syspaths not in deploy_scripts_search_paths:
        deploy_scripts_search_paths.append(
            (deploy_d_from_syspaths, True)
        )

    finished = []
    finished_full = []
    for entry, makedirs in deploy_scripts_search_paths:
        # This handles duplicate entries, which are likely to appear
        if entry in finished:
            continue
        else:
            finished.append(entry)

        if makedirs and not os.path.isdir(entry):
            try:
                os.makedirs(entry)
            except (OSError, IOError) as err:
                log.info(
                    'Failed to create directory {0!r}'.format(entry)
                )
                continue

        if not is_writeable(entry):
            log.debug(
                'The {0!r} is not writeable. Continuing...'.format(
                    entry
                )
            )
            continue

        deploy_path = os.path.join(entry, 'bootstrap-salt.sh')
        try:
            finished_full.append(deploy_path)
            with salt.utils.fopen(deploy_path, 'w') as fp_:
                fp_.write(req.text)
        except (OSError, IOError) as err:
            log.debug(
                'Failed to write the updated script: {0}'.format(err)
            )
            continue

    return {'Success': {'Files updated': finished_full}}


def _salt_cloud_force_ascii(exc):
    '''
    Helper method to try its best to convert any Unicode text into ASCII
    without stack tracing since salt internally does not handle Unicode strings

    This method is not supposed to be used directly. Once
    `py:module: salt.utils.cloud` is imported this method register's with
    python's codecs module for proper automatic conversion in case of encoding
    errors.
    '''
    if not isinstance(exc, (UnicodeEncodeError, UnicodeTranslateError)):
        raise TypeError('Can\'t handle {0}'.format(exc))

    unicode_trans = {
        u'\xa0': u' ',   # Convert non-breaking space to space
        u'\u2013': u'-',  # Convert en dash to dash
    }

    if exc.object[exc.start:exc.end] in unicode_trans:
        return unicode_trans[exc.object[exc.start:exc.end]], exc.end

    # There's nothing else we can do, raise the exception
    raise exc

codecs.register_error('salt-cloud-force-ascii', _salt_cloud_force_ascii)


def retrieve_password_from_keyring(credential_id, username):
    '''
    Retrieve particular user's password for a specified credential set from system keyring.
    '''
    try:
        import keyring
        return keyring.get_password(credential_id, username)
    except ImportError:
        log.error('USE_KEYRING configured as a password, but no keyring module is installed')
        return False


def _save_password_in_keyring(credential_id, username, password):
    '''
    Saves provider password in system keyring
    '''
    try:
        import keyring
        return keyring.set_password(credential_id, username, password)
    except ImportError:
        log.error('Tried to store password in keyring, but no keyring module is installed')
        return False


def store_password_in_keyring(credential_id, username, password=None):
    '''
    Interactively prompts user for a password and stores it in system keyring
    '''
    try:
        import keyring
        import keyring.errors
        if password is None:
            prompt = 'Please enter password for {0}: '.format(credential_id)
            try:
                password = getpass.getpass(prompt)
            except EOFError:
                password = None

            if not password:
                # WE should raise something else here to be able to use this
                # as/from an API
                raise RuntimeError('Invalid password provided.')

        try:
            _save_password_in_keyring(credential_id, username, password)
        except keyring.errors.PasswordSetError as exc:
            log.debug('Problem saving password in the keyring: {0}'.format(exc))
    except ImportError:
        log.error('Tried to store password in keyring, but no keyring module is installed')
        return False
