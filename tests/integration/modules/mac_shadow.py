# -*- coding: utf-8 -*-
'''
integration tests for mac_system
'''

# Import python libs
from __future__ import absolute_import
import datetime
import random
import string

# Import Salt Testing libs
from salttesting.helpers import ensure_in_syspath, destructiveTest
from salt.ext.six.moves import range
ensure_in_syspath('../../')

# Import salt libs
import integration
import salt.utils

TEST_USER = ''


def __random_string(size=6):
    '''
    Generates a random username
    '''
    return 'RS-' + ''.join(
        random.choice(string.ascii_uppercase + string.digits)
        for x in range(size)
    )


class MacShadowModuleTest(integration.ModuleCase):
    '''
    Validate the mac_system module
    '''

    def setUp(self):
        '''
        Get current settings
        '''
        if not salt.utils.is_darwin():
            self.skipTest('Test only available on Mac OS X')

        if not salt.utils.which('dscl'):
            self.skipTest('Test requires dscl binary')

        if not salt.utils.which('pwpolicy'):
            self.skipTest('Test requires pwpolicy binary')

        if salt.utils.get_uid(salt.utils.get_user()) != 0:
            self.skipTest('Test requires root')

        TEST_USER = __random_string()

        super(MacShadowModuleTest, self).setUp()

    def tearDown(self):
        '''
        Reset to original settings
        '''
        self.run_function('user.delete', [TEST_USER])

        super(MacShadowModuleTest, self).tearDown()

    def test_info(self):
        '''
        Test shadow.info
        '''
        self.run_function('user.add', [TEST_USER])
        ret = self.run_function('shadow.info', [TEST_USER])
        self.assertTrue(isinstance(ret, dict))
        self.assertEqual(ret['name'], TEST_USER)

    def test_get_account_created(self):
        '''
        Test shadow.get_account_created
        '''
        self.run_function('user.add', [TEST_USER])
        text_date = self.run_function('shadow.get_account_created', [TEST_USER])
        obj_date = datetime.datetime.strptime(text_date, '%Y-%m-%d %H:%M:%S')
        self.assertTrue(isinstance(obj_date, datetime.date))

    def test_get_last_change(self):
        '''
        Test shadow.get_last_change
        '''
        self.run_function('user.add', [TEST_USER])
        text_date = self.run_function('shadow.get_last_change', [TEST_USER])
        obj_date = datetime.datetime.strptime(text_date, '%Y-%m-%d %H:%M:%S')
        self.assertTrue(isinstance(obj_date, datetime.date))

    def test_get_login_failed_last(self):
        '''
        Test shadow.get_login_failed_last
        '''
        self.run_function('user.add', [TEST_USER])
        text_date = self.run_function('shadow.get_login_failed_last',
                                      [TEST_USER])
        obj_date = datetime.datetime.strptime(text_date, '%Y-%m-%d %H:%M:%S')
        self.assertTrue(isinstance(obj_date, datetime.date))

    def test_get_set_maxdays(self):
        '''
        Test shadow.get_maxdays
        Test shadow.set_maxdays
        '''
        self.run_function('user.add', [TEST_USER])
        self.assertTrue(self.run_function('shadow.set_maxdays',
                                          [TEST_USER, 20]))
        self.assertEqual(self.run_function('shadow.get_maxdays', [TEST_USER]),
                         20)

    def test_get_set_change(self):
        '''
        Test shadow.get_change
        Test shadow.set_change
        '''
        self.run_function('user.add', [TEST_USER])
        self.assertTrue(self.run_function('shadow.set_change',
                                          [TEST_USER, '02/11/2011']))
        self.assertEqual(self.run_function('shadow.get_change', [TEST_USER]),
                         '02/11/2011')

    def test_get_set_expire(self):
        '''
        Test shadow.get_expire
        Test shadow.set_expire
        '''
        self.run_function('user.add', [TEST_USER])
        self.assertTrue(self.run_function('shadow.set_expire',
                                          [TEST_USER, '02/11/2011']))
        self.assertEqual(self.run_function('shadow.get_expire', [TEST_USER]),
                         '02/11/2011')

    def test_del_password(self):
        '''
        Test shadow.del_password
        '''
        self.run_function('user.add', [TEST_USER])
        self.assertTrue(self.run_function('shadow.del_password', [TEST_USER]))

    def test_set_password(self):
        '''
        Test shadow.set_password
        '''
        self.run_function('user.add', [TEST_USER])
        self.assertTrue(self.run_function('shadow.set_password',
                                          [TEST_USER, 'Pa$$W0rd']))


if __name__ == '__main__':
    from integration import run_tests
    run_tests(MacShadowModuleTest)
