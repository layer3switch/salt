# -*- coding: utf-8 -*-

# Import Python libs
from __future__ import absolute_import
from distutils.version import LooseVersion  # pylint: disable=import-error,no-name-in-module

# Import Salt Testing libs
from salttesting.unit import skipIf, TestCase
from salttesting.mock import NO_MOCK, NO_MOCK_REASON, patch
from salttesting.helpers import ensure_in_syspath

ensure_in_syspath('../../')

# Import Salt libs
import salt.config
import salt.loader

# Import 3rd-party libs
import logging

# Import Mock libraries
from salttesting.mock import NO_MOCK, NO_MOCK_REASON, MagicMock, patch

# pylint: disable=import-error,no-name-in-module
from unit.modules.boto_cognitoidentity_test import BotoCognitoIdentityTestCaseMixin

# Import 3rd-party libs
try:
    import boto3
    from botocore.exceptions import ClientError
    HAS_BOTO = True
except ImportError:
    HAS_BOTO = False

# pylint: enable=import-error,no-name-in-module

# the boto_cognitoidentity module relies on the connect_to_region() method
# which was added in boto 2.8.0
# https://github.com/boto/boto/commit/33ac26b416fbb48a60602542b4ce15dcc7029f12
required_boto3_version = '1.2.1'

region = 'us-east-1'
access_key = 'GKTADJGHEIQSXMKKRBJ08H'
secret_key = 'askdjghsdfjkghWupUjasdflkdfklgjsdfjajkghs'
conn_parameters = {'region': region, 'key': access_key, 'keyid': secret_key, 'profile': {}}
error_message = 'An error occurred (101) when calling the {0} operation: Test-defined error'
error_content = {
  'Error': {
    'Code': 101,
    'Message': "Test-defined error"
  }
}

first_pool_id = 'first_pool_id'
first_pool_name = 'first_pool'
second_pool_id = 'second_pool_id'
second_pool_name = 'second_pool'
second_pool_name_updated = 'second_pool_updated'
third_pool_id = 'third_pool_id'
third_pool_name = first_pool_name
default_pool_name = 'default_pool_name'
default_pool_id = 'default_pool_id'
default_dev_provider = 'test_provider_default'

identity_pools_ret = dict(IdentityPools=[dict(IdentityPoolId=first_pool_id,
                                              IdentityPoolName=first_pool_name),
                                         dict(IdentityPoolId=second_pool_id,
                                              IdentityPoolName=second_pool_name),
                                         dict(IdentityPoolId=third_pool_id,
                                              IdentityPoolName=third_pool_name)])

first_pool_ret = dict(IdentityPoolId=first_pool_id,
                      IdentityPoolName=first_pool_name,
                      AllowUnauthenticatedIdentities=False,
                      SupportedLoginProviders={'accounts.google.com': 'testing123',
                                               'api.twitter.com': 'testing123',
                                               'graph.facebook.com': 'testing123',
                                               'www.amazon.com': 'testing123'},
                      DeveloperProviderName='test_provider',
                      OpenIdConnectProviderARNs=['some_provider_arn',
                                                 'another_provider_arn'])

first_pool_role_ret = dict(IdentityPoolId=first_pool_id,
                           Roles=dict(authenticated='first_pool_auth_role',
                                      unauthenticated='first_pool_unauth_role'))

second_pool_ret = dict(IdentityPoolId=second_pool_id,
                       IdentityPoolName=second_pool_name,
                       AllowUnauthenticatedIdentities=False)

second_pool_role_ret = dict(IdentityPoolId=second_pool_id,
                            Roles=dict(authenticated='second_pool_auth_role'))

second_pool_update_ret = dict(IdentityPoolId=second_pool_id,
                              IdentityPoolName=second_pool_name,
                              AllowUnauthenticatedIdentities=True)

third_pool_ret = dict(IdentityPoolId=third_pool_id,
                      IdentityPoolName=third_pool_name,
                      AllowUnauthenticatedIdentities=False,
                      DeveloperProviderName='test_provider2')

third_pool_role_ret = dict(IdentityPoolId=third_pool_id)

default_pool_ret = dict(IdentityPoolId=default_pool_id,
                        IdentityPoolName=default_pool_name,
                        AllowUnauthenticatedIdentities=False,
                        DeveloperProviderName=default_dev_provider)

default_pool_role_ret = dict(IdentityPoolId=default_pool_id)


log = logging.getLogger(__name__)

opts = salt.config.DEFAULT_MINION_OPTS
context = {}
utils = salt.loader.utils(opts, whitelist=['boto3'], context=context)
serializers = salt.loader.serializers(opts)
funcs = salt.loader.minion_mods(opts, context=context, utils=utils, whitelist=['boto_cognitoidentity'])
salt_states = salt.loader.states(opts=opts, functions=funcs, utils=utils, whitelist=['boto_cognitoidentity'], serializers=serializers)


def _has_required_boto():
    '''
    Returns True/False boolean depending on if Boto is installed and correct
    version.
    '''
    if not HAS_BOTO:
        return False
    elif LooseVersion(boto3.__version__) < LooseVersion(required_boto3_version):
        return False
    else:
        return True


class BotoCognitoIdentityStateTestCaseBase(TestCase):
    conn = None

    # Set up MagicMock to replace the boto3 session
    def setUp(self):
        context.clear()

        self.patcher = patch('boto3.session.Session')
        self.addCleanup(self.patcher.stop)
        mock_session = self.patcher.start()

        session_instance = mock_session.return_value
        self.conn = MagicMock()
        session_instance.client.return_value = self.conn


@skipIf(HAS_BOTO is False, 'The boto module must be installed.')
@skipIf(_has_required_boto() is False, 'The boto3 module must be greater than'
                                       ' or equal to version {0}'
        .format(required_boto3_version))
@skipIf(NO_MOCK, NO_MOCK_REASON)
class BotoCognitoIdentityTestCase(BotoCognitoIdentityStateTestCaseBase, BotoCognitoIdentityTestCaseMixin):
    '''
    TestCase for salt.states.boto_cognitoidentity state.module
    '''
    def _describe_identity_pool_side_effect(self, *args, **kwargs):
        if kwargs.get('IdentityPoolId') == first_pool_id:
            return first_pool_ret
        elif kwargs.get('IdentityPoolId') == second_pool_id:
            return second_pool_ret
        elif kwargs.get('IdentityPoolId') == third_pool_id:
            return third_pool_ret
        else:
            return default_pool_ret

    def test_present_when_failing_to_describe_identity_pools(self):
        '''
        Tests exceptions when describing identity pools
        '''
        self.conn.list_identity_pools.return_value = identity_pools_ret
        self.conn.describe_identity_pool.side_effect = ClientError(error_content, 'error on describe identity pool')
        result = salt_states['boto_cognitoidentity.pool_present'](
                             name='test pool present',
                             IdentityPoolName=first_pool_name,
                             AuthenticatedRole='my_auth_role',
                             **conn_parameters)
        self.assertEqual(result.get('result'), False)
        self.assertTrue('error on describe identity pool' in result.get('comment', {}))

    def test_present_when_multiple_pools_with_same_name_exist(self):
        '''
        Tests present on an identity pool name where it matched
        multiple pools.  The result should fail.
        '''
        self.conn.list_identity_pools.return_value = identity_pools_ret
        self.conn.describe_identity_pool.side_effect = self._describe_identity_pool_side_effect
        result = salt_states['boto_cognitoidentity.pool_present'](
                             name='test pool present',
                             IdentityPoolName=first_pool_name,
                             AuthenticatedRole='my_auth_role',
                             **conn_parameters)
        self.assertEqual(result.get('result'), False)
        self.assertIn('{0}'.format([first_pool_ret, third_pool_ret]), result.get('comment', ''))

    def test_present_when_failing_to_create_a_new_identity_pool(self):
        '''
        Tests present on an identity pool name that doesn't exist and
        an error is thrown on creation.
        '''
        self.conn.list_identity_pools.return_value = identity_pools_ret
        self.conn.describe_identity_pool.side_effect = self._describe_identity_pool_side_effect
        self.conn.create_identity_pool.side_effect = ClientError(error_content, 'error on create_identity_pool')
        result = salt_states['boto_cognitoidentity.pool_present'](
                            name='test pool present',
                            IdentityPoolName=default_pool_name,
                            AuthenticatedRole='my_auth_role',
                            **conn_parameters)
        self.assertEqual(result.get('result'), False)
        self.assertTrue('error on create_identity_pool' in result.get('comment', ''))
        self.conn.update_identity_pool.assert_not_called()

    def test_present_when_failing_to_update_an_existing_identity_pool(self):
        '''
        Tests present on a unique instance of identity pool having the matching
        IdentityPoolName, and an error is thrown on updating the pool properties.
        '''
        self.conn.list_identity_pools.return_value = identity_pools_ret
        self.conn.describe_identity_pool.side_effect = self._describe_identity_pool_side_effect
        self.conn.update_identity_pool.side_effect = ClientError(error_content, 'error on update_identity_pool')
        result = salt_states['boto_cognitoidentity.pool_present'](
                            name='test pool present',
                            IdentityPoolName=second_pool_name,
                            AuthenticatedRole='my_auth_role',
                            AllowUnauthenticatedIdentities=True,
                            **conn_parameters)
        self.assertEqual(result.get('result'), False)
        self.assertTrue('error on update_identity_pool' in result.get('comment', ''))
        self.conn.create_identity_pool.assert_not_called()

    def _get_identity_pool_roles_side_effect(self, *args, **kwargs):
        if kwargs.get('IdentityPoolId') == first_pool_id:
            return first_pool_role_ret
        elif kwargs.get('IdentityPoolId') == second_pool_id:
            return second_pool_role_ret
        elif kwargs.get('IdentityPoolId') == third_pool_id:
            return third_pool_role_ret
        else:
            return default_pool_role_ret

    def test_present_when_failing_to_get_identity_pool_roles(self):
        '''
        Tests present on a unique instance of identity pool having the matching
        IdentityPoolName, where update_identity_pool succeeded, but an error
        is thrown on getting the identity pool role prior to setting the roles.
        '''
        self.conn.list_identity_pools.return_value = identity_pools_ret
        self.conn.describe_identity_pool.side_effect = self._describe_identity_pool_side_effect
        self.conn.update_identity_pool.return_value = second_pool_update_ret
        self.conn.get_identity_pool_roles.side_effect = ClientError(error_content, 'error on get_identity_pool_roles')
        result = salt_states['boto_cognitoidentity.pool_present'](
                             name='test pool present',
                             IdentityPoolName=second_pool_name,
                             AuthenticatedRole='my_auth_role',
                             AllowUnauthenticatedIdentities=True,
                             **conn_parameters)
        self.assertEqual(result.get('result'), False)
        self.assertTrue('error on get_identity_pool_roles' in result.get('comment', ''))
        self.conn.create_identity_pool.assert_not_called()
        self.conn.set_identity_pool_roles.assert_not_called()

    def test_present_when_failing_to_set_identity_pool_roles(self):
        '''
        Tests present on a unique instance of identity pool having the matching
        IdentityPoolName, where update_identity_pool succeeded, but an error
        is thrown on setting the identity pool role.
        '''
        self.conn.list_identity_pools.return_value = identity_pools_ret
        self.conn.describe_identity_pool.side_effect = self._describe_identity_pool_side_effect
        self.conn.update_identity_pool.return_value = second_pool_update_ret
        self.conn.get_identity_pool_roles.return_value = second_pool_role_ret
        self.conn.set_identity_pool_roles.side_effect = ClientError(error_content, 'error on set_identity_pool_roles')
        with patch.dict(funcs, {'boto_iam.describe_role': MagicMock(return_value={'arn': 'my_auth_role_arn'})}):
            result = salt_states['boto_cognitoidentity.pool_present'](
                                 name='test pool present',
                                 IdentityPoolName=second_pool_name,
                                 AuthenticatedRole='my_auth_role',
                                 AllowUnauthenticatedIdentities=True,
                                 **conn_parameters)
            self.assertEqual(result.get('result'), False)
            self.assertTrue('error on set_identity_pool_roles' in result.get('comment', ''))
            expected_call_args = (dict(IdentityPoolId=second_pool_id,
                                       Roles={'authenticated': 'my_auth_role_arn'}),)
            self.assertTrue(self.conn.set_identity_pool_roles.call_args == expected_call_args)

    def test_present_when_pool_name_does_not_exist(self):
        '''
        Tests the successful case of creating a new instance, and updating its
        roles
        '''
        self.conn.list_identity_pools.return_value = identity_pools_ret
        self.conn.create_identity_pool.side_effect = self._describe_identity_pool_side_effect
        self.conn.get_identity_pool_roles.return_value = default_pool_role_ret
        self.conn.set_identity_pool_roles.return_value = None
        with patch.dict(funcs, {'boto_iam.describe_role': MagicMock(return_value={'arn': 'my_auth_role_arn'})}):
            result = salt_states['boto_cognitoidentity.pool_present'](
                                 name='test pool present',
                                 IdentityPoolName=default_pool_name,
                                 AuthenticatedRole='my_auth_role',
                                 AllowUnauthenticatedIdentities=True,
                                 DeveloperProviderName=default_dev_provider,
                                 **conn_parameters)
            self.assertEqual(result.get('result'), True)
            expected_call_args = (dict(AllowUnauthenticatedIdentities=True,
                                       IdentityPoolName=default_pool_name,
                                       DeveloperProviderName=default_dev_provider,
                                       SupportedLoginProviders={},
                                       OpenIdConnectProviderARNs=[]),)
            self.assertTrue(self.conn.create_identity_pool.call_args == expected_call_args)
            expected_call_args = (dict(IdentityPoolId=default_pool_id,
                                       Roles={'authenticated': 'my_auth_role_arn'}),)
            self.assertTrue(self.conn.set_identity_pool_roles.call_args == expected_call_args)
            self.conn.update_identity_pool.assert_not_called()

    def test_present_when_pool_name_exists(self):
        '''
        Tests the successful case of updating a single instance with matching
        IdentityPoolName and its roles.
        '''
        self.conn.list_identity_pools.return_value = identity_pools_ret
        self.conn.describe_identity_pool.side_effect = self._describe_identity_pool_side_effect
        self.conn.update_identity_pool.return_value = second_pool_update_ret
        self.conn.get_identity_pool_roles.return_value = second_pool_role_ret
        self.conn.set_identity_pool_roles.return_value = None
        with patch.dict(funcs, {'boto_iam.describe_role': MagicMock(return_value={'arn': 'my_auth_role_arn'})}):
            result = salt_states['boto_cognitoidentity.pool_present'](
                                 name='test pool present',
                                 IdentityPoolName=second_pool_name,
                                 AuthenticatedRole='my_auth_role',
                                 AllowUnauthenticatedIdentities=True,
                                 **conn_parameters)
            self.assertEqual(result.get('result'), True)
            expected_call_args = (dict(AllowUnauthenticatedIdentities=True,
                                       IdentityPoolId=second_pool_id,
                                       IdentityPoolName=second_pool_name),)
            self.assertTrue(self.conn.update_identity_pool.call_args == expected_call_args)
            expected_call_args = (dict(IdentityPoolId=second_pool_id,
                                       Roles={'authenticated': 'my_auth_role_arn'}),)
            self.assertTrue(self.conn.set_identity_pool_roles.call_args == expected_call_args)
            self.conn.create_identity_pool.assert_not_called()

    def test_absent_when_pool_does_not_exist(self):
        '''
        Tests absent on an identity pool that does not exist.
        '''
        self.conn.list_identity_pools.return_value = identity_pools_ret
        result = salt_states['boto_cognitoidentity.pool_absent'](
                             name='test pool absent',
                             IdentityPoolName='no_such_pool_name',
                             RemoveAllMatched=False,
                             **conn_parameters)
        self.assertEqual(result.get('result'), False)
        self.assertEqual(result['changes'], {})

    def test_absent_when_removeallmatched_is_false_and_multiple_pools_matched(self):
        '''
        Tests absent on when RemoveAllMatched flag is false and there are multiple matches
        for the given pool name
        first_pool_name is matched to first and third pool with different id's
        '''
        self.conn.list_identity_pools.return_value = identity_pools_ret
        self.conn.describe_identity_pool.side_effect = self._describe_identity_pool_side_effect
        result = salt_states['boto_cognitoidentity.pool_absent'](
                             name='test pool absent',
                             IdentityPoolName=first_pool_name,
                             RemoveAllMatched=False,
                             **conn_parameters)
        self.assertEqual(result.get('result'), False)
        self.assertEqual(result['changes'], {})
        self.assertTrue('{0}'.format([first_pool_ret, third_pool_ret]) in result.get('comment', ''))

    def test_absent_when_failing_to_describe_identity_pools(self):
        '''
        Tests exceptions when describing identity pools
        '''
        self.conn.list_identity_pools.return_value = identity_pools_ret
        self.conn.describe_identity_pool.side_effect = ClientError(error_content, 'error on describe identity pool')
        result = salt_states['boto_cognitoidentity.pool_absent'](
                             name='test pool absent',
                             IdentityPoolName=first_pool_name,
                             RemoveAllMatched=False,
                             **conn_parameters)
        self.assertEqual(result.get('result'), False)
        self.assertTrue('error on describe identity pool' in result.get('comment', {}))

    def test_absent_when_erroring_on_delete_identity_pool(self):
        '''
        Tests error due to delete_identity_pools
        '''
        self.conn.list_identity_pools.return_value = identity_pools_ret
        self.conn.describe_identity_pool.side_effect = self._describe_identity_pool_side_effect
        self.conn.delete_identity_pool.side_effect = ClientError(error_content, 'error on delete identity pool')
        result = salt_states['boto_cognitoidentity.pool_absent'](
                             name='test pool absent',
                             IdentityPoolName=first_pool_name,
                             RemoveAllMatched=True,
                             **conn_parameters)
        self.assertEqual(result.get('result'), False)
        self.assertEqual(result['changes'], {})
        self.assertTrue('error on delete identity pool' in result.get('comment', ''))

    def test_absent_when_a_single_pool_exists(self):
        '''
        Tests absent succeeds on delete when a single pool matched and
        RemoveAllMatched is False
        '''
        self.conn.list_identity_pools.return_value = identity_pools_ret
        self.conn.describe_identity_pool.return_value = second_pool_ret
        self.conn.delete_identity_pool.return_value = None
        result = salt_states['boto_cognitoidentity.pool_absent'](
                             name='test pool absent',
                             IdentityPoolName=second_pool_name,
                             RemoveAllMatched=False,
                             **conn_parameters)
        self.assertEqual(result.get('result'), True)
        expected_changes = {'new': {'Identity Pool Id {0}'.format(second_pool_id): None},
                            'old': {'Identity Pool Id {0}'.format(second_pool_id): second_pool_name}}
        self.assertEqual(result['changes'], expected_changes)

    def test_absent_when_multiple_pool_exists_and_removeallmatched_flag_is_true(self):
        '''
        Tests absent succeeds on delete when a multiple pools matched and
        RemoveAllMatched is True

        first_pool_name should match to first_pool_id and third_pool_id
        '''
        self.conn.list_identity_pools.return_value = identity_pools_ret
        self.conn.describe_identity_pool.side_effect = self._describe_identity_pool_side_effect
        self.conn.delete_identity_pool.return_value = None
        result = salt_states['boto_cognitoidentity.pool_absent'](
                             name='test pool absent',
                             IdentityPoolName=first_pool_name,
                             RemoveAllMatched=True,
                             **conn_parameters)
        self.assertEqual(result.get('result'), True)
        expected_changes = {'new': {'Identity Pool Id {0}'.format(first_pool_id): None,
                                    'Identity Pool Id {0}'.format(third_pool_id): None},
                            'old': {'Identity Pool Id {0}'.format(first_pool_id): first_pool_name,
                                    'Identity Pool Id {0}'.format(third_pool_id): third_pool_name}}
        self.assertEqual(result['changes'], expected_changes)
