'''
The management of salt command line utilities are stored in here
'''

# Import python libs
import os
import sys

# Import salt components
import salt.cli.caller
import salt.cli.cp
import salt.cli.key
import salt.cli.batch
import salt.client
import salt.output
import salt.runner

import optparse
from salt.utils import parsers
from salt.utils.verify import verify_env
from salt.version import __version__ as VERSION
from salt.exceptions import SaltInvocationError, SaltClientError, SaltException


class SaltCMD(parsers.SaltCMDOptionParser):
    '''
    The execution of a salt command happens here
    '''

    def run(self):
        '''
        Execute the salt command line
        '''
        self.parse_args()

        try:
            local = salt.client.LocalClient(self.get_config_file_path('master'))
        except SaltClientError as exc:
            self.exit(2, '{0}\n'.format(exc))
            return

        if self.options.query:
            ret = local.find_cmd(self.config['cmd'])
            for jid in ret:
                if isinstance(ret, list) or isinstance(ret, dict):
                    # Determine the proper output method and run it
                    printout = self.get_outputter()

                    print('Return data for job {0}:'.format(jid))
                    printout(ret[jid])
                    print('')
        elif self.options.batch:
            batch = salt.cli.batch.Batch(self.config)
            batch.run()
        else:
            if self.options.timeout <= 0:
                self.options.timeout = local.opts['timeout']

            args = [
                self.config['tgt'],
                self.config['fun'],
                self.config['arg'],
                self.options.timeout,
            ]

            if self.selected_target_option:
                args.append(self.selected_target_option)
            else:
                args.append('glob')

            if getattr(self.options, 'return'):
                args.append(getattr(self.options, 'return'))
            else:
                args.append('')
            try:
                # local will be None when there was an error
                if local:
                    if self.options.static:
                        if self.options.verbose:
                            args.append(True)
                        full_ret = local.cmd_full_return(*args)
                        ret, out = self._format_ret(full_ret)
                        self._output_ret(ret, out)
                    elif self.config['fun'] == 'sys.doc':
                        ret = {}
                        out = ''
                        for full_ret in local.cmd_cli(*args):
                            ret_, out = self._format_ret(full_ret)
                            ret.update(ret_)
                        self._output_ret(ret, out)
                    else:
                        if self.options.verbose:
                            args.append(True)
                        for full_ret in local.cmd_cli(*args):
                            ret, out = self._format_ret(full_ret)
                            self._output_ret(ret, out)
            except SaltInvocationError as exc:
                ret = exc
                out = ''

    def _output_ret(self, ret, out):
        '''
        Print the output from a single return to the terminal
        '''
        # Handle special case commands
        if self.config['fun'] == 'sys.doc':
            self._print_docs(ret)
        else:
            # Determine the proper output method and run it
            salt.output.display_output(ret, out, self.config)

    def _format_ret(self, full_ret):
        '''
        Take the full return data and format it to simple output
        '''
        ret = {}
        out = ''
        for key, data in full_ret.items():
            ret[key] = data['ret']
            if 'out' in data:
                out = data['out']
        return ret, out

    def _print_docs(self, ret):
        '''
        Print out the docstrings for all of the functions on the minions
        '''
        docs = {}
        if not ret:
            self.exit(2, 'No minions found to gather docs from\n')

        for host in ret:
            for fun in ret[host]:
                if fun not in docs:
                    if ret[host][fun]:
                        docs[fun] = ret[host][fun]
        for fun in sorted(docs):
            print(fun + ':')
            print(docs[fun])
            print('')


class SaltCP(parsers.SaltCPOptionParser):
    '''
    Run the salt-cp command line client
    '''

    def run(self):
        '''
        Execute salt-cp
        '''
        self.parse_args()
        cp_ = salt.cli.cp.SaltCP(self.config)
        cp_.run()


class SaltKey(parsers.SaltKeyOptionParser):
    '''
    Initialize the Salt key manager
    '''

    def run(self):
        '''
        Execute salt-key
        '''
        self.parse_args()

        verify_env([
                os.path.join(self.config['pki_dir'], 'minions'),
                os.path.join(self.config['pki_dir'], 'minions_pre'),
                os.path.join(self.config['pki_dir'], 'minions_rejected'),
                os.path.dirname(self.config['log_file']),
            ],
            self.config['user'],
            permissive=self.config['permissive_pki_access']
        )

        self.setup_logfile_logger()

        key = salt.cli.key.Key(self.config)
        key.run()


class SaltCall(parsers.SaltCallOptionParser):
    '''
    Used to locally execute a salt command
    '''

    def run(self):
        '''
        Execute the salt call!
        '''
        self.parse_args()

        verify_env([
                self.config['pki_dir'],
                self.config['cachedir'],
                os.path.dirname(self.config['log_file'])
            ],
            self.config['user'],
            permissive=self.config['permissive_pki_access']
        )

        caller = salt.cli.caller.Caller(self.config)

        if self.options.doc:
            caller.print_docs()
            self.exit(0)

        if self.options.grains_run:
            caller.print_grains()
            self.exit(0)

        caller.run()


class SaltRun(object):
    '''
    Used to execute salt convenience functions
    '''
    def __init__(self):
        self.opts = self.__parse()

    def __parse(self):
        '''
        Parse the command line arguments
        '''
        parser = optparse.OptionParser(version="%%prog %s" % VERSION)

        parser.add_option('-c',
                '--config',
                dest='conf_file',
                default='/etc/salt/master',
                help=('Change the location of the master configuration; '
                      'default=/etc/salt/master'))

        parser.add_option('-t',
                '--timeout',
                dest='timeout',
                default='1',
                help=('Change the timeout, if applicable, for the salt runner; '
                      'default=1'))

        parser.add_option('-d',
                '--doc',
                '--documentation',
                dest='doc',
                default=False,
                action='store_true',
                help=('Display documentation for runners, pass a module or '
                      'a runner to see documentation on only that '
                      'module/runner.'))

        options, args = parser.parse_args()

        opts = {}
        opts.update(salt.config.master_config(options.conf_file))
        opts['conf_file'] = options.conf_file
        opts['doc'] = options.doc
        if len(args) > 0:
            opts['fun'] = args[0]
        else:
            opts['fun'] = ''
        if len(args) > 1:
            opts['arg'] = args[1:]
        else:
            opts['arg'] = []

        return opts

    def run(self):
        '''
        Execute salt-run
        '''
        runner = salt.runner.Runner(self.opts)
        # Run this here so SystemExit isn't raised
        # anywhere else when someone tries to  use
        # the runners via the python api
        try:
            runner.run()
        except SaltClientError as exc:
            raise SystemExit(str(exc))
