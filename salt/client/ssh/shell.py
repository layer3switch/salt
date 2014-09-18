# -*- coding: utf-8 -*-
'''
Manage transport commands via ssh
'''

# Import python libs
import re
import os
import time
import logging
import subprocess

# Import salt libs
import salt.utils
import salt.utils.nb_popen
import salt.utils.vt

log = logging.getLogger(__name__)

SSH_PASSWORD_PROMPT_RE = re.compile(r'(?:.*)[Pp]assword(?: for .*)?:', re.M)
KEY_VALID_RE = re.compile(r'.*\(yes\/no\).*')


class NoPasswdError(Exception):
    pass


class KeyAcceptError(Exception):
    pass


def gen_key(path):
    '''
    Generate a key for use with salt-ssh
    '''
    cmd = 'ssh-keygen -P "" -f {0} -t rsa -q'.format(path)
    if not os.path.isdir(os.path.dirname(path)):
        os.makedirs(os.path.dirname(path))
    subprocess.call(cmd, shell=True)


class Shell(object):
    '''
    Create a shell connection object to encapsulate ssh executions
    '''
    def __init__(
            self,
            opts,
            host,
            user=None,
            port=None,
            passwd=None,
            priv=None,
            timeout=None,
            sudo=False,
            tty=False):
        self.opts = opts
        self.host = host
        self.user = user
        self.port = port
        self.passwd = str(passwd) if passwd else passwd
        self.priv = priv
        self.timeout = timeout
        self.sudo = sudo
        self.tty = tty

    def get_error(self, errstr):
        '''
        Parse out an error and return a targeted error string
        '''
        for line in errstr.split('\n'):
            if line.startswith('ssh:'):
                return line
            if line.startswith('Pseudo-terminal'):
                continue
            if 'to the list of known hosts.' in line:
                continue
            return line
        return errstr

    def _key_opts(self):
        '''
        Return options for the ssh command base for Salt to call
        '''
        options = [
                   'KbdInteractiveAuthentication=no',
                   'GSSAPIAuthentication=no',
                   'PasswordAuthentication=no',
                   ]
        options.append('ConnectTimeout={0}'.format(self.timeout))
        if self.opts.get('ignore_host_keys'):
            options.append('StrictHostKeyChecking=no')
        known_hosts = self.opts.get('known_hosts_file')
        if known_hosts and os.path.isfile(known_hosts):
            options.append('UserKnownHostsFile={0}'.format(known_hosts))
        if self.port:
            options.append('Port={0}'.format(self.port))
        if self.priv:
            options.append('IdentityFile={0}'.format(self.priv))
        if self.user:
            options.append('User={0}'.format(self.user))

        ret = []
        for option in options:
            ret.append('-o {0} '.format(option))
        return ''.join(ret)

    def _passwd_opts(self):
        '''
        Return options to pass to ssh
        '''
        # TODO ControlMaster does not work without ControlPath
        # user could take advantage of it if they set ControlPath in their
        # ssh config.  Also, ControlPersist not widely available.
        options = ['ControlMaster=auto',
                   'StrictHostKeyChecking=no',
                   'GSSAPIAuthentication=no',
                   ]
        options.append('ConnectTimeout={0}'.format(self.timeout))
        if self.opts.get('ignore_host_keys'):
            options.append('StrictHostKeyChecking=no')

        if self.passwd:
            options.extend(['PasswordAuthentication=yes',
                            'PubkeyAuthentication=yes'])
        else:
            options.extend(['PasswordAuthentication=no',
                            'PubkeyAuthentication=yes',
                            'KbdInteractiveAuthentication=no',
                            'ChallengeResponseAuthentication=no',
                            'BatchMode=yes'])
        if self.port:
            options.append('Port={0}'.format(self.port))
        if self.user:
            options.append('User={0}'.format(self.user))

        ret = []
        for option in options:
            ret.append('-o {0} '.format(option))
        return ''.join(ret)

    def _copy_id_str_old(self):
        '''
        Return the string to execute ssh-copy-id
        '''
        if self.passwd:
            # Using single quotes prevents shell expansion and
            # passwords containig '$'
            return "{0} {1} '{2} -p {3} {4}@{5}'".format(
                    'ssh-copy-id',
                    '-i {0}.pub'.format(self.priv),
                    self._passwd_opts(),
                    self.port,
                    self.user,
                    self.host)
        return None

    def _copy_id_str_new(self):
        '''
        Since newer ssh-copy-id commands ingest option differently we need to
        have two commands
        '''
        if self.passwd:
            # Using single quotes prevents shell expansion and
            # passwords containig '$'
            return "{0} {1} {2} -p {3} {4}@{5}".format(
                    'ssh-copy-id',
                    '-i {0}.pub'.format(self.priv),
                    self._passwd_opts(),
                    self.port,
                    self.user,
                    self.host)
        return None

    def copy_id(self):
        '''
        Execute ssh-copy-id to plant the id file on the target
        '''
        stdout, stderr, retcode = self._run_cmd(self._copy_id_str_old())
        if os.EX_OK != retcode and stderr.startswith('Usage'):
            stdout, stderr, retcode = self._run_cmd(self._copy_id_str_new())
        return stdout, stderr, retcode

    def _cmd_str(self, cmd, ssh='ssh'):
        '''
        Return the cmd string to execute
        '''

        # TODO: if tty, then our SSH_SHIM cannot be supplied from STDIN Will
        # need to deliver the SHIM to the remote host and execute it there

        if self.passwd:
            opts = self._passwd_opts()
        if self.priv:
            opts = self._key_opts()
        return "{0} {1} {2} {3} {4}".format(
                ssh,
                '' if ssh == 'scp' else self.host,
                '-t -t' if self.tty else '',
                opts,
                cmd)

    def _old_run_cmd(self, cmd):
        '''
        Cleanly execute the command string
        '''
        try:
            proc = subprocess.Popen(
                cmd,
                shell=True,
                stderr=subprocess.PIPE,
                stdout=subprocess.PIPE,
            )

            data = proc.communicate()
            return data[0], data[1], proc.returncode
        except Exception:
            return ('local', 'Unknown Error', None)

    def _run_nb_cmd(self, cmd):
        '''
        cmd iterator
        '''
        try:
            proc = salt.utils.nb_popen.NonBlockingPopen(
                cmd,
                shell=True,
                stderr=subprocess.PIPE,
                stdout=subprocess.PIPE,
            )
            while True:
                time.sleep(0.1)
                out = proc.recv()
                err = proc.recv_err()
                rcode = proc.returncode
                if out is None and err is None:
                    break
                if err:
                    err = self.get_error(err)
                yield out, err, rcode
        except Exception:
            yield ('', 'Unknown Error', None)

    def exec_nb_cmd(self, cmd):
        '''
        Yield None until cmd finished
        '''
        r_out = []
        r_err = []
        rcode = None
        cmd = self._cmd_str(cmd)

        logmsg = 'Executing non-blocking command: {0}'.format(cmd)
        if self.passwd:
            logmsg = logmsg.replace(self.passwd, ('*' * 6))
        log.debug(logmsg)

        for out, err, rcode in self._run_nb_cmd(cmd):
            if out is not None:
                r_out.append(out)
            if err is not None:
                r_err.append(err)
            yield None, None, None
        yield ''.join(r_out), ''.join(r_err), rcode

    def exec_cmd(self, cmd):
        '''
        Execute a remote command
        '''
        cmd = self._cmd_str(cmd)

        logmsg = 'Executing command: {0}'.format(cmd)
        if self.passwd:
            logmsg = logmsg.replace(self.passwd, ('*' * 6))
        log.debug(logmsg)

        ret = self._run_cmd(cmd)
        return ret

    def send(self, local, remote):
        '''
        scp a file or files to a remote system
        '''
        cmd = '{0} {1}:{2}'.format(local, self.host, remote)
        cmd = self._cmd_str(cmd, ssh='scp')

        logmsg = 'Executing command: {0}'.format(cmd)
        if self.passwd:
            logmsg = logmsg.replace(self.passwd, ('*' * 6))
        log.debug(logmsg)

        return self._run_cmd(cmd)

    def _run_cmd(self, cmd, key_accept=False, passwd_retries=3):
        '''
        Execute a shell command via VT. This is blocking and assumes that ssh
        is being run
        '''
        term = salt.utils.vt.Terminal(
                cmd,
                shell=True,
                log_stdout=True,
                log_stderr=True,
                stream_stdout=False,
                stream_stderr=False)
        sent_passwd = 0
        ret_stdout = ''
        ret_stderr = ''
        while True:
            stdout, stderr = term.recv()
            if stdout:
                ret_stdout += stdout
            if stderr:
                ret_stderr += stderr
            if stdout and SSH_PASSWORD_PROMPT_RE.search(stdout):
                if not self.passwd:
                    try:
                        term.close(terminate=True, kill=True)
                    except salt.utils.vt.TerminalException:
                        pass
                    return '', 'No authentication information available', 254
                if sent_passwd < passwd_retries:
                    term.sendline(self.passwd)
                    sent_passwd += 1
                    continue
                else:
                    # asking for a password, and we can't seem to send it
                    try:
                        term.close(terminate=True, kill=True)
                    except salt.utils.vt.TerminalException:
                        pass
                    return '', 'Password authentication failed', 254
            elif stdout and KEY_VALID_RE.search(stdout):
                if key_accept:
                    term.sendline('yes')
                    continue
                else:
                    term.sendline('no')
                    ret_stdout = ('The host key needs to be accepted, to '
                                  'auto accept run salt-ssh with the -i '
                                  'flag:\n{0}').format(stdout)
                    return ret_stdout, '', 254
            if not term.isalive():
                while True:
                    stdout, stderr = term.recv()
                    if stdout:
                        ret_stdout += stdout
                    if stderr:
                        ret_stderr += stderr
                    if stdout is None and stderr is None:
                        break
                term.close(terminate=True, kill=True)
                break
            time.sleep(0.5)
        return ret_stdout, ret_stderr, term.exitstatus
