'''
Create ssh executor system
'''
# Import python libs
import os
import multiprocessing
import json

# Import salt libs
import salt.ssh.shell
import salt.roster

class SSH(object):
    '''
    Create an ssh execution system
    '''
    def __init__(self, opts):
        self.opts = opts
        tgt_type = self.opts['selected_target_option'] if self.opts['selected_target_option'] else 'glob'
        self.roster = salt.roster.Roster(opts)
        self.targets = self.roster.targets(
                self.opts['tgt'],
                tgt_type)
        priv_default = os.path.join(
                self.opts['pki_dir'],
                'ssh',
                'salt-ssh.rsa')
        if not os.path.isfile(priv_default):
            priv_default = ''
        self.defaults = {
                'user': self.opts.get('ssh_user', 'root'),
                'port': self.opts.get('ssh_port', '22'),
                'passwd': self.opts.get('ssh_passwd', 'passwd'),
                'priv': self.opts.get('ssh_priv', priv_default),
                'timeout': self.opts.get('ssh_timeout', 60),
                'sudo': self.opts.get('ssh_sudo', False),
                }

    def process(self):
        '''
        Execute the desired routine on the specified systems
        '''
        # TODO, this is just the code to test the chain, this is where the
        # parallel stuff needs to go once the chain is proven valid
        for target in self.targets:
            for default in self.defaults:
                if not default in self.targets[target]:
                    self.targets[target][default] = self.defaults[default]
            single = Single(
                    self.opts,
                    self.opts['arg_str'],
                    target,
                    **self.targets[target])
            yield single.cmd()

    def run(self):
        '''
        Execute the overall routine
        '''
        for ret in self.process():
            salt.output.display_output(
                    ret,
                    self.opts.get('output', 'nested'),
                    self.opts)


class Single(multiprocessing.Process):
    '''
    Hold onto a single ssh execution
    '''
    # 1. Get command ready
    # 2. Check if target has salt
    # 3. deploy salt-thin
    # 4. execute requested command via salt-thin
    def __init__(
            self,
            opts,
            arg_str,
            id_,
            host,
            user=None,
            port=None,
            passwd=None,
            priv=None,
            timeout=None,
            sudo=False,
            **kwargs):
        super(Single, self).__init__()
        self.opts = opts
        self.arg_str = arg_str
        self.id = id_
        self.extra = kwargs
        self.shell = salt.ssh.shell.Shell(
                host,
                user,
                port,
                passwd,
                priv,
                timeout,
                sudo)

    def deploy(self):
        '''
        Deploy salt-thin
        '''
        self.shell.send(
                self.opts['salt_thin_tar'],
                '/tmp/salt-thin.tgz')
        self.shell.exec_cmd(
                'tar xvf /tmp/salt-thin.tgz -C /tmp && rm /tmp/salt-thin.tgz'
                )

    def cmd(self):
        '''
        Prepare the precheck command to send to the subsystem
        '''
        # 1. check if python is on the target
        # 2. check is salt-call is on the target
        # 3. deploy salt-thin
        # 4. execute command
        cmd = (' << "EOF"\n'
               'if [ `which python2` ]\n'
               'then\n'
               '    PYTHON=python2\n'
               'elif [ `which python26` ]\n'
               'then\n'
               '    PYTHON=python26\n'
               'fi\n'
               'if hash salt-call\n'
               'then\n'
               '    SALT=$(type -p salt-call)\n'
               'elif [ -f /tmp/salt-thin/salt-call] \n'
               'then\n'
               '    SALT=/tmp/salt-thin/salt-call\n'
               'else\n'
               '    echo "deploy"\n'
               '    exit 1\n'
               'fi\n'
               '$PYTHON $SALT --local --out json -l quiet {0}\n'
               'EOF').format(self.arg_str)
        ret = self.shell.exec_cmd(cmd)
        if ret.startswith('deploy'):
            self.deploy()
            return json.loads(self.cmd(self.arg_str))
        try:
            data = json.loads(ret)
            return {self.id: data['local']}
        except Exception:
            return {self.id: 'No valid data returned'}
