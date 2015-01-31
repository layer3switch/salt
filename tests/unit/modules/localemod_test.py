# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Rupesh Tare <rupesht@saltstack.com>`
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
from salt.modules import localemod

# Globals
localemod.__grains__ = {}
localemod.__salt__ = {}


@skipIf(NO_MOCK, NO_MOCK_REASON)
class LocalemodTestCase(TestCase):
    '''
    Test cases for salt.modules.localemod
    '''
    def test_list_avail(self):
        '''
        Test for Lists available (compiled) locales
        '''
        with patch.dict(localemod.__salt__,
                        {'cmd.run': MagicMock(return_value='A\nB')}):
            self.assertEqual(localemod.list_avail(), ['A', 'B'])

    def test_get_locale(self):
        '''
        Test for Get the current system locale
        '''
        with patch.dict(localemod.__grains__, {'os_family': ['Arch']}):
            with patch.object(localemod, '_localectl_get', return_value=True):
                self.assertTrue(localemod.get_locale())

        with patch.dict(localemod.__grains__, {'os_family': ['Gentoo']}):
            with patch.dict(localemod.__salt__, {'cmd.run':
                                                 MagicMock(return_value='A')}):
                self.assertEqual(localemod.get_locale(), 'A')

        with patch.dict(localemod.__grains__, {'os_family': ['A']}):
            with patch.dict(localemod.__salt__,
                            {'cmd.run': MagicMock(return_value='A=B')}):
                self.assertEqual(localemod.get_locale(), 'B')

        with patch.dict(localemod.__grains__, {'os_family': ['A']}):
            with patch.dict(localemod.__salt__, {'cmd.run':
                                                 MagicMock(return_value='A')}):
                self.assertEqual(localemod.get_locale(), '')

    def test_set_locale(self):
        '''
        Test for Sets the current system locale
        '''
        with patch.dict(localemod.__grains__, {'os_family': ['Arch']}):
            with patch.object(localemod, '_localectl_set', return_value=True):
                self.assertTrue(localemod.set_locale('l'))

        with patch.dict(localemod.__grains__, {'os_family': ['Gentoo']}):
            with patch.dict(localemod.__salt__, {'cmd.retcode':
                                                 MagicMock(return_value='A')}):
                self.assertFalse(localemod.set_locale('l'))

        with patch.dict(localemod.__grains__, {'os_family': ['A']}):
            self.assertTrue(localemod.set_locale('locale'))

    def test_avail(self):
        '''
        Test for Check if a locale is available
        '''
        with patch.object(localemod, '_normalize_locale',
                          return_value='en_US.UTF-8 UTF-8'):
            with patch.dict(localemod.__salt__,
                            {'locale.list_avail':
                             MagicMock(return_value=['A', 'B'])}):
                self.assertTrue(localemod.avail('locale'))

    def test_gen_locale_debian_no_charmap(self):
        '''
        Tests the return of gen_locale on Debian with no charmap provided
        '''
        with patch.dict(localemod.__grains__, {'os': 'Debian'}):
            self.assertFalse(localemod.gen_locale('foo'))

    def test_gen_locale_debian_with_charmap_not_valid(self):
        '''
        Tests the return of gen_locale on Debian with a charmap provided but it is not valid/found
        '''
        with patch.dict(localemod.__grains__, {'os': 'Debian'}):
            with patch.dict(localemod.__salt__, {'file.search': MagicMock(return_value=False)}):
                self.assertFalse(localemod.gen_locale('foo', charmap='bar'))

    def test_gen_locale_not_valid(self):
        '''
        Tests the return of gen_locale when the provided locale is not found
        '''
        self.assertFalse(localemod.gen_locale('foo'))

    def test_gen_locale_valid_debian(self):
        '''
        Tests the return of successful gen_locale on Debian system
        '''
        with patch.dict(localemod.__grains__, {'os': 'Debian'}):
            with patch.dict(localemod.__salt__,
                            {'file.search': MagicMock(return_value=True),
                             'file.replace': MagicMock(return_value=True),
                             'cmd.retcode': MagicMock(return_value='test')}):
                self.assertEqual(localemod.gen_locale('foo', charmap='bar'), 'test')

    @patch('os.listdir', MagicMock(return_value=['en_US.UTF-8']))
    def test_gen_locale_ubuntu(self):
        '''
        Test the return of successful gen_locale on Ubuntu system
        '''
        with patch.dict(localemod.__salt__,
                        {'file.replace': MagicMock(return_value=True),
                         'file.touch': MagicMock(return_value=None),
                         'file.append': MagicMock(return_value=None),
                         'cmd.retcode': MagicMock(return_value='A')}):
            with patch.dict(localemod.__grains__, {'os': 'Ubuntu'}):
                self.assertEqual(localemod.gen_locale('en_US.UTF-8'), 'A')

    @patch('os.listdir', MagicMock(return_value=['en_US.UTF-8']))
    def test_gen_locale_gentoo(self):
        '''
        Tests the return of successful gen_locale on Gentoo system
        '''
        with patch.dict(localemod.__grains__, {'os_family': 'Gentoo'}):
            with patch.dict(localemod.__salt__,
                            {'file.search': MagicMock(return_value=True),
                             'file.replace': MagicMock(return_value=True),
                             'cmd.retcode': MagicMock(return_value='A')}):
                self.assertEqual(localemod.gen_locale('en_US.UTF-8', charmap='test'), 'A')

    @patch('os.listdir', MagicMock(return_value=['en_US.UTF-8']))
    def test_gen_locale(self):
        '''
        Tests the return of successful gen_locale
        '''
        with patch.dict(localemod.__salt__,
                        {'file.replace': MagicMock(return_value=True),
                         'cmd.retcode': MagicMock(return_value='A')}):
            self.assertEqual(localemod.gen_locale('en_US.UTF-8'), 'A')


if __name__ == '__main__':
    from integration import run_tests
    run_tests(LocalemodTestCase, needs_daemon=False)
