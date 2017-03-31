# -*- coding: utf-8 -*-
'''
Tests for the salt-run command
'''
# Import Python libs
from __future__ import absolute_import

# Import Salt Testing libs
import tests.integration as integration


class ManageTest(integration.ShellCase):
    '''
    Test the manage runner
    '''
    def test_cache(self):
        '''
        Store, list, fetch, then flush data
        '''
        # Store the data
        ret = self.run_run_plus(
            'cache.store',
            bank='test/runner',
            key='test_cache',
            data='The time has come the walrus said',
        )
        # Make sure we can see the new key
        ret = self.run_run_plus('cache.list', bank='test/runner')
        self.assertIn('test_cache', ret['return'])
        # Make sure we can see the new data
        ret = self.run_run_plus('cache.fetch', bank='test/runner', key='test_cache')
        self.assertIn('The time has come the walrus said', ret['return'])
        # Make sure we can delete the data
        ret = self.run_run_plus('cache.flush', bank='test/runner', key='test_cache')
        ret = self.run_run_plus('cache.list', bank='test/runner')
        self.assertNotIn('test_cache', ret['return'])
