# -*- coding: utf-8 -*-
'''
Wheel system wrapper for con_cache
'''

from salt.utils.cache import CacheCli
import salt.config
import salt.utils.minion

def connected():
    ''' 
    List all connected minions on a salt-master
    '''
    opts = salt.config.master_config(__opts__['conf_file'])
    minions = []

    if opts.get('con_cache'):
        minions = set(cache_cli = CacheCli(opts))
    else:
        minions = list(salt.utils.minions.CkMinions(opts).connected_ids())
    return minions

