'''
Modules used to control the master itself
'''

# Import salt libs
import salt.loader
import salt.utils


def call_func(mod, fun, opts, **kwargs):
    '''
    Execute a master control function
    '''
    func = '{0}.{1}'.format(mod, fun)
    w_funcs = salt.loader.wheels(opts)
    if not func in w_funcs:
        return 'Unknown wheel function'
    f_call = salt.utils.format_call(w_funcs[func], kwargs)
    return w_funcs[func](*f_call.get('args', ()), **f_call.get('kwargs', {}))
