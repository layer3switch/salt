# -*- coding: utf-8 -*-

# TODO: Update skipped tests to expect dictionary results from the execution
#       module functions.

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
from salt.modules import boto_lambda
from salt.exceptions import SaltInvocationError, CommandExecutionError

# Import 3rd-party libs
import salt.ext.six as six
from tempfile import NamedTemporaryFile
import logging
import os
import copy

# Import Mock libraries
from salttesting.mock import NO_MOCK, NO_MOCK_REASON, MagicMock, patch, call

# pylint: disable=import-error,no-name-in-module
try:
    import boto3
    from botocore.exceptions import ClientError
    HAS_BOTO = True
except ImportError:
    HAS_BOTO = False

# pylint: enable=import-error,no-name-in-module

# the boto_lambda module relies on the connect_to_region() method
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
function_ret = dict(FunctionName='testfunction',
                    Runtime='python2.7',
                    Role=None,
                    Handler='handler',
                    Description='abcdefg',
                    Timeout=5,
                    MemorySize=128,
                    CodeSha256='abcdef',
                    CodeSize=199,
                    FunctionArn='arn:lambda:us-east-1:1234:Something',
                    LastModified='yes')

log = logging.getLogger(__name__)

opts = salt.config.DEFAULT_MINION_OPTS
context = {}
utils = salt.loader.utils(opts, whitelist=['boto3'], context=context)

boto_lambda.__utils__ = utils
boto_lambda.__init__(opts)
boto_lambda.__salt__ = {}


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

class BotoLambdaTestCaseBase(TestCase):
    conn = None

    # Set up MagicMock to replace the boto3 session
    def setUp(self):
        global context
        context.clear()

        self.patcher = patch('boto3.session.Session')
        self.addCleanup(self.patcher.stop)
        mock_session = self.patcher.start()

        session_instance = mock_session.return_value
        self.conn = MagicMock()
        session_instance.client.return_value = self.conn

class TempZipFile:
    def __enter__(self):
        with NamedTemporaryFile(suffix='.zip', prefix='salt_test_', delete=False) as tmp:
            tmp.write('###\n')
            self.zipfile = tmp.name
        return self.zipfile
    def __exit__(self, type, value, traceback):
        os.remove(self.zipfile)

class BotoLambdaTestCaseMixin(object):
    pass


@skipIf(HAS_BOTO is False, 'The boto module must be installed.')
@skipIf(_has_required_boto() is False, 'The boto3 module must be greater than'
                                       ' or equal to version {0}'
        .format(required_boto3_version))
@skipIf(NO_MOCK, NO_MOCK_REASON)
class BotoLambdaFunctionTestCase(BotoLambdaTestCaseBase, BotoLambdaTestCaseMixin):
    '''
    TestCase for salt.modules.boto_lambda module
    '''

    def test_that_when_checking_if_a_function_exists_and_a_function_exists_the_function_exists_method_returns_true(self):
        '''
        Tests checking lambda function existence when the lambda function already exists
        '''
        self.conn.list_functions.return_value={'Functions': [function_ret]}
        func_exists_result = boto_lambda.function_exists(FunctionName=function_ret['FunctionName'], **conn_parameters)

        self.assertTrue(func_exists_result['exists'])

    def test_that_when_checking_if_a_function_exists_and_a_function_does_not_exist_the_function_exists_method_returns_false(self):
        '''
        Tests checking lambda function existence when the lambda function does not exist
        '''
        self.conn.list_functions.return_value={'Functions': [function_ret]}
        func_exists_result = boto_lambda.function_exists(FunctionName='myfunc', **conn_parameters)

        self.assertFalse(func_exists_result['exists'])

    def test_that_when_checking_if_a_function_exists_and_boto3_returns_an_error_the_function_exists_method_returns_error(self):
        '''
        Tests checking lambda function existence when boto returns an error
        '''
        self.conn.list_functions.side_effect=ClientError(error_content, 'list_functions')
        func_exists_result = boto_lambda.function_exists(FunctionName='myfunc', **conn_parameters)

        self.assertEqual(func_exists_result.get('error',{}).get('message'), error_message.format('list_functions'))

    def test_that_when_creating_a_function_from_zipfile_succeeds_the_create_function_method_returns_true(self):
        '''
        tests True function created.
        '''
        with patch.dict(boto_lambda.__salt__, {'boto_iam.get_account_id': MagicMock(return_value='1234')}), TempZipFile() as zipfile:
            self.conn.create_function.return_value=function_ret
            lambda_creation_result = boto_lambda.create_function(FunctionName='testfunction',
                                                    Runtime='python2.7',
                                                    Role='myrole',
                                                    Handler='file.method',
                                                    ZipFile=zipfile,
                                                    **conn_parameters)

        self.assertTrue(lambda_creation_result['created'])

    def test_that_when_creating_a_function_from_s3_succeeds_the_create_function_method_returns_true(self):
        '''
        tests True function created.
        '''
        with patch.dict(boto_lambda.__salt__, {'boto_iam.get_account_id': MagicMock(return_value='1234')}):
            self.conn.create_function.return_value=function_ret
            lambda_creation_result = boto_lambda.create_function(FunctionName='testfunction',
                                                    Runtime='python2.7',
                                                    Role='myrole',
                                                    Handler='file.method',
                                                    S3Bucket='bucket',
                                                    S3Key='key',
                                                    **conn_parameters)

        self.assertTrue(lambda_creation_result['created'])

    def test_that_when_creating_a_function_without_code_raises_a_salt_invocation_error(self):
        '''
        tests Creating a function without code
        '''
        with patch.dict(boto_lambda.__salt__, {'boto_iam.get_account_id': MagicMock(return_value='1234')}
                       ), self.assertRaisesRegexp(SaltInvocationError,
                                     'Either ZipFile must be specified, or S3Bucket and S3Key must be provided.'):
            lambda_creation_result = boto_lambda.create_function(FunctionName='testfunction',
                                                    Runtime='python2.7',
                                                    Role='myrole',
                                                    Handler='file.method',
                                                    **conn_parameters)

    def test_that_when_creating_a_function_with_zipfile_and_s3_raises_a_salt_invocation_error(self):
        '''
        tests Creating a function without code
        '''
        with patch.dict(boto_lambda.__salt__, {'boto_iam.get_account_id': MagicMock(return_value='1234')}
                      ), self.assertRaisesRegexp(SaltInvocationError,
                                     'Either ZipFile must be specified, or S3Bucket and S3Key must be provided.'
                       ), TempZipFile() as zipfile:
                lambda_creation_result = boto_lambda.create_function(FunctionName='testfunction',
                                                    Runtime='python2.7',
                                                    Role='myrole',
                                                    Handler='file.method',
                                                    ZipFile=zipfile,
                                                    S3Bucket='bucket',
                                                    S3Key='key',
                                                    **conn_parameters)

    def test_that_when_creating_a_function_fails_the_create_function_method_returns_error(self):
        '''
        tests False function not created.
        '''
        with patch.dict(boto_lambda.__salt__, {'boto_iam.get_account_id': MagicMock(return_value='1234')}):
            self.conn.create_function.side_effect=ClientError(error_content, 'create_function')
            with TempZipFile() as zipfile:
                lambda_creation_result = boto_lambda.create_function(FunctionName='testfunction',
                                                    Runtime='python2.7',
                                                    Role='myrole',
                                                    Handler='file.method',
                                                    ZipFile=zipfile,
                                                    **conn_parameters)
        self.assertEqual(lambda_creation_result.get('error',{}).get('message'), error_message.format('create_function'))

    def test_that_when_deleting_a_function_succeeds_the_delete_function_method_returns_true(self):
        '''
        tests True function deleted.
        '''
        with patch.dict(boto_lambda.__salt__, {'boto_iam.get_account_id': MagicMock(return_value='1234')}), TempZipFile() as zipfile:
            result = boto_lambda.delete_function(FunctionName='testfunction',
                                                    Qualifier=1,
                                                    **conn_parameters)

        self.assertTrue(result['deleted'])

    def test_that_when_deleting_a_function_fails_the_delete_function_method_returns_false(self):
        '''
        tests False function not deleted.
        '''
        with patch.dict(boto_lambda.__salt__, {'boto_iam.get_account_id': MagicMock(return_value='1234')}):
            self.conn.delete_function.side_effect=ClientError(error_content, 'delete_function')
            result = boto_lambda.delete_function(FunctionName='testfunction',
                                                    **conn_parameters)
        self.assertFalse(result['deleted'])

    def test_that_when_describing_function_it_returns_the_dict_of_properties_returns_true(self):
        '''
        Tests describing parameters if function exists
        '''
        self.conn.list_functions.return_value={ 'Functions': [ function_ret ]}

        with patch.dict(boto_lambda.__salt__, {'boto_iam.get_account_id': MagicMock(return_value='1234')}):
            result = boto_lambda.describe_function(FunctionName=function_ret['FunctionName'], **conn_parameters)

        self.assertEqual(result, { 'function': function_ret })

    def test_that_when_describing_function_it_returns_the_dict_of_properties_returns_false(self):
        '''
        Tests describing parameters if function does not exist
        '''
        self.conn.list_functions.return_value={ 'Functions': [ ]}
        with patch.dict(boto_lambda.__salt__, {'boto_iam.get_account_id': MagicMock(return_value='1234')}):
            result = boto_lambda.describe_function(FunctionName='testfunction', **conn_parameters)

        self.assertFalse(result['function'])

    def test_that_when_describing_lambda_on_client_error_it_returns_error(self):
        '''
        Tests describing parameters failure
        '''
        self.conn.list_functions.side_effect=ClientError(error_content, 'list_functions')
        result = boto_lambda.describe_function(FunctionName='testfunction', **conn_parameters)
        self.assertTrue('error' in result)

    def test_that_when_updating_a_function_succeeds_the_update_function_method_returns_true(self):
        '''
        tests True function updated.
        '''
        with patch.dict(boto_lambda.__salt__, {'boto_iam.get_account_id': MagicMock(return_value='1234')}):
            self.conn.update_function_config.return_value=function_ret
            result = boto_lambda.update_function_config(FunctionName=function_ret['FunctionName'], Role='myrole', **conn_parameters)

        self.assertTrue(result['updated'])

    def test_that_when_updating_a_function_fails_the_update_function_method_returns_error(self):
        '''
        tests False function not updated.
        '''
        with patch.dict(boto_lambda.__salt__, {'boto_iam.get_account_id': MagicMock(return_value='1234')}):
            self.conn.update_function_configuration.side_effect=ClientError(error_content, 'update_function')
            result = boto_lambda.update_function_config(FunctionName='testfunction',
                                                    Role='myrole',
                                                    **conn_parameters)
        self.assertEqual(result.get('error',{}).get('message'), error_message.format('update_function'))

    def test_that_when_updating_function_code_from_zipfile_succeeds_the_update_function_method_returns_true(self):
        '''
        tests True function updated.
        '''
        with patch.dict(boto_lambda.__salt__, {'boto_iam.get_account_id': MagicMock(return_value='1234')}), TempZipFile() as zipfile:
            self.conn.update_function_code.return_value=function_ret
            result = boto_lambda.update_function_code(FunctionName=function_ret['FunctionName'], ZipFile=zipfile, **conn_parameters)

        self.assertTrue(result['updated'])

    def test_that_when_updating_function_code_from_s3_succeeds_the_update_function_method_returns_true(self):
        '''
        tests True function updated.
        '''
        with patch.dict(boto_lambda.__salt__, {'boto_iam.get_account_id': MagicMock(return_value='1234')}):
            self.conn.update_function_code.return_value=function_ret
            result = boto_lambda.update_function_code(FunctionName='testfunction',
                                                    S3Bucket='bucket',
                                                    S3Key='key',
                                                    **conn_parameters)

        self.assertTrue(result['updated'])

    def test_that_when_updating_function_code_without_code_raises_a_salt_invocation_error(self):
        '''
        tests Creating a function without code
        '''
        with patch.dict(boto_lambda.__salt__, {'boto_iam.get_account_id': MagicMock(return_value='1234')}
                       ), self.assertRaisesRegexp(SaltInvocationError,
                                     'Either ZipFile must be specified, or S3Bucket and S3Key must be provided.'):
            result = boto_lambda.update_function_code(FunctionName='testfunction',
                                                    **conn_parameters)

    def test_that_when_updating_function_code_fails_the_update_function_method_returns_error(self):
        '''
        tests False function not updated.
        '''
        with patch.dict(boto_lambda.__salt__, {'boto_iam.get_account_id': MagicMock(return_value='1234')}):
            self.conn.update_function_code.side_effect=ClientError(error_content, 'update_function_code')
            result = boto_lambda.update_function_code(FunctionName='testfunction',
                                                    S3Bucket='bucket',
                                                    S3Key='key',
                                                    **conn_parameters)
        self.assertEqual(result.get('error',{}).get('message'), error_message.format('update_function_code'))

    def test_that_when_listing_function_versions_succeeds_the_list_function_versions_method_returns_true(self):
        '''
        tests True function versions listed.
        '''
        with patch.dict(boto_lambda.__salt__, {'boto_iam.get_account_id': MagicMock(return_value='1234')}):
            self.conn.list_versions_by_function.return_value={'Versions': [ function_ret ]}
            result = boto_lambda.list_function_versions(FunctionName='testfunction',
                                                    **conn_parameters)

        self.assertTrue(result['Versions'])

    def test_that_when_listing_function_versions_fails_the_list_function_versions_method_returns_false(self):
        '''
        tests False no function versions listed.
        '''
        with patch.dict(boto_lambda.__salt__, {'boto_iam.get_account_id': MagicMock(return_value='1234')}):
            self.conn.list_versions_by_function.return_value={'Versions': [ ]}
            result = boto_lambda.list_function_versions(FunctionName='testfunction',
                                                    **conn_parameters)
        self.assertFalse(result['Versions'])

    def test_that_when_listing_function_versions_fails_the_list_function_versions_method_returns_error(self):
        '''
        tests False function versions error.
        '''
        with patch.dict(boto_lambda.__salt__, {'boto_iam.get_account_id': MagicMock(return_value='1234')}):
            self.conn.list_versions_by_function.side_effect=ClientError(error_content, 'list_versions_by_function')
            result = boto_lambda.list_function_versions(FunctionName='testfunction',
                                                    **conn_parameters)
        self.assertEqual(result.get('error',{}).get('message'), error_message.format('list_versions_by_function'))

if __name__ == '__main__':
    from integration import run_tests  # pylint: disable=import-error
    run_tests(BotoLambdaTestCase, needs_daemon=False)
