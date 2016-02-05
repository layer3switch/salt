# -*- coding: utf-8 -*-
'''
The thorium system allows for advanced event tracking and reactions
'''
# Needed:
# Use a top file to load sls files locally
# use the existing state system to compile a low state
# Create a new state runtime to run the low state flow programming style
# Create the thorium plugin system
# Add dynamic recompile of thorium ruleset on given interval

# Import python libs
from __future__ import absolute_import
import time
import logging
import traceback

# Import Salt libs
import salt.state
import salt.payload
from salt.exceptions import SaltRenderError

log = logging.getLogger(__name__)


class ThorState(salt.state.HighState):
    '''
    Compile the thorium state and manage it in the thorium runtime
    '''
    def __init__(
            self,
            opts,
            grains=False,
            grain_keys=None,
            pillar=False,
            pillar_keys=None):
        self.grains = grains
        self.grain_keys = grain_keys
        self.pillar = pillar
        self.pillar_keys = pillar_keys
        opts['file_roots'] = opts['thorium_roots']
        self.opts = opts
        salt.state.HighState.__init__(self, self.opts, loader='thorium')
        self.state.inject_globals = {'__reg__': {}}
        self.event = salt.utils.event.get_master_event(
                self.opts,
                self.opts['sock_dir'])

    def gather_cache(self):
        '''
        Gather the specified data from the minion data cache
        '''
        cache = {'grains': {}, 'pillar': {}}
        if self.grains or self.pillar:
            if self.opts.get('minion_data_cache'):
                serial = salt.payload.Serial(__opts__)
                cdir = os.path.join(self.opts['cachedir'], 'minions')
                if not os.path.isdir(cdir):
                    minions = []
                else:
                    minions = os.listdir(cdir)
                if not minions:
                    return grains, pillar
                for minion in minions:
                    pillar[minion] = {}
                    grains[minion] = {}
                    datap = os.path.join(cdir, minion, 'data.p')
                    try:
                        with salt.utils.fopen(datap, 'rb') as fp_:
                            total = serial.load(fp_)
                            if 'pillar' in total:
                                if self.pillar_keys:
                                    for key in self.pillar_keys:
                                        if key in total['pillar']:
                                            cache['pillar'][minion][key] = total['pillar'][key]
                                else:
                                    cache['pillar'][minion] = total['pillar']
                            if 'grains' in total:
                                if self.grain_keys:
                                    for key in self.grain_keys:
                                        if key in total['pillar']:
                                            cache['pillar'][minion][key] = total['pillar'][key]
                                else:
                                    cache['pillar'][minion] = total['pillar']
                            else:
                                continue
                    except (IOError, OSError):
                        continue
        return cache

    def start_runtime(self):
        '''
        Start the system!
        '''
        while True:
            try:
                self.call_runtime()
            except Exception:
                log.error('Exception in Thorium: ', exc_info=True)
                time.sleep(self.opts['thorium_interval'])

    def get_chunks(self, exclude=None, whitelist=None):
        '''
        Compile the top file and return the lowstate for the thorium runtime
        to iterate over
        '''
        ret = {}
        err = []
        try:
            top = self.get_top()
        except SaltRenderError as err:
            return ret
        except Exception:
            trb = traceback.format_exc()
            err.append(trb)
            return err
        err += self.verify_tops(top)
        matches = self.top_matches(top)
        if not matches:
            msg = 'No Top file found!'
            raise SaltRenderError(msg)
        matches = self.matches_whitelist(matches, whitelist)
        high, errors = self.render_highstate(matches)
        if exclude:
            if isinstance(exclude, str):
                exclude = exclude.split(',')
            if '__exclude__' in high:
                high['__exclude__'].extend(exclude)
            else:
                high['__exclude__'] = exclude
            err += errors
        high, ext_errors = self.state.reconcile_extend(high)
        err += ext_errors
        err += self.state.verify_high(high)
        if err:
            raise SaltRenderError(err)
        return self.state.compile_high_data(high)

    def get_events(self):
        '''
        iterate over the available events and return a list of events
        '''
        ret = []
        while True:
            event = self.event.get_event(wait=1, full=True)
            if event is None:
                return ret
            ret.append(event)

    def call_runtime(self):
        '''
        Execute the runtime
        '''
        cache = self.gather_cache()
        chunks = self.get_chunks()
        interval = self.opts['thorium_interval']
        recompile = self.opts.get('thorium_recompile', 300)
        r_start = time.time()
        while True:
            events = self.get_events()
            if not events:
                time.sleep(interval)
                continue
            start = time.time()
            self.state.inject_globals['__events__'] = events
            self.state.call_chunks(chunks)
            elapsed = time.time() - start
            left = interval - elapsed
            if left > 0:
                time.sleep(left)
            self.state.reset_run_num()
            if (start - r_start) > recompile:
                cache = self.gather_cache()
                chunks = self.get_chunks()
                r_start = time.time()
