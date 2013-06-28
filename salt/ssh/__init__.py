'''
Create ssh executor system
'''
# Import python libs
import multiprocessing

# Import salt libs
import salt.ssh.shell

class SSH(object):
    '''
    Create an ssh execution system
    '''
    def __init__(self, opts):
        self.opts = opts


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
            host,
            user=None,
            port=None,
            passwd=None,
            priv=None,
            timeout=None,
            sudo=False):
        self.opts = opts
        self.arg_str = arg_str
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
               'if [ `which salt-call` ]\n'
               'then\n'
               '    SALT=salt-call\n'
               'elif [ -f /tmp/salt-thin/salt-call] \n'
               'then\n'
               '    SALT=/tmp/salt-thin/salt-call\n'
               'else\n'
               '    echo "deploy"\n'
               '    exit 1\n'
               '$PYTHON $SALT --local -l quiet {0}\n'
               'EOF').format(self.arg_std)
        ret = self.shell.exec_cmd(cmd)
        if ret.startswith('deploy'):
            self.deploy()
            return self.cmd(arg_str)
        return ret
