'''
The caller module is used as a front-end to manage direct calls to the salt
minion modules.
'''

# Import python modules
import sys
import logging
import traceback

# Import salt libs
import salt.loader
import salt.minion
import salt.output
from salt._compat import string_types
from salt.log import LOG_LEVELS

# Custom exceptions
from salt.exceptions import (
    SaltClientError,
    CommandNotFoundError,
    CommandExecutionError,
)


class Caller(object):
    '''
    Object to wrap the calling of local salt modules for the salt-call command
    '''
    def __init__(self, opts):
        '''
        Pass in the command line options
        '''
        self.opts = opts
        # Handle this here so other deeper code which might
        # be imported as part of the salt api doesn't do  a
        # nasty sys.exit() and tick off our developer users
        try:
            self.minion = salt.minion.SMinion(opts)
        except SaltClientError as exc:
            raise SystemExit(str(exc))

    def call(self):
        '''
        Call the module
        '''
        ret = {}
        fun = self.opts['fun']

        if fun not in self.minion.functions:
            sys.stderr.write('Function {0} is not available\n'.format(fun))
            sys.exit(1)
        try:
            args, kw = salt.minion.detect_kwargs(
                self.minion.functions[fun], self.opts['arg'])
            ret['return'] = self.minion.functions[fun](*args, **kw)
        except (TypeError, CommandExecutionError) as exc:
            msg = 'Error running \'{0}\': {1}\n'
            active_level = LOG_LEVELS.get(
                self.opts['log_level'].lower, logging.ERROR)
            if active_level <= logging.DEBUG:
                sys.stderr.write(traceback.format_exc())
            sys.stderr.write(msg.format(fun, str(exc)))
            sys.exit(1)
        except CommandNotFoundError as exc:
            msg = 'Command required for \'{0}\' not found: {1}\n'
            sys.stderr.write(msg.format(fun, str(exc)))
            sys.exit(1)
        if hasattr(self.minion.functions[fun], '__outputter__'):
            oput = self.minion.functions[fun].__outputter__
            if isinstance(oput, string_types):
                ret['out'] = oput
        return ret

    def print_docs(self):
        '''
        Pick up the documentation for all of the modules and print it out.
        '''
        docs = {}
        for name, func in self.minion.functions.items():
            if name not in docs:
                if func.__doc__:
                    docs[name] = func.__doc__
        for name in sorted(docs):
            if name.startswith(self.opts.get('fun', '')):
                print('{0}:\n{1}\n'.format(name, docs[name]))

    def print_grains(self):
        '''
        Print out the grains
        '''
        grains = salt.loader.grains(self.opts)
        printout = salt.output.get_printout(grains, 'yaml', self.opts, indent=2)
        printout(grains, color=not bool(self.opts['no_color']))

    def run(self):
        '''
        Execute the salt call logic
        '''
        ret = self.call()
        printout = salt.output.get_printout(
            ret, ret.get('out', None), self.opts, indent=2
        )
        if printout is None:
            printout = salt.output.get_outputter(None)
        printout({'local': ret['return']}, color=not bool(self.opts['no_color']))
