# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Rahul Handay <rahulha@saltstack.com>`
'''

# Import Python Libs
from __future__ import absolute_import

# Import Salt Testing Libs
from tests.support.unit import TestCase, skipIf
from tests.support.mock import (
    MagicMock,
    patch,
    NO_MOCK,
    NO_MOCK_REASON
)

# Import Salt Libs
import salt.modules.win_path as win_path

# Globals
win_path.__salt__ = {}


class MockWin32Gui(object):
    '''
        Mock class for win32gui
    '''
    def __init__(self):
        pass

    @staticmethod
    def SendMessageTimeout(*args):
        '''
            Mock method for SendMessageTimeOut
        '''
        return [args[0]]


class MockWin32Con(object):
    '''
        Mock class for win32con
    '''
    HWND_BROADCAST = 1
    WM_SETTINGCHANGE = 1

    def __init__(self):
        pass

win_path.win32gui = MockWin32Gui
win_path.win32con = MockWin32Con


@skipIf(NO_MOCK, NO_MOCK_REASON)
class WinPathTestCase(TestCase):
    '''
        Test cases for salt.modules.win_path
    '''
    def test_rehash(self):
        '''
            Test to rehash the Environment variables
        '''
        self.assertTrue(win_path.rehash())

    def test_get_path(self):
        '''
            Test to Returns the system path
        '''
        mock = MagicMock(return_value={'vdata': 'c:\\salt'})
        with patch.dict(win_path.__salt__, {'reg.read_value': mock}):
            self.assertListEqual(win_path.get_path(), ['c:\\salt'])

    def test_exists(self):
        '''
            Test to check if the directory is configured
        '''
        mock = MagicMock(return_value='c:\\salt')
        with patch.object(win_path, 'get_path', mock):
            self.assertTrue(win_path.exists("c:\\salt"))

    def test_add(self):
        '''
            Test to add the directory to the SYSTEM path
        '''
        mock_get = MagicMock(return_value=['c:\\salt'])
        with patch.object(win_path, 'get_path', mock_get):
            mock_set = MagicMock(return_value=True)
            with patch.dict(win_path.__salt__, {'reg.set_value': mock_set}):
                mock_rehash = MagicMock(side_effect=[True, False])
                with patch.object(win_path, 'rehash', mock_rehash):
                    self.assertTrue(win_path.add("c:\\salt", 1))

                    self.assertFalse(win_path.add("c:\\salt", 1))

    def test_remove(self):
        '''
            Test to remove the directory from the SYSTEM path
        '''
        mock_get = MagicMock(side_effect=[[1], ['c:\\salt'], ['c:\\salt']])
        with patch.object(win_path, 'get_path', mock_get):
            self.assertTrue(win_path.remove("c:\\salt"))

            mock_set = MagicMock(side_effect=[True, False])
            with patch.dict(win_path.__salt__, {'reg.set_value': mock_set}):
                mock_rehash = MagicMock(return_value="Salt")
                with patch.object(win_path, 'rehash', mock_rehash):
                    self.assertEqual(win_path.remove("c:\\salt"), "Salt")

                self.assertFalse(win_path.remove("c:\\salt"))
