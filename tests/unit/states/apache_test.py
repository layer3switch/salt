# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Jayesh Kariya <jayeshk@saltstack.com>`
'''
# Import Python libs
from __future__ import absolute_import

# Import Salt Testing Libs
from salttesting import skipIf, TestCase
from salttesting.mock import (
    NO_MOCK,
    NO_MOCK_REASON,
    MagicMock,
    patch,
    mock_open)

from salttesting.helpers import ensure_in_syspath

ensure_in_syspath('../../')

# Import Salt Libs
from salt.states import apache
import salt.utils

apache.__opts__ = {}
apache.__salt__ = {}


@skipIf(NO_MOCK, NO_MOCK_REASON)
class ApacheTestCase(TestCase):
    '''
    Test cases for salt.states.apache
    '''
    # 'configfile' function tests: 1

    @patch('os.path.exists', MagicMock(return_value=True))
    def test_configfile(self):
        '''
        Test to allows for inputting a yaml dictionary into a file
        for apache configuration files.
        '''
        name = 'yaml'
        config = 'VirtualHost: this: "*:80"'

        ret = {'name': name,
               'result': True,
               'changes': {},
               'comment': ''}

        mock = MagicMock(side_effect=[config, '', ''])
        with patch.object(salt.utils, 'fopen', mock_open(read_data=config)):
            with patch.dict(apache.__salt__,
                            {'apache.config': mock}):
                ret.update({'comment': 'Configuration is up to date.'})
                self.assertDictEqual(apache.configfile(name, config), ret)

                ret.update({'comment': 'Configuration will update.',
                            'changes': {'new': '',
                                        'old': 'VirtualHost: this: "*:80"'},
                            'result': None})
                with patch.dict(apache.__opts__, {'test': True}):
                    self.assertDictEqual(apache.configfile(name, config), ret)

                ret.update({'comment': 'Successfully created configuration.',
                            'result': True})
                with patch.dict(apache.__opts__, {'test': False}):
                    self.assertDictEqual(apache.configfile(name, config), ret)


if __name__ == '__main__':
    from integration import run_tests
    run_tests(ApacheTestCase, needs_daemon=False)
