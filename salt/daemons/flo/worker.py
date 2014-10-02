# -*- coding: utf-8 -*-
'''
The core behaviors used by minion and master
'''
# pylint: disable=W0232

# Import python libs
import time
import os
import multiprocessing
import logging

# Import salt libs
import salt.daemons.masterapi
from raet import raeting
from raet.lane.stacking import LaneStack
from raet.lane.yarding import RemoteYard


# Import ioflo libs
import ioflo.base.deeding

log = logging.getLogger(__name__)


class SaltRaetWorkerFork(ioflo.base.deeding.Deed):
    '''
    Fork off the worker procs
    FloScript:

    do salt raet worker fork at enter

    '''
    Ioinits = {'opts': '.salt.opts',
               'worker_verify': '.salt.var.worker_verify',
               'access_keys': '.salt.access_keys'}

    def _make_workers(self):
        '''
        Spin up a process for each worker thread
        '''
        for ind in range(int(self.opts.value['worker_threads'])):
            time.sleep(0.01)
            proc = multiprocessing.Process(
                    target=self._worker, kwargs={'yid': ind + 1}
                    )
            proc.start()

    def _worker(self, yid):
        '''
        Spin up a worker, do this in  multiprocess
        '''
        self.opts.value['__worker'] = True
        behaviors = ['salt.daemons.flo']
        preloads = [('.salt.opts', dict(value=self.opts.value)),
                    ('.salt.var.worker_verify', dict(value=self.worker_verify.value))]
        preloads.append(('.salt.yid', dict(value=yid)))
        preloads.append(
                ('.salt.access_keys', dict(value=self.access_keys.value)))

        console_logdir = self.opts.value.get('ioflo_console_logdir', '')
        if console_logdir:
            consolepath = os.path.join(console_logdir, "worker_{0}.log".format(yid))
        else:  # empty means log to std out
            consolepath = ''

        ioflo.app.run.start(
                name='worker{0}'.format(yid),
                period=float(self.opts.value['ioflo_period']),
                stamp=0.0,
                real=self.opts.value['ioflo_realtime'],
                filepath=self.opts.value['worker_floscript'],
                behaviors=behaviors,
                username='',
                password='',
                mode=None,
                houses=None,
                metas=None,
                preloads=preloads,
                verbose=int(self.opts.value['ioflo_verbose']),
                consolepath=consolepath,
                )

    def action(self):
        '''
        Run with an enter, starts the worker procs
        '''
        self._make_workers()


class SaltRaetWorkerSetup(ioflo.base.deeding.Deed):
    '''
    FloScript:

    do salt raet worker setup at enter

    '''
    Ioinits = {
            'opts': '.salt.opts',
            'yid': '.salt.yid',
            'access_keys': '.salt.access_keys',
            'remote': '.salt.loader.remote',
            'local': '.salt.loader.local',
            'inode': '.salt.lane.manor.',
            'stack': 'stack',
            'main': {'ipath': 'main',
                       'ival': {'name': 'master',
                                'yid': 0,
                                'lanename': 'master'}}
            }

    def action(self):
        '''
        Set up the uxd stack and behaviors
        '''
        #name = "{0}{1}{2}".format(self.opts.value.get('id', self.main.data.name),
                                  #'worker',
                                  #self.yid.value)
        name = "worker{0}".format(self.yid.value)
        # master application kind
        kind = self.opts.value['__role']
        if kind == 'master':
            lanename = 'master'  # self.opts.value.get('id', self.main.data.lanename)
        else:  # workers currently are only supported for masters
            emsg = ("Invalid application kind '{0}' for worker.".format(kind))
            log.error(emsg + '\n')
            raise ValueError(emsg)

        self.stack.value = LaneStack(
                                     name=name,
                                     lanename=lanename,
                                     uid=self.yid.value,
                                     sockdirpath=self.opts.value['sock_dir'])
        self.stack.value.Pk = raeting.packKinds.pack
        manor_yard = RemoteYard(
                                 stack=self.stack.value,
                                 #uid=0,
                                 name='manor',
                                 lanename=lanename,
                                 dirpath=self.opts.value['sock_dir'])
        self.stack.value.addRemote(manor_yard)
        self.remote.value = salt.daemons.masterapi.RemoteFuncs(self.opts.value)
        self.local.value = salt.daemons.masterapi.LocalFuncs(
                self.opts.value,
                self.access_keys.value)
        init = {}
        init['route'] = {
                'src': (None, self.stack.value.local.name, None),
                'dst': (None, manor_yard.name, 'worker_req')
                }
        self.stack.value.transmit(init, self.stack.value.fetchUidByName(manor_yard.name))
        self.stack.value.serviceAll()

    def __del__(self):
        self.stack.server.close()


class SaltRaetWorkerRouter(ioflo.base.deeding.Deed):
    '''
    FloScript:

    do salt raet worker router

    '''
    Ioinits = {
            'uxd_stack': '.salt.lane.manor.stack',
            'udp_stack': '.salt.road.manor.stack',
            'opts': '.salt.opts',
            'yid': '.salt.yid',
            'worker_verify': '.salt.var.worker_verify',
            'remote': '.salt.loader.remote',
            'local': '.salt.loader.local',
            }

    def action(self):
        '''
        Read in a command and execute it, send the return back up to the
        main master process
        '''
        self.uxd_stack.value.serviceAll()
        while self.uxd_stack.value.rxMsgs:
            msg, sender = self.uxd_stack.value.rxMsgs.popleft()
            try:
                s_estate, s_yard, s_share = msg['route']['src']
                d_estate, d_yard, d_share = msg['route']['dst']
            except (ValueError, IndexError):
                log.error('Received invalid message: {0}'.format(msg))
                return

            if 'load' in msg:
                cmd = msg['load'].get('cmd')
                if not cmd:
                    continue
                elif cmd.startswith('__'):
                    continue
                ret = {}
                if d_share == 'remote_cmd':
                    if hasattr(self.remote.value, cmd):
                        ret['return'] = getattr(self.remote.value, cmd)(msg['load'])
                elif d_share == 'local_cmd':
                    if hasattr(self.local.value, cmd):
                        ret['return'] = getattr(self.local.value, cmd)(msg['load'])
                else:
                    ret = {'error': 'Invalid request'}
                if cmd == 'publish' and 'pub' in ret['return']:
                    r_share = 'pub_ret'
                    ret['__worker_verify'] = self.worker_verify.value
                else:
                    r_share = s_share
                ret['route'] = {
                        'src': (None, self.uxd_stack.value.local.name, None),
                        'dst': (s_estate, s_yard, r_share)
                        }
                self.uxd_stack.value.transmit(ret,
                        self.uxd_stack.value.fetchUidByName('manor'))
                self.uxd_stack.value.serviceAll()
