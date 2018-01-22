# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Bo Maryniuk <bo@suse.de>`
'''

from __future__ import absolute_import, print_function, unicode_literals
from tests.support.unit import TestCase, skipIf
from tests.support.mock import (
    NO_MOCK,
    NO_MOCK_REASON,
    MagicMock,
    patch)

# Import Salt libs
import salt.exceptions
import salt.state
from salt.utils import ssdp
import datetime

try:
    import pytest
except ImportError as err:
    pytest = None


class Mocks(object):
    def get_socket_mock(self, expected_ip, expected_hostname):
        '''
        Get a mock of a socket
        :return:
        '''
        sck = MagicMock()
        sck.getsockname = MagicMock(return_value=(expected_ip, 123456))

        sock_mock = MagicMock()
        sock_mock.socket = MagicMock(return_value=sck)
        sock_mock.gethostbyname = MagicMock(return_value=expected_hostname)

        return sock_mock


@skipIf(NO_MOCK, NO_MOCK_REASON)
@skipIf(pytest is None, 'PyTest is missing')
class SSDPBaseTestCase(TestCase, Mocks):
    '''
    TestCase for SSDP-related parts.
    '''

    @staticmethod
    def exception_generic(*args, **kwargs):
        '''
        Side effect
        :return:
        '''
        raise Exception('some network error')

    @staticmethod
    def exception_attr_error(*args, **kwargs):
        '''
        Side effect
        :return:
        '''
        raise AttributeError('attribute error: {0}. {1}'.format(args, kwargs))

    @patch('salt.utils.ssdp._json', None)
    @patch('salt.utils.ssdp.asyncio', None)
    def test_base_avail(self):
        '''
        Test SSDP base class availability method.
        :return:
        '''
        base = ssdp.SSDPBase()
        assert not base._is_available()

        with patch('salt.utils.ssdp._json', True):
            assert not base._is_available()

        with patch('salt.utils.ssdp.asyncio', True):
            assert not base._is_available()

        with patch('salt.utils.ssdp._json', True), patch('salt.utils.ssdp.asyncio', True):
            assert base._is_available()

    def test_base_protocol_settings(self):
        '''
        Tests default constants data.
        :return:
        '''
        base = ssdp.SSDPBase()
        v_keys = ['signature', 'answer', 'port', 'listen_ip', 'timeout']
        v_vals = ['__salt_master_service', {}, 4520, '0.0.0.0', 3]
        for key in v_keys:
            assert key in base.DEFAULTS

        for key in base.DEFAULTS.keys():
            assert key in v_keys

        for key, value in zip(v_keys, v_vals):
            assert base.DEFAULTS[key] == value

    def test_base_self_ip(self):
        '''
        Test getting self IP method.

        :return:
        '''
        base = ssdp.SSDPBase()
        expected_ip = '192.168.1.10'
        expected_host = 'oxygen'
        sock_mock = self.get_socket_mock(expected_ip, expected_host)

        with patch('salt.utils.ssdp.socket', sock_mock):
            assert base.get_self_ip() == expected_ip

        sock_mock.socket().getsockname.side_effect = SSDPBaseTestCase.exception_generic
        with patch('salt.utils.ssdp.socket', sock_mock):
            assert base.get_self_ip() == expected_host


@skipIf(NO_MOCK, NO_MOCK_REASON)
@skipIf(pytest is None, 'PyTest is missing')
class SSDPFactoryTestCase(TestCase):
    '''
    Test socket protocol
    '''
    @patch('salt.utils.ssdp.socket.gethostbyname', MagicMock(return_value='10.10.10.10'))
    def test_attr_check(self):
        '''
        Tests attributes are set to the base class

        :return:
        '''
        config = {
            ssdp.SSDPBase.SIGNATURE: '-signature-',
            ssdp.SSDPBase.ANSWER: {'this-is': 'the-answer'}
        }
        factory = ssdp.SSDPFactory(**config)
        for attr in [ssdp.SSDPBase.SIGNATURE, ssdp.SSDPBase.ANSWER]:
            assert hasattr(factory, attr)
            assert getattr(factory, attr) == config[attr]
        assert not factory.disable_hidden
        assert factory.my_ip == '10.10.10.10'

    def test_transport_sendto_success(self):
        '''
        Test transport send_to.

        :return:
        '''
        transport = MagicMock()
        log = MagicMock()
        factory = ssdp.SSDPFactory()
        with patch.object(factory, 'transport', transport), patch.object(factory, 'log', log):
            data = {'some': 'data'}
            addr = '10.10.10.10'
            factory._sendto(data=data, addr=addr)
            assert factory.transport.sendto.called
            assert factory.transport.sendto.mock_calls[0][1][0]['some'] == 'data'
            assert factory.transport.sendto.mock_calls[0][2]['addr'] == '10.10.10.10'
            assert factory.log.debug.called
            assert factory.log.debug.mock_calls[0][1][0] == 'Sent successfully'

    @patch('salt.utils.ssdp.time.sleep', MagicMock())
    def test_transport_sendto_retry(self):
        '''
        Test transport send_to.

        :return:
        '''
        transport = MagicMock()
        transport.sendto = MagicMock(side_effect=SSDPBaseTestCase.exception_attr_error)
        log = MagicMock()
        factory = ssdp.SSDPFactory()
        with patch.object(factory, 'transport', transport), patch.object(factory, 'log', log):
            data = {'some': 'data'}
            addr = '10.10.10.10'
            factory._sendto(data=data, addr=addr)
            assert factory.transport.sendto.called
            assert ssdp.time.sleep.called
            assert ssdp.time.sleep.call_args[0][0] > 0 and ssdp.time.sleep.call_args[0][0] < 0.5
            assert factory.log.debug.called
            assert 'Permission error' in factory.log.debug.mock_calls[0][1][0]

    def test_datagram_signature_bad(self):
        '''
        Test datagram_received on bad signature

        :return:
        '''
        factory = ssdp.SSDPFactory()
        data = 'nonsense'
        addr = '10.10.10.10', 'foo.suse.de'

        with patch.object(factory, 'log', MagicMock()):
            factory.datagram_received(data=data, addr=addr)
            assert factory.log.debug.called
            assert 'Received bad signature from' in factory.log.debug.call_args[0][0]
            assert factory.log.debug.call_args[0][1] == addr[0]
            assert factory.log.debug.call_args[0][2] == addr[1]

    def test_datagram_signature_wrong_timestamp_quiet(self):
        '''
        Test datagram receives a wrong timestamp (no reply).

        :return:
        '''
        factory = ssdp.SSDPFactory()
        data = '{}nonsense'.format(ssdp.SSDPBase.DEFAULTS[ssdp.SSDPBase.SIGNATURE])
        addr = '10.10.10.10', 'foo.suse.de'
        with patch.object(factory, 'log', MagicMock()), patch.object(factory, '_sendto', MagicMock()):
            factory.datagram_received(data=data, addr=addr)
            assert factory.log.debug.called
            assert 'Received invalid timestamp in package' in factory.log.debug.call_args[0][0]
            assert not factory._sendto.called

    def test_datagram_signature_wrong_timestamp_reply(self):
        '''
        Test datagram receives a wrong timestamp.

        :return:
        '''
        factory = ssdp.SSDPFactory()
        factory.disable_hidden = True
        signature = ssdp.SSDPBase.DEFAULTS[ssdp.SSDPBase.SIGNATURE]
        data = '{}nonsense'.format(signature)
        addr = '10.10.10.10', 'foo.suse.de'
        with patch.object(factory, 'log', MagicMock()), patch.object(factory, '_sendto', MagicMock()):
            factory.datagram_received(data=data, addr=addr)
            assert factory.log.debug.called
            assert 'Received invalid timestamp in package' in factory.log.debug.call_args[0][0]
            assert factory._sendto.called
            assert '{}:E:Invalid timestamp'.format(signature) == factory._sendto.call_args[0][0]

    def test_datagram_signature_outdated_timestamp_quiet(self):
        '''
        Test if datagram processing reacts on outdated message (more than 20 seconds). Quiet mode.
        :return:
        '''
        factory = ssdp.SSDPFactory()
        signature = ssdp.SSDPBase.DEFAULTS[ssdp.SSDPBase.SIGNATURE]
        data = '{}{}'.format(signature, '1516623820')
        addr = '10.10.10.10', 'foo.suse.de'

        ahead_dt = datetime.datetime.fromtimestamp(1516623841)
        curnt_dt = datetime.datetime.fromtimestamp(1516623820)
        delta = datetime.timedelta(0, 20)
        with patch.object(factory, 'log', MagicMock()), patch.object(factory, '_sendto'), \
             patch('salt.utils.ssdp.datetime.datetime', MagicMock()), \
             patch('salt.utils.ssdp.datetime.datetime.now', MagicMock(return_value=ahead_dt)), \
             patch('salt.utils.ssdp.datetime.datetime.fromtimestamp', MagicMock(return_value=curnt_dt)), \
             patch('salt.utils.ssdp.datetime.timedelta', MagicMock(return_value=delta)):
            factory.datagram_received(data=data, addr=addr)
            assert factory.log.debug.called
            assert not factory.disable_hidden
            assert not factory._sendto.called
            assert 'Received outdated package' in factory.log.debug.call_args[0][0]

    def test_datagram_signature_outdated_timestamp_reply(self):
        '''
        Test if datagram processing reacts on outdated message (more than 20 seconds). Reply mode.
        :return:
        '''
        factory = ssdp.SSDPFactory()
        factory.disable_hidden = True
        signature = ssdp.SSDPBase.DEFAULTS[ssdp.SSDPBase.SIGNATURE]
        data = '{}{}'.format(signature, '1516623820')
        addr = '10.10.10.10', 'foo.suse.de'

        ahead_dt = datetime.datetime.fromtimestamp(1516623841)
        curnt_dt = datetime.datetime.fromtimestamp(1516623820)
        delta = datetime.timedelta(0, 20)
        with patch.object(factory, 'log', MagicMock()), patch.object(factory, '_sendto'), \
             patch('salt.utils.ssdp.datetime.datetime', MagicMock()), \
             patch('salt.utils.ssdp.datetime.datetime.now', MagicMock(return_value=ahead_dt)), \
             patch('salt.utils.ssdp.datetime.datetime.fromtimestamp', MagicMock(return_value=curnt_dt)), \
             patch('salt.utils.ssdp.datetime.timedelta', MagicMock(return_value=delta)):
            factory.datagram_received(data=data, addr=addr)
            assert factory.log.debug.called
            assert factory.disable_hidden
            assert factory._sendto.called
            assert factory._sendto.call_args[0][0] == '{}:E:Timestamp is too old'.format(signature)
            assert 'Received outdated package' in factory.log.debug.call_args[0][0]

    def test_datagram_signature_correct_timestamp_reply(self):
        '''
        Test if datagram processing sends out correct reply within 20 seconds.
        :return:
        '''
        factory = ssdp.SSDPFactory()
        factory.disable_hidden = True
        signature = ssdp.SSDPBase.DEFAULTS[ssdp.SSDPBase.SIGNATURE]
        data = '{}{}'.format(signature, '1516623820')
        addr = '10.10.10.10', 'foo.suse.de'

        ahead_dt = datetime.datetime.fromtimestamp(1516623840)
        curnt_dt = datetime.datetime.fromtimestamp(1516623820)
        delta = datetime.timedelta(0, 20)
        with patch.object(factory, 'log', MagicMock()), patch.object(factory, '_sendto'), \
             patch('salt.utils.ssdp.datetime.datetime', MagicMock()), \
             patch('salt.utils.ssdp.datetime.datetime.now', MagicMock(return_value=ahead_dt)), \
             patch('salt.utils.ssdp.datetime.datetime.fromtimestamp', MagicMock(return_value=curnt_dt)), \
             patch('salt.utils.ssdp.datetime.timedelta', MagicMock(return_value=delta)):
            factory.datagram_received(data=data, addr=addr)
            assert factory.log.debug.called
            assert factory.disable_hidden
            assert factory._sendto.called
            assert factory._sendto.call_args[0][0] == "{}:@:{{}}".format(signature)
