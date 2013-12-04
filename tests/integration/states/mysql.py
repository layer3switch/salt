# -*- coding: utf-8 -*-

'''
Tests for the MySQL state
'''

# Import python libs
import logging


# Import Salt Testing libs
from salttesting import skipIf
from salttesting.helpers import (
    destructiveTest,
    ensure_in_syspath
)
ensure_in_syspath('../../')

# Import salt libs
import integration
import salt.utils

log = logging.getLogger(__name__)

NO_MYSQL = False
try:
    import MySQLdb
except Exception:
    NO_MYSQL = True

@skipIf(
    NO_MYSQL,
    'Please install MySQL bindings and a MySQL Server before running'
    'MySQL integration tests.'
)
class MysqlDatabaseStateTest(integration.ModuleCase,
                             integration.SaltReturnAssertsMixIn):
    '''
    Validate the mysql_database state
    '''

    user = 'root'
    password = 'poney'


    @destructiveTest
    def setUp(self):
        '''
        Test presence of MySQL server, enforce a root password
        '''
        super(MysqlDatabaseStateTest, self).setUp()
        NO_MYSQL_SERVER = True
        # now ensure we know the mysql root password
        # one of theses two at least should work
        ret1 = self.run_state(
            'cmd.run',
             name='mysqladmin -u '
               + self.user
               + ' flush-privileges password "'
               + self.password
               + '"'
        )
        ret2 = self.run_state(
            'cmd.run',
             name='mysqladmin -u '
               + self.user
               + ' --password="'
               + self.password
               + '" flush-privileges password "'
               + self.password
               + '"'
        )
        key, value = ret2.popitem()
        if value['result']:
            NO_MYSQL_SERVER = False
        else:
            self.skipTest('No MySQL Server running, or no root access on it.')

    @destructiveTest
    def test_present_absent(self):
        '''
        mysql_database.present
        '''
        # In case of...
        ret = self.run_state('mysql_database.absent',
                             name='testdb1',
                             character_set='utf8',
                             collate='utf8_general_ci',
                             connection_user=self.user,
                             connection_pass=self.password
        )
        ret = self.run_state('mysql_database.present',
                             name='testdb1',
                             character_set='utf8',
                             collate='utf8_general_ci',
                             connection_user=self.user,
                             connection_pass=self.password
        )
        self.assertSaltTrueReturn(ret)
        self.assertInSaltComment('The database testdb1 has been created', ret)
        #2nd run
        ret = self.run_state('mysql_database.present',
                             name='testdb1',
                             character_set='utf8',
                             collate='utf8_general_ci',
                             connection_user=self.user,
                             connection_pass=self.password
        )
        self.assertSaltTrueReturn(ret)
        self.assertInSaltComment('Database testdb1 is already present', ret)
        self.assertSaltStateChangesEqual(ret, {})

        # Test root connection on db
        ret = self.run_function(
            'mysql.query',
            database='testdb1',
            query='SELECT 1',
            connection_user=self.user,
            connection_pass=self.password,
            connection_host='localhost'
        )
        if not isinstance(ret, dict) or not 'results' in ret:
            raise AssertionError(
                ('Unexpected result while testing connection'
                ' on db {0!r}: {1}').format(
                    'testdb1',
                    repr(ret)
                )
            )
        self.assertEqual([['1']], ret['results'])

    # TODO: test with variations on collate and charset, check for db alter
    # once it will be done in mysql_database.present state

        ret = self.run_state('mysql_database.absent',
                             name='testdb1',
                             connection_user=self.user,
                             connection_pass=self.password
        )
        self.assertSaltTrueReturn(ret)
        self.assertInSaltComment(
            'Database testdb1 has been removed',
            ret
        )
        #2nd run
        ret = self.run_state('mysql_database.absent',
                             name='testdb1',
                             connection_user=self.user,
                             connection_pass=self.password
        )
        self.assertSaltTrueReturn(ret)
        self.assertInSaltComment(
            'Database testdb1 is not present, so it cannot be removed',
            ret
        )
        self.assertSaltStateChangesEqual(ret, {})


    @destructiveTest
    def test_present_absent_fuzzy(self):
        '''
        mysql_database.present with utf-8 andf fuzzy db name
        '''
        # \xe6\xa8\x99\ = \u6a19 = 標
        # this is : ":;,?:@=`&/標'\
        dbname_utf8 = '":;,?:@=`&/\xe6\xa8\x99\'\\'
        dbname_unicode = u'":;,?:@=`&/\u6a19\'\\'
        #dbname_utf8 = '":;,?:@=`&/\u6a19\'\\'
        #dbname_unicode = '":;,?:@=`&/\u6a19\'\\'
        # In case of...
        ret = self.run_state('mysql_database.absent',
                             name=dbname_utf8,
                             character_set='utf8',
                             collate='utf8_general_ci',
                             connection_user=self.user,
                             connection_pass=self.password,
                             connection_use_unicode=True,
                             connection_charset='utf8',
                             saltenv={"LC_ALL": "en_US.utf8"}
        )
        ret = self.run_state('mysql_database.present',
                             name=dbname_utf8,
                             character_set='utf8',
                             collate='utf8_general_ci',
                             connection_user=self.user,
                             connection_pass=self.password,
                             connection_use_unicode=True,
                             connection_charset='utf8',
                             saltenv={"LC_ALL": "en_US.utf8"}
        )
        self.assertSaltTrueReturn(ret)
        # 'The database ":;,?: has been created' not found in 'Database ":;,?: is already present'
        self.assertInSaltComment(
            'The database ' + dbname_utf8 + ' has been created',
            ret
        )
        #2nd run
        ret = self.run_state('mysql_database.present',
                             name=dbname_unicode,
                             character_set='utf8',
                             collate='utf8_general_ci',
                             connection_user=self.user,
                             connection_pass=self.password,
                             connection_use_unicode=True,
                             connection_charset='utf8',
                             saltenv={"LC_ALL": "en_US.utf8"}
        )
        self.assertSaltTrueReturn(ret)
        self.assertInSaltComment(
            'Database ' + dbname_utf8 + ' is already present',
            ret
        )
        self.assertSaltStateChangesEqual(ret, {})

        # Test root connection on db
        ret = self.run_function(
            'mysql.query',
            database=dbname_utf8,
            query='SELECT 1',
            connection_user=self.user,
            connection_pass=self.password,
            connection_host='localhost',
            connection_use_unicode=True,
            connection_charset='utf8',
        )
        if not isinstance(ret, dict) or not 'results' in ret:
            raise AssertionError(
                ('Unexpected result while testing connection'
                ' on db {0!r}: {1}').format(
                    dbname_utf8,
                    repr(ret)
                )
            )
        self.assertEqual([['1']], ret['results'])
        
        ret = self.run_state('mysql_database.absent',
                             name=dbname_utf8,
                             character_set='utf8',
                             collate='utf8_general_ci',
                             connection_user=self.user,
                             connection_pass=self.password,
                             connection_use_unicode=True,
                             connection_charset='utf8',
                             saltenv={"LC_ALL": "en_US.utf8"}
        )
        self.assertSaltTrueReturn(ret)
        self.assertInSaltComment(
            'Database ' + dbname_utf8 + ' has been removed',
            ret
        )
        #2nd run
        ret = self.run_state('mysql_database.absent',
                             name=dbname_unicode,
                             character_set='utf8',
                             collate='utf8_general_ci',
                             connection_user=self.user,
                             connection_pass=self.password,
                             connection_use_unicode=True,
                             connection_charset='utf8',
                             saltenv={"LC_ALL": "en_US.utf8"}
        )
        self.assertSaltTrueReturn(ret)
        self.assertInSaltComment(
            'Database ' + dbname_utf8 + ' is not present, so it cannot be removed',
            ret
        )
        self.assertSaltStateChangesEqual(ret, {})

    @destructiveTest
    @skipIf(True, 'This tests needs issue #8947 to be fixed first')
    def test_utf8_from_sls_file(self):
        '''
        Try to create/destroy an utf-8 database name from an sls file #8947
        '''
        expected_result = {
            'mysql_database_|-A_|-foo \xe6\xba\x96`bar_|-present': {
                '__run_num__': 0,
                'comment': 'The database foo \xe6\xba\x96`bar has been created',
                'result': True},
            'mysql_database_|-B_|-foo \xe6\xba\x96`bar_|-absent': {
                '__run_num__': 1,
                'comment': 'Database foo \xe6\xba\x96`bar has been removed',
                'result': True},
        }
        result = {}
        ret = self.run_function('state.sls', mods='mysql_utf8')
        if not isinstance(ret, dict):
            raise AssertionError(
                ('Unexpected result while testing external mysql utf8 sls'
                ': {0}').format(
                    repr(ret)
                )
            )
        for item, descr in ret.iteritems():
            result[item] = {
                '__run_num__': descr['__run_num__'],
                'comment': descr['comment'],
                'result': descr['result']
            }
        self.assertEqual(expected_result, result)

if __name__ == '__main__':
    from integration import run_tests
    run_tests(MysqlDatabaseStateTest)
