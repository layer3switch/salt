# -*- coding: utf-8 -*-

# Import python libs
from __future__ import absolute_import

# Import Salt Libs
from salt.utils import minions

# Import Salt Testing Libs
from tests.support.unit import TestCase
from tests.support.helpers import ensure_in_syspath

ensure_in_syspath('../../')

NODEGROUPS = {
    'group1': 'L@host1,host2,host3',
    'group2': ['G@foo:bar', 'or', 'web1*'],
    'group3': ['N@group1', 'or', 'N@group2'],
    'group4': ['host4', 'host5', 'host6'],
}

EXPECTED = {
    'group1': ['L@host1,host2,host3'],
    'group2': ['G@foo:bar', 'or', 'web1*'],
    'group3': ['(', '(', 'L@host1,host2,host3', ')', 'or', '(', 'G@foo:bar', 'or', 'web1*', ')', ')'],
    'group4': ['L@host4,host5,host6'],
}


class MinionsTestCase(TestCase):
    '''
    TestCase for salt.utils.minions module functions
    '''
    def test_nodegroup_comp(self):
        '''
        Test a simple string nodegroup
        '''
        for nodegroup in NODEGROUPS:
            expected = EXPECTED[nodegroup]
            ret = minions.nodegroup_comp(nodegroup, NODEGROUPS)
            self.assertEqual(ret, expected)


if __name__ == '__main__':
    from integration import run_tests
    run_tests(MinionsTestCase, needs_daemon=False)
