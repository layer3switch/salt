# -*- coding: utf-8 -*-
'''
Manage the Thorium complex event reaction system
'''
from __future__ import absolute_import

# Import salt libs
import salt.thorium


def start(grains=False, grain_keys=None, pillar=False, pillar_keys=None):
    '''
    Execute the Thorium runtime
    '''
    state = salt.thorium.ThorState(
            __opts__,
            grains,
            grains_keys,
            pillar,
            pillar_keys)
    state.start_runtime()
