'''
The caller module is used as a front-end to manage direct calls to the salt
minion modules.
'''
# Import python modules
import os
import pprint
# Import salt libs
import salt.loader
import salt.minion
import salt


class Caller(object):
    '''
    Object to wrap the calling of local salt modules for the salt-call command
    '''
    def __init__(self, opts):
        '''
        Pass in the command line options
        '''
        self.opts = opts
        opts['grains'] = salt.loader.grains(opts)
        self.minion = salt.minion.SMinion(opts)

    def call(self):
        '''
        Call the module
        '''
        ret = {}
        ret['return'] = self.minion.functions[self.opts['fun']](*self.opts['arg'])
        if hasattr(self.minion.functions[self.opts['fun']], '__outputter__'):
            oput = self.minion.functions[self.opts['fun']].__outputter__
            if isinstance(oput, str):
                ret['out'] = oput
        return ret

    def print_docs(self):
        '''
        Pick up the documentation for all of the modules and print it out.
        '''
        docs = {}
        for name, func in self.minion.functions.items():
            if not docs.has_key(name):
                if func.__doc__:
                    docs[name] = func.__doc__
        for name in sorted(docs):
            if name.startswith(self.opts['fun']):
                print '{0}:\n{1}\n'.format(name, docs[name])

    def print_grains(self):
        '''
        Print out the grains
        '''
        grains = salt.loader.grains(self.opts)
        pprint.pprint(grains)

    def run(self):
        '''
        Execute the salt call logic
        '''
        if self.opts['doc']:
            self.print_docs()
        elif self.opts['grains_run']:
            self.print_grains()
        else:
            ret = self.call()
            # Determine the proper output method and run it
            get_outputter = salt.output.get_outputter
            if self.opts['raw_out']:
                printout = get_outputter('raw')
            elif self.opts['json_out']:
                printout = get_outputter('json')
            elif self.opts['txt_out']:
                printout = get_outputter('txt')
            elif self.opts['yaml_out']:
                printout = get_outputter('yaml')
            elif ret.has_key('out'):
                printout = get_outputter(ret['out'])
            else:
                printout = get_outputter(None)

            printout({'local': ret['return']})


