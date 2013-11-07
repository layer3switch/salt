# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Pedro Algarvio (pedro@algarvio.me)`
    :copyright: © 2013 by the SaltStack Team, see AUTHORS for more details.
    :license: Apache 2.0, see LICENSE for more details.


    salt.utils.context
    ~~~~~~~~~~~~~~~~~~

    Context managers used throughout Salt's source code.
'''

# Import python libs
from contextlib import contextmanager


@contextmanager
def state_call_context(func, **overrides):
    '''
    Override specific variable within a state call context.
    '''
    # recognize methods
    if hasattr(func, "im_func"):
        func = func.im_func

    # Get a reference to the function globals dictionary
    func_globals = func.func_globals
    # Save the current function globals dictionary state values for the
    # overridden objects
    injected_func_globals = []
    overridden_func_globals = {}
    for override in overrides:
        if override in func_globals:
            overridden_func_globals[override] = func_globals[override]
        else:
            injected_func_globals.append(override)

    # Override the function globals with what's passed in the above overrides
    func_globals.update(overrides)

    # The context is now ready to be used
    yield

    # We're now done with the context

    # Restore the overwritten function globals
    func_globals.update(overridden_func_globals)

    # Remove any entry injected in the function globals
    for injected in injected_func_globals:
        del func_globals[injected]
