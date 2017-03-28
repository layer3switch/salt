# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Jayesh Kariya <jayeshk@saltstack.com>`
'''
# Import Python libs
from __future__ import absolute_import

# Import Salt Testing Libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.unit import skipIf, TestCase
from tests.support.mock import (
    NO_MOCK,
    NO_MOCK_REASON,
    MagicMock,
    patch
)

# Import Salt Libs
import salt.states.postgres_schema as postgres_schema


@skipIf(NO_MOCK, NO_MOCK_REASON)
class PostgresSchemaTestCase(TestCase, LoaderModuleMockMixin):
    '''
    Test cases for salt.states.postgres_schema
    '''
    def setup_loader_modules(self):
        return {postgres_schema: {}}

    # 'present' function tests: 1

    def test_present(self):
        '''
        Test to ensure that the named schema is present in the database.
        '''
        name = 'myname'
        dbname = 'mydb'

        ret = {'name': name,
               'dbname': dbname,
               'changes': {},
               'result': True,
               'comment': ''}

        mock = MagicMock(return_value=name)
        with patch.dict(postgres_schema.__salt__,
                        {'postgres.schema_get': mock}):
            comt = ('Schema {0} already exists in database {1}'.format(name,
                                                                       dbname))
            ret.update({'comment': comt})
            self.assertDictEqual(postgres_schema.present(dbname, name), ret)

    # 'absent' function tests: 1

    def test_absent(self):
        '''
        Test to ensure that the named schema is absent.
        '''
        name = 'myname'
        dbname = 'mydb'

        ret = {'name': name,
               'dbname': dbname,
               'changes': {},
               'result': True,
               'comment': ''}

        mock_t = MagicMock(side_effect=[True, False])
        mock = MagicMock(side_effect=[True, True, False])
        with patch.dict(postgres_schema.__salt__,
                        {'postgres.schema_exists': mock,
                         'postgres.schema_remove': mock_t}):
            comt = ('Schema {0} has been removed from database {1}'.
                    format(name, dbname))
            ret.update({'comment': comt, 'result': True,
                        'changes': {name: 'Absent'}})
            self.assertDictEqual(postgres_schema.absent(dbname, name), ret)

            comt = ('Schema {0} failed to be removed'.format(name))
            ret.update({'comment': comt, 'result': False, 'changes': {}})
            self.assertDictEqual(postgres_schema.absent(dbname, name), ret)

            comt = ('Schema {0} is not present in database {1},'
                    ' so it cannot be removed'.format(name, dbname))
            ret.update({'comment': comt, 'result': True})
            self.assertDictEqual(postgres_schema.absent(dbname, name), ret)
