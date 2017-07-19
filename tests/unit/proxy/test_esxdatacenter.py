# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Alexandru Bleotu <alexandru.bleotu@morganstanley.com>`

    Tests for esxdatacenter proxy
'''

# Import Python Libs
from __future__ import absolute_import

# Import external libs
try:
    import jsonschema
    HAS_JSONSCHEMA = True
except ImportError:
    HAS_JSONSCHEMA = False

# Import Salt Libs
import salt.proxy.esxdatacenter as esxdatacenter
import salt.exceptions
from  salt.config.schemas.esxdatacenter import EsxdatacenterProxySchema

# Import Salt Testing Libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.unit import TestCase, skipIf
from tests.support.mock import (
    MagicMock,
    patch,
    NO_MOCK,
    NO_MOCK_REASON
)


@skipIf(NO_MOCK, NO_MOCK_REASON)
@skipIf(not HAS_JSONSCHEMA, 'jsonschema is required')
class InitTestCase(TestCase, LoaderModuleMockMixin):
    '''Tests for salt.proxy.esxdatacenter.init'''
    def setup_loader_modules(self):
        return {esxdatacenter: {'__virtual__':
                                MagicMock(return_value='esxdatacenter')}}

    def setUp(self):
        self.opts_userpass = {'proxy': {'proxytype': 'esxdatacenter',
                                        'vcenter': 'fake_vcenter',
                                        'datacenter': 'fake_dc',
                                        'mechanism': 'userpass',
                                        'username': 'fake_username',
                                        'passwords': ['fake_password'],
                                        'protocol': 'fake_protocol',
                                        'port': 100}}
        self.opts_sspi = {'proxy': {'proxytype': 'esxdatacenter',
                                    'vcenter': 'fake_vcenter',
                                    'datacenter': 'fake_dc',
                                    'mechanism': 'sspi',
                                    'domain': 'fake_domain',
                                    'principal': 'fake_principal',
                                    'protocol': 'fake_protocol',
                                    'port': 100}}

    def test_esxdatacenter_schema(self):
        mock_json_validate = MagicMock()
        serialized_schema = EsxdatacenterProxySchema().serialize()
        with patch('salt.proxy.esxdatacenter.jsonschema.validate',
                   mock_json_validate):
            esxdatacenter.init(self.opts_sspi)
        mock_json_validate.assert_called_once_with(
            self.opts_sspi['proxy'], serialized_schema)

    def test_invalid_proxy_input_error(self):
        with patch('salt.proxy.esxdatacenter.jsonschema.validate',
                   MagicMock(side_effect=jsonschema.exceptions.ValidationError(
                       'Validation Error'))):
            with self.assertRaises(salt.exceptions.InvalidConfigError) as \
                    excinfo:
                esxdatacenter.init(self.opts_userpass)
        self.assertEqual(excinfo.exception.strerror.message,
                         'Validation Error')

    def test_no_username(self):
        opts = self.opts_userpass.copy()
        del opts['proxy']['username']
        with self.assertRaises(salt.exceptions.InvalidConfigError) as \
                excinfo:
            esxdatacenter.init(opts)
        self.assertEqual(excinfo.exception.strerror,
                         'Mechanism is set to \'userpass\', but no '
                         '\'username\' key found in proxy config.')


    def test_no_passwords(self):
        opts = self.opts_userpass.copy()
        del opts['proxy']['passwords']
        with self.assertRaises(salt.exceptions.InvalidConfigError) as \
                excinfo:
            esxdatacenter.init(opts)
        self.assertEqual(excinfo.exception.strerror,
                         'Mechanism is set to \'userpass\', but no '
                         '\'passwords\' key found in proxy config.')

    def test_no_domain(self):
        opts = self.opts_sspi.copy()
        del opts['proxy']['domain']
        with self.assertRaises(salt.exceptions.InvalidConfigError) as \
                excinfo:
            esxdatacenter.init(opts)
        self.assertEqual(excinfo.exception.strerror,
                         'Mechanism is set to \'sspi\', but no '
                         '\'domain\' key found in proxy config.')

    def test_no_principal(self):
        opts = self.opts_sspi.copy()
        del opts['proxy']['principal']
        with self.assertRaises(salt.exceptions.InvalidConfigError) as \
                excinfo:
            esxdatacenter.init(opts)
        self.assertEqual(excinfo.exception.strerror,
                         'Mechanism is set to \'sspi\', but no '
                         '\'principal\' key found in proxy config.')

    def test_find_credentials(self):
        mock_find_credentials = MagicMock(return_value=('fake_username',
                                                        'fake_password'))
        with patch('salt.proxy.esxdatacenter.find_credentials',
                   mock_find_credentials):
            esxdatacenter.init(self.opts_userpass)
        mock_find_credentials.assert_called_once_with()


    def test_details_userpass(self):
        esxdatacenter.DETAILS = {}
        mock_find_credentials = MagicMock(return_value=('fake_username',
                                                        'fake_password'))
        with patch('salt.proxy.esxdatacenter.find_credentials',
                   mock_find_credentials):
            esxdatacenter.init(self.opts_userpass)
        self.assertDictEqual(esxdatacenter.DETAILS,
                             {'vcenter': 'fake_vcenter',
                              'datacenter': 'fake_dc',
                              'mechanism': 'userpass',
                              'username': 'fake_username',
                              'password': 'fake_password',
                              'passwords': ['fake_password'],
                              'protocol': 'fake_protocol',
                              'port': 100})

    def test_details_userpass(self):
        esxdatacenter.DETAILS = {}
        esxdatacenter.init(self.opts_sspi)
        self.assertDictEqual(esxdatacenter.DETAILS,
                             {'vcenter': 'fake_vcenter',
                              'datacenter': 'fake_dc',
                              'mechanism': 'sspi',
                              'domain': 'fake_domain',
                              'principal': 'fake_principal',
                              'protocol': 'fake_protocol',
                              'port': 100})
