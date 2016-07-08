# -*- encoding: utf-8 -*-
'''
    :codeauthor: :email: `Justin Anderson <janderson@saltstack.com>`

    tests.integration.states.network
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
'''
# Python libs
from __future__ import absolute_import

# Salt libs
import integration

# Salttesting libs
from salttesting.helpers import destructiveTest, ensure_in_syspath

ensure_in_syspath('../../')


@destructiveTest
class NetworkTest(integration.ModuleCase, integration.SaltReturnAssertsMixIn):
    '''
    Validate network state module
    '''
    def setUp(self):
        os_family = self.run_function('grains.get', ['os_family'])
        if os_family not in ('RedHat', 'Debian'):
            self.skipTest('Network state only supported on RedHat and Debian based systems')

        self.run_function('cmd.run', ['ip link add name dummy0 type dummy'])

    def tearDown(self):
        self.run_function('cmd.run', ['ip link delete dev dummy0'])

    def test_managed(self):
        '''
        network.managed
        '''
        if_name = 'dummy0'
        ipaddr = '10.1.0.1'
        netmask = '255.255.255.0'
        broadcast = '10.1.0.255'

        expected_if_ret = [{
                    "broadcast": broadcast,
                    "netmask": netmask,
                    "label": if_name,
                    "address": ipaddr
                }]

        ret = self.run_function('state.sls', mods='network.managed')
        self.assertSaltTrueReturn(ret)

        interface = self.run_function('network.interface', [if_name])
        self.assertEqual(interface, expected_if_ret)

    def test_routes(self):
        '''
        network.routes
        '''
        state_key = 'network_|-routes_|-dummy0_|-routes'
        expected_changes = {'network_routes': 'Added interface dummy0 routes.'}

        ret = self.run_function('state.sls', mods='network.routes')

        self.assertSaltTrueReturn(ret)
        self.assertEqual(ret[state_key]['changes'], expected_changes)

    def test_system(self):
        '''
        network.system
        '''
        state_key = 'network_|-system_|-system_|-system'

        ret = self.run_function('state.sls', mods='network.system')

        self.assertSaltTrueReturn(ret)
        self.assertIn('network_settings', ret[state_key]['changes'])


if __name__ == '__main__':
    from integration import run_tests
    run_tests(NetworkTest)
