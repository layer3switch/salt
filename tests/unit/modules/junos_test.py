__author__ = "Rajvi Dhimar"

import unittest2 as unittest
from nose.plugins.attrib import attr
from mock import patch, MagicMock

from jnpr.junos.utils.config import Config
from jnpr.junos.utils.sw import SW
from jnpr.junos.device import Device
import salt.modules.junos as junos

@attr('unit')
class Test_Junos_Module(unittest.TestCase):

    def setUp(self):
        junos.__proxy__ = {'junos.conn': self.make_connect}
        junos.__salt__ = {'cp.get_template': self.fake_cp}

    @patch('ncclient.manager.connect')
    def make_connect(self, mock_connect):
        self.dev = self.dev = Device(host='1.1.1.1', user='test', password='test123',
                          gather_facts=False)
        self.dev.open()
        self.dev.bind(cu=Config)
        self.dev.bind(sw=SW)
        return self.dev

    def fake_cp(self, path='dummy', dest=None, template_vars=None):
        return MagicMock()

    def raise_exception(self, **kwargs):
        raise Exception('dummy exception')

    def raise_exception_for_load(self, string, format):
        raise Exception('dummy exception')

    def raise_exception_for_zeroize(self, str):
        raise Exception('dummy exception')

    def raise_exception_for_install(self, path, progress):
        raise Exception('dummy exception')

    '''
    @patch('jnpr.junos.device._Connection.facts_refresh')
    def test_facts_refresh_raise_exception(self, mock_jnpr_facts_refresh):
        mock_jnpr_facts_refresh.side_effect = self.raise_exception
        ret = dict()
        ret['message'] = 'Execution failed due to "dummy exception"'
        ret['out'] = False
        self.assertEqual(junos.facts_refresh(), ret)
    '''

    def test_rpc_without_args(self):
        ret = dict()
        ret['message'] = 'Please provide the rpc to execute.'
        ret['out'] = False
        self.assertEqual(junos.rpc(), ret)

    def test_set_hostname_without_args(self):
        ret = dict()
        ret['message'] = 'Please provide the hostname.'
        ret['out'] = False
        self.assertEqual(junos.set_hostname(), ret)

    def test_set_hostname_load_called_with_valid_name(self):
        with patch('jnpr.junos.utils.config.Config.load') as mock_load:
            junos.set_hostname('dummy-name')
            mock_load.assert_called_with('set system host-name dummy-name', format='set')

    @patch('jnpr.junos.utils.config.Config.load')
    def test_set_hostname_raise_exception_for_load(self, mock_load):
        mock_load.side_effect = self.raise_exception_for_load
        ret = dict()
        ret['message'] = 'Could not load configuration due to error "dummy exception"'
        ret['out'] = False
        self.assertEqual(junos.set_hostname('dummy-name'), ret)

    @patch('jnpr.junos.utils.config.Config.commit_check')
    def test_set_hostname_raise_exception_for_commit_check(self, mock_commit_check):
        mock_commit_check.side_effect = self.raise_exception
        ret = dict()
        ret['message'] = 'Could not commit check due to error "dummy exception"'
        ret['out'] = False
        self.assertEqual(junos.set_hostname('dummy-name'), ret)

    @patch('jnpr.junos.utils.config.Config.load')
    @patch('jnpr.junos.utils.config.Config.commit_check')
    @patch('jnpr.junos.utils.config.Config.commit')
    def test_set_hostname_one_arg_parsed_correctly(self, mock_commit, mock_commit_check, mock_load):
        mock_commit_check.return_value = True
        args = {'comment': 'Committed via salt', '__pub_user': 'root', '__pub_arg':
            ['dummy-name', {'comment': 'Committed via salt'}], '__pub_fun': 'junos.set_hostname',
                '__pub_jid': '20170220210915624885', '__pub_tgt': 'mac_min', '__pub_tgt_type':
                    'glob', '__pub_ret': ''}

        junos.set_hostname('dummy-name', **args)
        mock_commit.assert_called_with(comment='Committed via salt')

    @patch('jnpr.junos.utils.config.Config.load')
    @patch('jnpr.junos.utils.config.Config.commit_check')
    @patch('jnpr.junos.utils.config.Config.commit')
    def test_set_hostname_more_than_one_args_parsed_correctly(self, mock_commit, mock_commit_check, mock_load):
        mock_commit_check.return_value = True
        args = {'comment': 'Committed via salt', '__pub_user': 'root', '__pub_arg':
            ['dummy-name', {'comment': 'Committed via salt', 'confirm': 5}], '__pub_fun': 'junos.set_hostname',
                '__pub_jid': '20170220210915624885', '__pub_tgt': 'mac_min', '__pub_tgt_type':
                    'glob', '__pub_ret': ''}

        junos.set_hostname('dummy-name', **args)
        mock_commit.assert_called_with(comment='Committed via salt', confirm=5)


    @patch('jnpr.junos.utils.config.Config.load')
    @patch('jnpr.junos.utils.config.Config.commit_check')
    @patch('jnpr.junos.utils.config.Config.commit')
    def test_set_hostname_successful_return_message(self, mock_commit, mock_commit_check, mock_load):
        mock_commit_check.return_value = True
        args = {'comment': 'Committed via salt', '__pub_user': 'root', '__pub_arg':
            ['dummy-name', {'comment': 'Committed via salt'}], '__pub_fun': 'junos.set_hostname',
                '__pub_jid': '20170220210915624885', '__pub_tgt': 'mac_min', '__pub_tgt_type':
                    'glob', '__pub_ret': ''}
        ret = dict()
        ret['message'] = 'Successfully changed hostname.'
        ret['out'] = True
        self.assertEqual(junos.set_hostname('dummy-name', **args), ret)

    @patch('jnpr.junos.utils.config.Config.commit')
    def test_set_hostname_raise_exception_for_commit(self, mock_commit):
        mock_commit.side_effect = self.raise_exception
        ret = dict()
        ret['message'] = 'Successfully loaded host-name but commit failed with "dummy exception"'
        ret['out'] = False
        self.assertEqual(junos.set_hostname('dummy-name'), ret)

    @patch('jnpr.junos.utils.config.Config.commit_check')
    @patch('salt.modules.junos.rollback')
    def test_set_hostname_fail_commit_check(self, mock_rollback, mock_commit_check):
        mock_commit_check.return_value = False
        ret = dict()
        ret['out'] = False
        ret['message'] = 'Successfully loaded host-name but pre-commit check failed.'
        self.assertEqual(junos.set_hostname('dummy'), ret)

    @patch('jnpr.junos.utils.config.Config.commit_check')
    @patch('jnpr.junos.utils.config.Config.commit')
    def test_commit_without_args(self, mock_commit, mock_commit_check):
        mock_commit.return_value = True
        mock_commit_check.return_value = True
        ret = dict()
        ret['message'] = 'Commit Successful.'
        ret['out'] = True
        self.assertEqual(junos.commit(), ret)

    @patch('jnpr.junos.utils.config.Config.commit_check')
    def test_commit_raise_commit_check_exeception(self, mock_commit_check):
        mock_commit_check.side_effect = self.raise_exception
        ret = dict ()
        ret['message'] = 'Could not perform commit check due to "dummy exception"'
        ret['out'] = False
        self.assertEqual(junos.commit(), ret)

    @patch('jnpr.junos.utils.config.Config.commit_check')
    @patch('jnpr.junos.utils.config.Config.commit')
    def test_commit_raise_commit_exception(self, mock_commit, mock_commit_check):
        mock_commit_check.return_value = True
        mock_commit.side_effect = self.raise_exception
        ret = dict()
        ret['out'] = False
        ret['message'] = \
            'Commit check succeeded but actual commit failed with "dummy exception"'
        self.assertEqual(junos.commit(), ret)

    @patch('jnpr.junos.utils.config.Config.commit_check')
    @patch('jnpr.junos.utils.config.Config.commit')
    def test_commit_with_single_argument(self, mock_commit, mock_commit_check):
        mock_commit_check.return_value = True
        args = {'__pub_user': 'root', '__pub_arg': [{'sync': True}],
                'sync': True, '__pub_fun': 'junos.commit', '__pub_jid':
                    '20170221182531323467', '__pub_tgt': 'mac_min',
                '__pub_tgt_type': 'glob', '__pub_ret': ''}
        junos.commit(**args)
        mock_commit.assert_called_with(detail=False, sync=True)

    @patch('jnpr.junos.utils.config.Config.commit_check')
    @patch('jnpr.junos.utils.config.Config.commit')
    def test_commit_with_multiple_arguments(self, mock_commit, mock_commit_check):
        mock_commit_check.return_value = True
        args = {'comment': 'comitted via salt', '__pub_user': 'root', '__pub_arg':
                [{'comment': 'comitted via salt', 'confirm': 3, 'detail': True}],
                'confirm': 3, 'detail': True, '__pub_fun': 'junos.commit',
                '__pub_jid': '20170221182856987820', '__pub_tgt': 'mac_min',
                '__pub_tgt_type': 'glob', '__pub_ret': ''}
        junos.commit(**args)
        mock_commit.assert_called_with(comment='comitted via salt', detail=True, confirm=3)

    @patch('jnpr.junos.utils.config.Config.commit_check')
    @patch('jnpr.junos.utils.config.Config.commit')
    def test_commit_pyez_commit_returning_false(self, mock_commit, mock_commit_check):
        mock_commit.return_value = False
        mock_commit_check.return_value = True
        ret = dict()
        ret['message'] = 'Commit failed.'
        ret['out'] = False
        self.assertEqual(junos.commit(), ret)

    @patch('jnpr.junos.utils.config.Config.commit_check')
    def test_commit_pyez_commit_check_returns_false(self, mock_commit_check):
        mock_commit_check.return_value = False
        ret = dict()
        ret['out'] = False
        ret['message'] = 'Pre-commit check failed.'
        self.assertEqual(junos.commit(), ret)

    @patch('jnpr.junos.utils.config.Config.commit_check')
    @patch('jnpr.junos.utils.config.Config.commit')
    @patch('jnpr.junos.utils.config.Config.rollback')
    def test_rollback_without_args_success(self, mock_rollback, mock_commit, mock_commit_check):
        mock_commit_check.return_value = True
        mock_rollback.return_value = True
        ret = dict()
        ret['message'] = 'Rollback successful'
        ret['out'] = True
        self.assertEqual(junos.rollback(), ret)

    @patch('jnpr.junos.utils.config.Config.rollback')
    def test_rollback_without_args_fail(self, mock_rollback):
        mock_rollback.return_value = False
        ret = dict()
        ret['message'] = 'Rollback failed'
        ret['out'] = False
        self.assertEqual(junos.rollback(), ret)

    @patch('jnpr.junos.utils.config.Config.commit_check')
    @patch('jnpr.junos.utils.config.Config.commit')
    @patch('jnpr.junos.utils.config.Config.rollback')
    def test_rollback_with_id(self, mock_rollback, mock_commit, mock_commit_check):
        mock_commit_check.return_value = True
        junos.rollback(id=5)
        mock_rollback.assert_called_with(5)

    @patch('jnpr.junos.utils.config.Config.commit_check')
    @patch('jnpr.junos.utils.config.Config.commit')
    @patch('jnpr.junos.utils.config.Config.rollback')
    def test_rollback_with_id_and_single_arg(self, mock_rollback, mock_commit, mock_commit_check):
        mock_commit_check.return_value = True
        args = {'__pub_user': 'root', '__pub_arg': [2, {'confirm': 2}],
                'confirm': 2, '__pub_fun': 'junos.rollback',
                '__pub_jid': '20170221184518526067', '__pub_tgt': 'mac_min',
                '__pub_tgt_type': 'glob', '__pub_ret': ''}
        junos.rollback(2, **args)
        mock_rollback.assert_called_with(2)
        mock_commit.assert_called_with(confirm=2)

    @patch('jnpr.junos.utils.config.Config.commit_check')
    @patch('jnpr.junos.utils.config.Config.commit')
    @patch('jnpr.junos.utils.config.Config.rollback')
    def test_rollback_with_id_and_multiple_args(self, mock_rollback, mock_commit, mock_commit_check):
        mock_commit_check.return_value = True
        args = {'comment': 'Comitted via salt', '__pub_user': 'root', 'dev_timeout': 40,
                '__pub_arg': [2, {'comment': 'Comitted via salt', 'timeout': 40,
                'confirm': 1}], 'confirm': 1, '__pub_fun': 'junos.rollback',
                '__pub_jid': '20170221192708251721', '__pub_tgt': 'mac_min',
                '__pub_tgt_type': 'glob', '__pub_ret': ''}
        junos.rollback(id=2, **args)
        mock_rollback.assert_called_with(2)
        mock_commit.assert_called_with(comment='Comitted via salt', confirm=1, timeout=40)

    @patch('jnpr.junos.utils.config.Config.commit_check')
    @patch('jnpr.junos.utils.config.Config.commit')
    @patch('jnpr.junos.utils.config.Config.rollback')
    def test_rollback_with_only_single_arg(self, mock_rollback, mock_commit, mock_commit_check):
        mock_commit_check.return_value = True
        args = {'__pub_user': 'root', '__pub_arg': [{'sync': True}], 'sync': True,
                '__pub_fun': 'junos.rollback', '__pub_jid': '20170221193615696475',
                '__pub_tgt': 'mac_min', '__pub_tgt_type': 'glob', '__pub_ret': ''}
        junos.rollback(**args)
        mock_rollback.assert_called_once_with(0)
        mock_commit.assert_called_once_with(sync=True)

    @patch('jnpr.junos.utils.config.Config.commit_check')
    @patch('jnpr.junos.utils.config.Config.commit')
    @patch('jnpr.junos.utils.config.Config.rollback')
    def test_rollback_with_only_multiple_args_no_id(self, mock_rollback, mock_commit, mock_commit_check):
        mock_commit_check.return_value = True
        args = {'comment': 'Comitted via salt', '__pub_user': 'root',
                '__pub_arg': [{'comment': 'Comitted via salt', 'confirm': 3, 'sync': True}],
                'confirm': 3, 'sync': True, '__pub_fun': 'junos.rollback',
                '__pub_jid': '20170221193945996362', '__pub_tgt': 'mac_min',
                '__pub_tgt_type': 'glob', '__pub_ret': ''}
        junos.rollback(**args)
        mock_rollback.assert_called_with(0)
        mock_commit.assert_called_once_with(sync=True, confirm=3, comment='Comitted via salt')

    @patch('salt.modules.junos.fopen')
    @patch('jnpr.junos.utils.config.Config.diff')
    @patch('jnpr.junos.utils.config.Config.commit_check')
    @patch('jnpr.junos.utils.config.Config.commit')
    @patch('jnpr.junos.utils.config.Config.rollback')
    def test_rollback_with_diffs_file_option_when_diff_is_None(self, mock_rollback, mock_commit, mock_commit_check, mock_diff, mock_fopen):
        mock_commit_check.return_value = True
        mock_diff.return_value = 'diff'
        args = {'__pub_user': 'root', '__pub_arg': [{'diffs_file': '/home/regress/diff', 'confirm': 2}],
                'confirm': 2, '__pub_fun': 'junos.rollback', '__pub_jid': '20170221205153884009',
                '__pub_tgt': 'mac_min', '__pub_tgt_type': 'glob', '__pub_ret': '',
                'diffs_file': '/home/regress/diff'}
        junos.rollback(**args)
        mock_fopen.assert_called_with('/home/regress/diff', 'w')

    @patch('salt.modules.junos.fopen')
    @patch('jnpr.junos.utils.config.Config.diff')
    @patch('jnpr.junos.utils.config.Config.commit_check')
    @patch('jnpr.junos.utils.config.Config.commit')
    @patch('jnpr.junos.utils.config.Config.rollback')
    def test_rollback_with_diffs_file_option(self, mock_rollback, mock_commit, mock_commit_check, mock_diff, mock_fopen):
        mock_commit_check.return_value = True
        mock_diff.return_value = None
        args = {'__pub_user': 'root', '__pub_arg': [{'diffs_file': '/home/regress/diff', 'confirm': 2}],
                'confirm': 2, '__pub_fun': 'junos.rollback', '__pub_jid': '20170221205153884009',
                '__pub_tgt': 'mac_min', '__pub_tgt_type': 'glob', '__pub_ret': '',
                'diffs_file': '/home/regress/diff'}
        junos.rollback(**args)
        assert not mock_fopen.called

    @patch('jnpr.junos.utils.config.Config.diff')
    def test_diff_without_args(self, mock_diff):
        junos.diff()
        mock_diff.assert_called_with(rb_id=0)

    @patch('jnpr.junos.utils.config.Config.diff')
    def test_diff_with_arg(self, mock_diff):
        junos.diff(2)
        mock_diff.assert_called_with(rb_id=2)

    def test_ping_without_args(self):
        ret = dict()
        ret['message'] = 'Please specify the destination ip to ping.'
        ret['out'] = False
        self.assertEqual(junos.ping(), ret)


    def test_ping_with_host_ip_only(self):
        print

    def test_cli_without_args(self):
        ret = dict()
        ret['message'] = 'Please provide the CLI command to be executed.'
        ret['out'] = False
        self.assertEqual(junos.cli(), ret)

    def test_shutdown_without_args(self):
        ret = dict()
        ret['message'] = \
            'Provide either one of the arguments: shutdown or reboot.'
        ret['out'] = False
        self.assertEqual(junos.shutdown(), ret)

    @patch('salt.modules.junos.SW.reboot')
#    @patch('jnpr.junos.utils.sw.SW.reboot')
    def test_shutdown_with_reboot_args(self, mock_reboot):
        ret = dict()
        ret['message'] = 'Successfully powered off/rebooted.'
        ret['out'] = True
        args = {'__pub_user': 'root', '__pub_arg': [{'reboot': True}],
                'reboot': True, '__pub_fun': 'junos.shutdown',
                '__pub_jid': '20170222213858582619', '__pub_tgt': 'mac_min',
                '__pub_tgt_type': 'glob', '__pub_ret': ''}
        self.assertEqual(junos.shutdown(**args), ret)
        assert mock_reboot.called

    @patch('salt.modules.junos.SW.poweroff')
    def test_shutdown_with_reboot_args(self, mock_poweroff):
        ret = dict()
        ret['message'] = 'Successfully powered off/rebooted.'
        ret['out'] = True
        args = {'__pub_user': 'root', '__pub_arg': [{'shutdown': True}],
                'reboot': True, '__pub_fun': 'junos.shutdown',
                '__pub_jid': '20170222213858582619', '__pub_tgt': 'mac_min',
                '__pub_tgt_type': 'glob', '__pub_ret': ''}
        self.assertEqual(junos.shutdown(**args), ret)
        assert mock_poweroff.called

    def test_shutdown_with_shutdown_as_false(self):
        ret = dict()
        ret['message'] = 'Nothing to be done.'
        ret['out'] = False
        args = {'__pub_user': 'root', '__pub_arg': [{'shutdown': False}],
                'reboot': True, '__pub_fun': 'junos.shutdown',
                '__pub_jid': '20170222213858582619', '__pub_tgt': 'mac_min',
                '__pub_tgt_type': 'glob', '__pub_ret': ''}
        self.assertEqual(junos.shutdown(**args), ret)

    @patch('salt.modules.junos.SW.poweroff')
    def test_shutdown_with_in_min_arg(self, mock_poweroff):
        args = {'__pub_user': 'root', 'in_min': 10, '__pub_arg': [{'in_min': 10,
                'shutdown': True}], 'reboot': True, '__pub_fun': 'junos.shutdown',
                '__pub_jid': '20170222231445709212', '__pub_tgt': 'mac_min',
                '__pub_tgt_type': 'glob', '__pub_ret': ''}
        junos.shutdown(**args)
        mock_poweroff.assert_called_with(in_min=10)

    @patch('salt.modules.junos.SW.reboot')
    def test_shutdown_with_at_arg(self, mock_reboot):
        args = {'__pub_user': 'root', '__pub_arg': [{'at': '12:00 pm',
                'reboot': True}], 'reboot': True,
                '__pub_fun': 'junos.shutdown', '__pub_jid': '201702276857',
                'at': '12:00 pm', '__pub_tgt': 'mac_min',
                '__pub_tgt_type': 'glob', '__pub_ret': ''}
        junos.shutdown(**args)
        mock_reboot.assert_called_with(at='12:00 pm')

    @patch('salt.modules.junos.SW.poweroff')
    def test_shutdown_fail_with_exception(self, mock_poweroff):
        mock_poweroff.side_effect = self.raise_exception
        args = {'__pub_user': 'root', '__pub_arg': [{'shutdown': True}],
                'shutdown': True, '__pub_fun': 'junos.shutdown',
                '__pub_jid': '20170222213858582619', '__pub_tgt': 'mac_min',
                '__pub_tgt_type': 'glob', '__pub_ret': ''}
        ret = dict()
        ret['message'] = 'Could not poweroff/reboot beacause "dummy exception"'
        ret['out'] = False
        self.assertEqual(junos.shutdown(**args), ret)

    def test_install_config_without_args(self):
        ret = dict()
        ret['message'] = \
            'Please provide the salt path where the configuration is present'
        ret['out'] = False
        self.assertEqual(junos.install_config(), ret)

    @patch('os.path.isfile')
    def test_install_config_cp_fails(self, mock_isfile):
        mock_isfile.return_value = False
        ret = dict()
        ret['message'] = 'Invalid file path.'
        ret['out'] = False
        self.assertEqual(junos.install_config('path'), ret)


    @patch('os.path.isfile')
    @patch('os.path.getsize')
    def test_install_config_file_cp_fails(self, mock_getsize, mock_isfile):
        mock_isfile.return_value = True
        mock_getsize.return_value = 0
        ret = dict()
        ret['message'] = 'Template failed to render'
        ret['out'] = False
        self.assertEqual(junos.install_config('path'), ret)











    @patch('jnpr.junos.device.Device.cli')
    def test_zeroize(self, mock_cli):
        result = junos.zeroize()
        ret = dict()
        ret['out'] = True
        ret['message'] = 'Completed zeroize and rebooted'
        mock_cli.assert_called_once_with('request system zeroize')
        self.assertEqual(result, ret)

    @patch('jnpr.junos.device.Device.cli')
    def test_zeroize_throw_exception(self, mock_cli):
        mock_cli.side_effect = self.raise_exception_for_zeroize
        ret = dict()
        ret['message'] = 'Could not zeroize due to : "dummy exception"'
        ret['out'] = False
        self.assertEqual(junos.zeroize(), ret)

    def test_install_os_without_args(self):
        ret = dict()
        ret['message'] = \
            'Please provide the salt path where the junos image is present.'
        ret['out'] = False
        self.assertEqual(junos.install_os(), ret)

    @patch('os.path.isfile')
    @patch('os.path.getsize')
    def test_install_os_cp_fails(self, mock_getsize, mock_isfile):
        mock_getsize.return_value = 10
        mock_isfile.return_value = False
        ret = dict()
        ret['message'] = 'Invalid image path.'
        ret['out'] = False
        self.assertEqual(junos.install_os('/image/path/'), ret)

    @patch('os.path.isfile')
    @patch('os.path.getsize')
    def test_install_os_image_cp_fails(self, mock_getsize, mock_isfile):  # , mock_mkstemp):
        mock_getsize.return_value = 0
        mock_isfile.return_value = True
        ret = dict()
        ret['message'] = 'Failed to copy image'
        ret['out'] = False
        self.assertEqual(junos.install_os('/image/path/'), ret)


    @patch('jnpr.junos.utils.sw.SW.install')
    @patch('salt.modules.junos.safe_rm')
    @patch('salt.modules.junos.files.mkstemp')
    @patch('os.path.isfile')
    @patch('os.path.getsize')
    def test_install_os(self, mock_getsize, mock_isfile, mock_mkstemp, mock_safe_rm, mock_install):
        mock_getsize.return_value = 10
        mock_isfile.return_value = True
        ret = dict()
        ret['out'] = True
        ret['message'] = 'Installed the os.'
        self.assertEqual(junos.install_os('path'), ret)

    @patch('jnpr.junos.utils.sw.SW.reboot')
    @patch('jnpr.junos.utils.sw.SW.install')
    @patch('salt.modules.junos.safe_rm')
    @patch('salt.modules.junos.files.mkstemp')
    @patch('os.path.isfile')
    @patch('os.path.getsize')
    def test_install_os_with_reboot_arg(self, mock_getsize, mock_isfile, mock_mkstemp, mock_safe_rm, mock_install, mock_reboot):
        mock_getsize.return_value = 10
        mock_isfile.return_value = True
        args = {'__pub_user': 'root', '__pub_arg': [{'reboot': True}],
                'reboot': True, '__pub_fun': 'junos.install_os',
                '__pub_jid': '20170222213858582619', '__pub_tgt': 'mac_min',
                '__pub_tgt_type': 'glob', '__pub_ret': ''}
        ret = dict()
        ret['message'] = 'Successfully installed and rebooted!'
        ret['out'] = True
        self.assertEqual(junos.install_os('path', **args), ret)

    @patch('jnpr.junos.utils.sw.SW.install')
    @patch('salt.modules.junos.safe_rm')
    @patch('salt.modules.junos.files.mkstemp')
    @patch('os.path.isfile')
    @patch('os.path.getsize')
    def test_install_os_pyez_install_throws_exception(self, mock_getsize, mock_isfile, mock_mkstemp, mock_safe_rm, mock_install):
        mock_getsize.return_value = 10
        mock_isfile.return_value = True
        mock_install.side_effect = self.raise_exception_for_install
        ret = dict()
        ret['message'] = 'Installation failed due to: "dummy exception"'
        ret['out'] = False
        self.assertEqual(junos.install_os('path'), ret)

    @patch('jnpr.junos.utils.sw.SW.reboot')
    @patch('jnpr.junos.utils.sw.SW.install')
    @patch('salt.modules.junos.safe_rm')
    @patch('salt.modules.junos.files.mkstemp')
    @patch('os.path.isfile')
    @patch('os.path.getsize')
    def test_install_os_with_reboot_raises_exception(self, mock_getsize, mock_isfile, mock_mkstemp, mock_safe_rm, mock_install,
                                        mock_reboot):
        mock_getsize.return_value = 10
        mock_isfile.return_value = True
        mock_reboot.side_effect = self.raise_exception
        args = {'__pub_user': 'root', '__pub_arg': [{'reboot': True}],
                'reboot': True, '__pub_fun': 'junos.install_os',
                '__pub_jid': '20170222213858582619', '__pub_tgt': 'mac_min',
                '__pub_tgt_type': 'glob', '__pub_ret': ''}
        ret = dict()
        ret['message'] = \
            'Installation successful but reboot failed due to : "dummy exception"'
        ret['out'] = False
        self.assertEqual(junos.install_os('path', **args), ret)

    def test_file_copy_without_args(self):
        ret = dict()
        ret['message'] = \
            'Please provide the absolute path of the file to be copied.'
        ret['out'] = False
        self.assertEqual(junos.file_copy(), ret)

    def test_file_copy_without_dest(self):
        ret = dict()
        ret['message'] = \
            'Please provide the absolute path of the destination where the file is to be copied.'
        ret['out'] = False
        with patch('salt.modules.junos.os.path.isfile') as mck:
            mck.return_value = True
            self.assertEqual(junos.file_copy('/home/user/config.set'), ret)
