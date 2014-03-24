# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Nicole Thomas <nicole@satlstack.com>`
'''

# Import Python Libs

# Import Salt Libs
from salt.modules import darwin_sysctl
from salt.exceptions import CommandExecutionError

# Import Salt Testing Libs
from salttesting import TestCase
from salttesting.helpers import ensure_in_syspath
from salttesting.mock import MagicMock, patch

ensure_in_syspath('../../')

# Globals
darwin_sysctl.__salt__ = {}

SYSCTL_ALL = 'kern.ostype = Darwin\n' \
             'kern.osrelease = 13.1.0'


class DarwinSysctlTestCase(TestCase):
    '''
    TestCase for salt.modules.darwin_sysctl module
    '''

    def test_get(self):
        '''
        Tests the return of get function
        '''
        mock_cmd = MagicMock(return_value='foo')
        with patch.dict(darwin_sysctl.__salt__, {'cmd.run': mock_cmd}):
            self.assertEqual(darwin_sysctl.get('kern.ostype'), 'foo')

    def test_assign_cmd_failed(self):
        '''
        Tests if the assignment was successful or not
        '''
        cmd = {'pid': 3548, 'retcode': 1, 'stderr': '',
               'stdout': 'net.inet.icmp.icmplim: 250 -> 50'}
        mock_cmd = MagicMock(return_value=cmd)
        with patch.dict(darwin_sysctl.__salt__, {'cmd.run_all': mock_cmd}):
            self.assertRaises(CommandExecutionError,
                              darwin_sysctl.assign,
                              'net.inet.icmp.icmplim', 50)

    def test_assign(self):
        '''
        Tests the return of successful assign function
        '''
        cmd = {'pid': 3548, 'retcode': 0, 'stderr': '',
               'stdout': 'net.inet.icmp.icmplim: 250 -> 50'}
        ret = {'net.inet.icmp.icmplim': '50'}
        mock_cmd = MagicMock(return_value=cmd)
        with patch.dict(darwin_sysctl.__salt__, {'cmd.run_all': mock_cmd}):
            self.assertEqual(darwin_sysctl.assign(
                'net.inet.icmp.icmplim', 50), ret)


if __name__ == '__main__':
    from integration import run_tests
    run_tests(DarwinSysctlTestCase, needs_daemon=False)