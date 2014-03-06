# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Nicole Thomas <nicole@satlstack.com>`
'''

# Import Salt Testing Libs
from salttesting import TestCase
from salttesting.mock import MagicMock, patch
from salttesting.helpers import ensure_in_syspath

ensure_in_syspath('../../')

# Import Salt Libs
from salt.modules import brew

# Global Variables
brew.__context__ = {}
brew.__salt__ = {}

TAPS_STRING = 'homebrew/dupes\nhomebrew/science\nhomebrew/x11'
TAPS_LIST = ['homebrew/dupes', 'homebrew/science', 'homebrew/x11']
HOMEBREW_BIN = '/usr/local/bin/brew'


class BrewTestCase(TestCase):
    '''
    TestCase for salt.modules.brew module
    '''

    # '_list_taps' function tests: 1

    def test_list_taps(self):
        '''
        Tests the return of the list of taps
        '''
        mock_taps = MagicMock(return_value=TAPS_STRING)
        with patch.dict(brew.__salt__, {'cmd.run': mock_taps}):
            self.assertEqual(brew._list_taps(), TAPS_LIST)

    # '_tap' function tests: 3

    @patch('salt.modules.brew._list_taps', MagicMock(return_value=TAPS_LIST))
    def test_tap_installed(self):
        '''
        Tests if tap argument is already installed or not
        '''
        self.assertTrue(brew._tap('homebrew/science'))

    @patch('salt.modules.brew._list_taps', MagicMock(return_value={}))
    def test_tap_failure(self):
        '''
        Tests if the tap installation failed
        '''
        mock_failure = MagicMock(return_value=1)
        with patch.dict(brew.__salt__, {'cmd.retcode': mock_failure}):
            self.assertFalse(brew._tap('homebrew/test'))

    @patch('salt.modules.brew._list_taps', MagicMock(return_value=TAPS_LIST))
    def test_tap(self):
        '''
        Tests adding unofficial Github repos to the list of brew taps
        '''
        mock_success = MagicMock(return_value=0)
        with patch.dict(brew.__salt__, {'cmd.retcode': mock_success}):
            self.assertTrue(brew._tap('homebrew/test'))

    # '_homebrew_bin' function tests: 1

    def test_homebrew_bin(self):
        '''
        Tests the path to the homebrew binary
        '''
        mock_path = MagicMock(return_value='/usr/local')
        with patch.dict(brew.__salt__, {'cmd.run': mock_path}):
            self.assertEqual(brew._homebrew_bin(), '/usr/local/bin/brew')

    # 'list_pkgs' function tests: 2
    # Only tested a few basics
    # Full functionality should be tested in integration phase

    def test_list_pkgs_removed(self):
        '''
        Tests removed implementation
        '''
        self.assertEqual(brew.list_pkgs(removed=True), {})

    def test_list_pkgs_versions_true(self):
        '''
        Tests if pkg.list_pkgs is already in context and is a list
        '''
        mock_context = {'foo': ['bar']}
        with patch.dict(brew.__context__, {'pkg.list_pkgs': mock_context}):
            self.assertEqual(brew.list_pkgs(versions_as_list=True),
                             mock_context)

    # 'version' function tests: 1

    def test_version(self):
        '''
        Tests version name returned
        '''
        mock_version = MagicMock(return_value='0.1.5')
        with patch.dict(brew.__salt__, {'pkg_resource.version': mock_version}):
            self.assertEqual(brew.version('foo'), '0.1.5')

    # 'latest_version' function tests: 0
    # It has not been fully implemented

    # 'refresh_db' function tests: 2

    @patch('salt.modules.brew._homebrew_bin',
           MagicMock(return_value=HOMEBREW_BIN))
    def test_refresh_db_failure(self):
        '''
        Tests an update of homebrew package repository failure
        '''
        mock_user = MagicMock(return_value='foo')
        mock_failure = MagicMock(return_value=1)
        with patch.dict(brew.__salt__, {'file.get_user': mock_user,
                                        'cmd.retcode': mock_failure}):
            self.assertFalse(brew.refresh_db())

    @patch('salt.modules.brew._homebrew_bin',
           MagicMock(return_value=HOMEBREW_BIN))
    def test_refresh_db(self):
        '''
        Tests a successful update of homebrew package repository
        '''
        mock_user = MagicMock(return_value='foo')
        mock_success = MagicMock(return_value=0)
        with patch.dict(brew.__salt__, {'file.get_user': mock_user,
                                        'cmd.retcode': mock_success}):
            self.assertTrue(brew.refresh_db())


if __name__ == '__main__':
    from integration import run_tests
    run_tests(BrewTestCase, needs_daemon=False)
