# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Jayesh Kariya <jayeshk@saltstack.com>`
'''

# Import Salt Testing Libs
from salttesting import TestCase, skipIf
from salttesting.mock import (
    MagicMock,
    patch,
    NO_MOCK,
    NO_MOCK_REASON
)
# Import Salt Libs
from salt.modules import cpan
# Globals
cpan.__grains__ = {}
cpan.__salt__ = {}
cpan.__context__ = {}


@skipIf(NO_MOCK, NO_MOCK_REASON)
class CpanTestCase(TestCase):
    '''
    Test cases for salt.modules.cpan
    '''
    # 'install' function tests: 2

    def test_install(self):
        '''
        Test if it install a module from cpan
        '''
        mock = MagicMock(return_value='')
        with patch.dict(cpan.__salt__, {'cmd.run': mock}):
            mock = MagicMock(side_effect=[{'installed version': None},
                                          {'installed version':'3.1'}])
            with patch.object(cpan, 'show', mock):
                self.assertDictEqual(cpan.install('Alloy'),
                                     {'new': '3.1', 'old': None})

    def test_install_error(self):
        '''
        Test if it install a module from cpan
        '''
        mock = MagicMock(return_value="don't know what it is")
        with patch.dict(cpan.__salt__, {'cmd.run': mock}):
            self.assertDictEqual(cpan.install('Alloy'),
                                {'error': 'CPAN cannot identify this package',
                                 'new': None, 'old': None})

    # 'remove' function tests: 4

    @patch('os.listdir', MagicMock(return_value=['']))
    def test_remove(self):
        '''
        Test if it remove a module using cpan
        '''
        mock = MagicMock(return_value='')
        with patch.dict(cpan.__salt__, {'cmd.run': mock}):
            mock = MagicMock(return_value={'installed version': '2.1',
                                           'cpan build dirs': [''],
                                           'installed file': '/root'})
            with patch.object(cpan, 'show', mock):
                self.assertDictEqual(cpan.remove('Alloy'),
                                     {'new': None, 'old': '2.1'})

    def test_remove_unexist_error(self):
        '''
        Test if it try to remove an unexist module using cpan
        '''
        mock = MagicMock(return_value="don't know what it is")
        with patch.dict(cpan.__salt__, {'cmd.run': mock}):
            self.assertDictEqual(cpan.remove('Alloy'),
                                 {'error':
                                  'This package does not seem to exist'})

    def test_remove_noninstalled_error(self):
        '''
        Test if it remove non installed module using cpan
        '''
        mock = MagicMock(return_value={'installed version': None})
        with patch.object(cpan, 'show', mock):
            self.assertDictEqual(cpan.remove('Alloy'),
                                 {'new': None, 'old': None})

    def test_remove_nopan_error(self):
        '''
        Test if it gives no cpan error while removing
        '''
        mock = MagicMock(return_value={'installed version': '2.1'})
        with patch.object(cpan, 'show', mock):
            self.assertDictEqual(cpan.remove('Alloy'),
                                 {'error':'No CPAN data available to' \
                                  ' use for uninstalling'})

    # 'list' function tests: 1

    def test_list(self):
        '''
        Test if it list installed Perl module
        '''
        mock = MagicMock(return_value='')
        with patch.dict(cpan.__salt__, {'cmd.run': mock}):
            self.assertDictEqual(cpan.list_(), {})

    # 'show' function tests: 2

    def test_show(self):
        '''
        Test if it show information about a specific Perl module
        '''
        mock = MagicMock(return_value='')
        with patch.dict(cpan.__salt__, {'cmd.run': mock}):
            self.assertDictEqual(cpan.show('Alloy'),
                                 {'error':
                                  'This package does not seem to exist',
                                  'name': 'Alloy'})

    @patch('salt.modules.cpan.show',
           MagicMock(return_value={'Salt': 'salt'}))
    def test_show_mock(self):
        '''
        Test if it show information about a specific Perl module
        '''
        mock = MagicMock(return_value='Salt module installed')
        with patch.dict(cpan.__salt__, {'cmd.run': mock}):
            self.assertDictEqual(cpan.show('Alloy'), {'Salt': 'salt'})

    # 'show_config' function tests: 1

    def test_show_config(self):
        '''
        Test if it return a dict of CPAN configuration values
        '''
        mock = MagicMock(return_value='')
        with patch.dict(cpan.__salt__, {'cmd.run': mock}):
            self.assertDictEqual(cpan.show_config(), {})


if __name__ == '__main__':
    from integration import run_tests
    run_tests(CpanTestCase, needs_daemon=False)
