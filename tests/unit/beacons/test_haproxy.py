# coding: utf-8

# Python libs
from __future__ import absolute_import
from collections import namedtuple

# Salt testing libs
from tests.support.unit import skipIf, TestCase
from tests.support.mock import NO_MOCK, NO_MOCK_REASON, patch, Mock, MagicMock
from tests.support.mixins import LoaderModuleMockMixin

# Salt libs
import salt.beacons.haproxy as haproxy


@skipIf(NO_MOCK, NO_MOCK_REASON)
class HAProxyBeaconTestCase(TestCase, LoaderModuleMockMixin):
    '''
    Test case for salt.beacons.haproxy
    '''

    def setup_loader_modules(self):
        return {haproxy: {}}

    def test_non_list_config(self):
        config = {}

        ret = haproxy.validate(config)

        self.assertEqual(ret, (False, 'Configuration for haproxy beacon must'
                                      ' be a list.'))

    def test_empty_config(self):
        config = [{}]

        ret = haproxy.validate(config)

        self.assertEqual(ret, (False, 'Configuration for haproxy beacon '
                                      'requires a list of backends '
                                      'and servers'))

    def test_threshold_reached(self):
        config = [{'www-backend': {'threshold': 45,
                                   'servers': ['web1']
                                   }}]
        ret = haproxy.validate(config)

        self.assertEqual(ret, (True, 'Valid beacon configuration'))

        mock = MagicMock(return_value=46)
        with patch.dict(haproxy.__salt__, {'haproxy.get_sessions': mock}):
            ret = haproxy.beacon(config)
            self.assertEqual(ret, [{'threshold': 45,
                                    'scur': 46,
                                    'server': 'web1'}])

    def test_threshold_not_reached(self):
        config = [{'www-backend': {'threshold': 100,
                                   'servers': ['web1']
                                   }}]
        ret = haproxy.validate(config)

        self.assertEqual(ret, (True, 'Valid beacon configuration'))

        mock = MagicMock(return_value=50)
        with patch.dict(haproxy.__salt__, {'haproxy.get_sessions': mock}):
            ret = haproxy.beacon(config)
            self.assertEqual(ret, [])

