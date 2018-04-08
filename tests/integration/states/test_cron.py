# -*- coding: utf-8 -*-

'''
Tests for the cron state
'''

# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals
import logging

log = logging.getLogger(__name__)

# Import Salt Testing libs
from tests.support.case import ModuleCase
from tests.support.unit import skipIf
from tests.support.paths import FILES, TMP, TMP_STATE_TREE
from tests.support.helpers import (
    skip_if_not_root,
    with_system_user_and_group,
    with_tempfile,
    Webserver,
)


class CronTest(ModuleCase):
    '''
    Validate the file state
    '''
    def setUp(self):
        '''
        Setup
        '''
        self.run_state('user.present', name='test_cron_user')

    def tearDown(self):
        '''
        Teardown
        '''
        # Remove cron file
        self.run_function('cmd.run',
                          cmd='crontab -u test_cron_user -r')

        # Delete user
        self.run_state('user.absent', name='test_cron_user')

    def test_managed(self):
        '''
        file.managed
        '''
        ret = self.run_state(
            'cron.file',
            name='salt://issue-46881/cron',
            user='test_cron_user'
        )
        _expected = '--- \n+++ \n@@ -1 +1,2 @@\n-\n+# Lines below here are managed by Salt, do not edit\n+@hourly touch /tmp/test-file\n'
        self.assertIn('changes', ret['cron_|-salt://issue-46881/cron_|-salt://issue-46881/cron_|-file'])
        self.assertIn('diff', ret['cron_|-salt://issue-46881/cron_|-salt://issue-46881/cron_|-file']['changes'])
        self.assertEqual(_expected, ret['cron_|-salt://issue-46881/cron_|-salt://issue-46881/cron_|-file']['changes']['diff'])
