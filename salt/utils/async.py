# -*- coding: utf-8 -*-
'''
Helpers/utils for working with tornado async stuff
'''

from __future__ import absolute_import

import tornado.ioloop
import tornado.concurrent
import zmq.eventloop.ioloop

import contextlib


@contextlib.contextmanager
def current_ioloop(io_loop):
    '''
    A context manager that will set the current ioloop to io_loop for the context
    '''
    orig_loop = tornado.ioloop.IOLoop.current()
    io_loop.make_current()
    try:
        yield
    finally:
        orig_loop.make_current()


class SyncWrapper(object):
    '''
    A wrapper to make Async classes synchronous

    This is uses as a simple wrapper, for example:

    async = AsyncClass()
    # this method would reguarly return a future
    future = async.async_method()

    sync = SyncWrapper(async_factory_method, (arg1, arg2), {'kwarg1': 'val'})
    # the sync wrapper will automatically wait on the future
    ret = sync.async_method()
    '''
    def __init__(self, method, args=tuple(), kwargs=None):
        if kwargs is None:
            kwargs = {}

        self.io_loop = zmq.eventloop.ioloop.ZMQIOLoop()
        kwargs['io_loop'] = self.io_loop

        with current_ioloop(self.io_loop):
            self.async = method(*args, **kwargs)

    def __getattribute__(self, key):
        try:
            return object.__getattribute__(self, key)
        except AttributeError:
            pass
        attr = getattr(self.async, key)
        if hasattr(attr, '__call__'):
            def wrap(*args, **kwargs):
                # Overload the ioloop for the func call-- since it might call .current()
                with current_ioloop(self.io_loop):
                    ret = attr(*args, **kwargs)
                    if isinstance(ret, tornado.concurrent.Future):
                        ret = self._block_future(ret)
                    return ret
            return wrap

        else:
            return attr

    def _block_future(self, future):
        self.io_loop.add_future(future, lambda future: self.io_loop.stop())
        self.io_loop.start()
        return future.result()
