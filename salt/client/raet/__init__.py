# -*- coding: utf-8 -*-
'''
The client libs to communicate with the salt master when running raet
'''

# Import python libs
import os
import time
import logging

# Import Salt libs
from salt.transport.road.raet import stacking
from salt.transport.road.raet import yarding
import salt.config
import salt.client
import salt.syspaths as syspaths

log = logging.getLogger(__name__)


class LocalClient(salt.client.LocalClient):
    '''
    The RAET LocalClient
    '''
    def __init__(self,
                 c_path=os.path.join(syspaths.CONFIG_DIR, 'master'),
                 mopts=None):
        salt.client.LocalClient.__init__(self, c_path, mopts)

    def pub(self,
            tgt,
            fun,
            arg=(),
            expr_form='glob',
            ret='',
            jid='',
            timeout=5,
            **kwargs):
        '''
        Publish the command!
        '''
        payload_kwargs = self._prep_pub(
                tgt,
                fun,
                arg=(),
                expr_form='glob',
                ret='',
                jid='',
                timeout=5,
                **kwargs)
        stack = stacking.StackUxd(lanename='com', dirpath=self.opts['sock_dir'])
        router_yard = yarding.Yard(
                name='router',
                lanename='com',
                yid=0,
                dirpath=self.opts['sock_dir'])
        stack.addRemoteYard(router_yard)
        route = {'dst': (None, router_yard.name, 'local_cmd')}
        msg = {'route': route, 'load': payload_kwargs}
        stack.transmit(msg)
        stack.serviceAll()
        while True:
            time.sleep(0.01)
            stack.serviceAll()
            for msg in stack.rxMsgs:
                return msg
