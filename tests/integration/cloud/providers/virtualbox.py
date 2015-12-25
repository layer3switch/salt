# This code assumes vboxapi.py from VirtualBox distribution
# being in PYTHONPATH, or installed system-wide

# Import Python Libs
from __future__ import absolute_import

import os
import unittest
import logging

# Import Salt Testing Libs
from salttesting import skipIf
from salttesting.helpers import ensure_in_syspath, expensiveTest

from integration.cloud.helpers import random_name
from integration.cloud.helpers.virtualbox import VirtualboxTestCase
from cloud.clouds import virtualbox

ensure_in_syspath('../../../')

# Import Salt Libs
import integration
from salt.config import cloud_providers_config

log = logging.getLogger()
log_handler = logging.StreamHandler()
log_handler.setLevel(logging.DEBUG)
log.addHandler(log_handler)
log.setLevel(logging.DEBUG)
info = log.info

# Create the cloud instance name to be used throughout the tests
INSTANCE_NAME = random_name()
PROVIDER_NAME = 'virtualbox'
DRIVER_NAME = 'virtualbox'


@skipIf(virtualbox.HAS_LIBS is False, 'salt-cloud requires virtualbox to be installed')
class VirtualboxProviderTest(integration.ShellCase):
    """
    Integration tests for the Virtualbox cloud provider using the Virtualbox driver
    """

    def run_cloud(self, arg_str, catch_stderr=False, timeout=None):
        """
        Execute salt-cloud
        """
        config_path = os.path.join(
            integration.FILES,
            'conf'
        )
        arg_str = '-c {0} {1}'.format(config_path, arg_str)
        log.debug("running salt-cloud with ", arg_str)
        return self.run_script('salt-cloud', arg_str, catch_stderr, timeout)

    def setUp(self):
        """
        Sets up the test requirements
        """
        super(VirtualboxProviderTest, self).setUp()

        # check if appropriate cloud provider and profile files are present
        profile_str = 'virtualbox-config'
        providers = self.run_cloud('--list-providers')
        log.debug("providers: ", providers)

        if profile_str + ':' not in providers:
            self.skipTest(
                'Configuration file for {0} was not found. Check {0}.conf files '
                'in tests/integration/files/conf/cloud.*.d/ to run these tests.'
                    .format(PROVIDER_NAME)
            )

        # check if personal access token, ssh_key_file, and ssh_key_names are present
        config_path = os.path.join(
            integration.FILES,
            'conf',
            'cloud.providers.d',
            PROVIDER_NAME + '.conf'
        )
        log.debug("config_path: ", config_path)
        config = cloud_providers_config(config_path)
        log.debug("config: ", config)

        # user = config[profile_str][DRIVER_NAME]['user']
        # tenant = config[profile_str][DRIVER_NAME]['tenant']
        # api = config[profile_str][DRIVER_NAME]['apikey']
        # if api == '' or tenant == '' or user == '':
        #     self.skipTest(
        #         'A user, tenant, and an api key must be provided to run these '
        #         'tests. Check tests/integration/files/conf/cloud.providers.d/{0}.conf'
        #             .format(PROVIDER_NAME)
        #     )

    def test_whatever(self):
        self.assertTrue(True)

    # def test_instance(self):
    #     """
    #     Test creating an instance on virtualbox with the virtualbox driver
    #     """
    #     # check if instance with salt installed returned
    #     try:
    #         self.assertIn(
    #             INSTANCE_NAME,
    #             [i.strip() for i in self.run_cloud('-p virtualbox-test {0}'.format(INSTANCE_NAME))]
    #         )
    #     except AssertionError:
    #         self.run_cloud('-d {0} --assume-yes'.format(INSTANCE_NAME))
    #         raise
    #
    #     # delete the instance
    #     try:
    #         self.assertIn(
    #             INSTANCE_NAME + ':',
    #             [i.strip() for i in self.run_cloud('-d {0} --assume-yes'.format(INSTANCE_NAME))]
    #         )
    #     except AssertionError:
    #         raise

    def tearDown(self):
        """
        Clean up after tests
        """
        query = self.run_cloud('--query')
        ret = '        {0}:'.format(INSTANCE_NAME)

        log.debug("query: ", query)

        # if test instance is still present, delete it
        # if ret in query:
        #    self.run_cloud('-d {0} --assume-yes'.format(INSTANCE_NAME))


class BaseVirtualboxTests(unittest.TestCase):
    def test_get_manager(self):
        self.assertIsNotNone(virtualbox.vb_get_manager())


class CreationDestructionVirtualboxTests(VirtualboxTestCase):
    def setUp(self):
        super(CreationDestructionVirtualboxTests, self).setUp()

    def test_vm_creation_and_destruction(self):
        vm_name = "__temp_test_vm__"
        virtualbox.vb_create_machine(vm_name)
        self.assertMachineExists(vm_name)

        virtualbox.vb_destroy_machine(vm_name)
        self.assertMachineDoesNotExist(vm_name)


class CloneVirtualboxTests(VirtualboxTestCase):
    def setUp(self):
        self.vbox = virtualbox.vb_get_manager()

        self.name = "SaltCloudVirtualboxTestVM"
        virtualbox.vb_create_machine(self.name)
        self.assertMachineExists(self.name)

    def tearDown(self):
        virtualbox.vb_destroy_machine(self.name)
        self.assertMachineDoesNotExist(self.name)

    def test_create_machine(self):
        vb_name = "NewTestMachine"
        virtualbox.vb_clone_vm(
            name=vb_name,
            clone_from=self.name
        )
        self.assertMachineExists(vb_name)

        virtualbox.vb_destroy_machine(vb_name)
        self.assertMachineDoesNotExist(vb_name)


if __name__ == '__main__':
    from integration import run_tests  # pylint: disable=import-error

    run_tests(VirtualboxProviderTest)
    # unittest.main()
