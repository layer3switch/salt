# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Nicole Thomas <nicole@saltstack.com>`
'''

# Import Python Libs
import os

# Import Salt Libs
import integration
from salt.config import cloud_providers_config

# Import Salt Testing Libs
from salttesting import skipIf
from salttesting.helpers import ensure_in_syspath, expensiveTest

ensure_in_syspath('../../../')

# Import Third-Party Libs
try:
    import libcloud  # pylint: disable=W0611
    HAS_LIBCLOUD = True
except ImportError:
    HAS_LIBCLOUD = False

try:
    import requests  # pylint: disable=W0611
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False


@skipIf(True, 'waiting on bug report fixes from #13232')
@skipIf(HAS_LIBCLOUD is False, 'salt-cloud requires >= libcloud 0.13.2')
@skipIf(HAS_REQUESTS is False, 'salt-cloud requires python requests library')
class DigitalOceanTest(integration.ShellCase):
    '''
    Integration tests for the Digital Ocean cloud provider in Salt-Cloud
    '''

    def setUp(self):
        '''
        Sets up the test requirements
        '''
        super(DigitalOceanTest, self).setUp()

        # check if appropriate cloud provider and profile files are present
        profile_str = 'digitalocean-config:'
        provider = 'digital_ocean'
        providers = self.run_cloud('--list-providers')
        print providers
        if profile_str not in providers:
            self.skipTest(
                'Configuration file for {0} was not found. Check {0}.conf files '
                'in tests/integration/files/conf/cloud.*.d/ to run these tests.'
                .format(provider)
            )

        # check if client_key and api_key are present
        path = os.path.join(integration.FILES,
                            'conf',
                            'cloud.providers.d',
                            provider + '.conf')
        config = cloud_providers_config(path)
        print config
        api = config['digitalocean-config']['digital_ocean']['api_key']
        client = config['digitalocean-config']['digital_ocean']['client_key']
        if api == '' or client == '':
            self.skipTest(
                'A client key and an api key must be provided to run these tests. '
                'Check tests/integration/files/conf/cloud.providers.d/{0}.conf'
                .format(provider)
            )

    @expensiveTest
    def test_instance(self):
        '''
        Test creating an instance on Digital Ocean
        '''
        name = 'digitalocean-testing'

        # create the instance
        instance = self.run_cloud('-p digitalocean-test {0}'.format(name))
        str = '        {0}'.format(name)

        # check if instance with salt installed returned
        try:
            self.assertIn(str, instance)
        except AssertionError:
            self.run_cloud('-d {0} --assume-yes'.format(name))
            raise

        # delete the instance
        delete = self.run_cloud('-d {0} --assume-yes'.format(name))
        str = '            True'
        try:
            self.assertIn(str, delete)
        except AssertionError:
            raise

    def tearDown(self):
        '''
        Clean up after tests
        '''
        name = 'digitalocean-testing'
        query = self.run_cloud('--query')
        str = '        {0}:'.format(name)

        # if test instance is still present, delete it
        if str in query:
            self.run_cloud('-d {0} --assume-yes'.format(name))


if __name__ == '__main__':
    from integration import run_tests
    run_tests(DigitalOceanTest)
