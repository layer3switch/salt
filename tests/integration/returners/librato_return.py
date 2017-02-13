# -*- coding: utf-8 -*-
'''
Tests for the librato returner
'''
# Import Python libs
from __future__ import absolute_import
import logging
import os

# Import Salt Testing libs
from salttesting.helpers import ensure_in_syspath
ensure_in_syspath('../../')

# Import salt libs
import integration
from integration import TMP
import salt.utils.job
from salt.returners import librato_return

log = logging.getLogger(__name__)

# JOBS DIR and FILES
MOCK_RET_OBJ = {
    "fun_args": [],
    "return": {
        "test-return-state": {
            "comment": "insertcommenthere",
            "name": "test-state-1",
            "start_time": "01: 19: 51.105566",
            "result": True,
            "duration": 3.645,
            "__run_num__": 193,
            "changes": {},
            "__id__": "test-return-state"
        },
        "test-return-state2": {
            "comment": "insertcommenthere",
            "name": "test-state-2",
            "start_time": "01: 19: 51.105566",
            "result": False,
            "duration": 3.645,
            "__run_num__": 194,
            "changes": {},
            "__id__": "test-return-state"
        }
    },
    "retcode": 2,
    "success": True,
    "fun": "state.highstate",
    "id": "Librato-Test",
    "out": "highstate"
}


class libratoTest(integration.ShellCase):
    '''
    Test the librato returner
    '''

    def test_count_runtimes(self):
        '''
        Test the calculations
        '''
        results = librato_return._calculate_runtimes(MOCK_RET_OBJ['return'])
        self.assertEqual(results['num_failed_states'], 1)
        self.assertEqual(results['num_passed_states'], 1)
        self.assertEqual(results['runtime'], 7.29)

if __name__ == '__main__':
    from integration import run_tests
    run_tests(libratoTest)
