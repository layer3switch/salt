# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Rupesh Tare <rupesht@saltstack.com>`
'''
# Import python libs
from __future__ import absolute_import

# Import Salt Testing Libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.paths import TMP
from tests.support.unit import TestCase, skipIf
from tests.support.mock import (
    MagicMock,
    patch,
    NO_MOCK,
    NO_MOCK_REASON
)

# Import Salt Libs
import salt.modules.event as event
import salt.utils.event


@skipIf(NO_MOCK, NO_MOCK_REASON)
class EventTestCase(TestCase, LoaderModuleMockMixin):
    '''
    Test cases for salt.modules.event
    '''
    def setup_loader_modules(self):
        return {
            event: {
                '__opts__': {
                    'id': 'id',
                    'sock_dir': TMP,
                    'transport': 'zeromq'
                }
            }
        }

    @patch('salt.crypt.SAuth')
    @patch('salt.transport.Channel.factory')
    def test_fire_master(self,
                         salt_crypt_sauth,
                         salt_transport_channel_factory):
        '''
        Test for Fire an event off up to the master server
        '''

        preload = {'id': 'id', 'tag': 'tag', 'data': 'data',
                   'tok': 'salt', 'cmd': '_minion_event'}

        with patch.dict(event.__opts__, {'transport': 'raet',
                                         'local': False}):
            with patch.object(salt_transport_channel_factory, 'send',
                              return_value=None):
                self.assertTrue(event.fire_master('data', 'tag'))

        with patch.dict(event.__opts__, {'transport': 'A',
                                         'master_uri': 'localhost',
                                         'local': False}):
            with patch.object(salt_crypt_sauth, 'gen_token',
                              return_value='tok'):
                with patch.object(salt_transport_channel_factory, 'send',
                                  return_value=None):
                    self.assertTrue(event.fire_master('data', 'tag', preload))

        with patch.dict(event.__opts__, {'transport': 'A', 'local': False}):
            with patch.object(salt.utils.event.MinionEvent, 'fire_event',
                              side_effect=Exception('foo')):
                self.assertFalse(event.fire_master('data', 'tag'))

    @patch('salt.utils.event')
    def test_fire(self, salt_utils_event):
        '''
        Test to fire an event on the local minion event bus.
        Data must be formed as a dict.
        '''
        with patch.object(salt_utils_event, 'get_event') as mock:
            mock.fire_event = MagicMock(return_value=True)
            self.assertTrue(event.fire('data', 'tag'))

    def test_send(self):
        '''
        Test for Send an event to the Salt Master
        '''
        with patch.object(event, 'fire_master', return_value='B'):
            self.assertEqual(event.send('tag'), 'B')
