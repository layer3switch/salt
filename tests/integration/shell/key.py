# -*- coding: utf-8 -*-

# Import python libs
from __future__ import absolute_import
import os
import yaml
import shutil
import tempfile

# Import Salt Testing libs
from salttesting.helpers import ensure_in_syspath
ensure_in_syspath('../../')

# Import salt libs
import integration
import salt.utils

USERA = 'saltdev'
USERA_PWD = 'saltdev'
HASHED_USERA_PWD = '$6$SALTsalt$ZZFD90fKFWq8AGmmX0L3uBtS9fXL62SrTk5zcnQ6EkD6zoiM3kB88G1Zvs0xm/gZ7WXJRs5nsTBybUvGSqZkT.'


class KeyTest(integration.ShellCase, integration.ShellCaseCommonTestsMixIn):
    '''
    Test salt-key script
    '''

    _call_binary_ = 'salt-key'

    def _add_user(self):
        '''
        helper method to add user
        '''
        try:
            add_user = self.run_call('user.add {0} createhome=False'.format(USERA))
            add_pwd = self.run_call('shadow.set_password {0} \'{1}\''.format(USERA,
                                    USERA_PWD if salt.utils.is_darwin() else HASHED_USERA_PWD))
            self.assertTrue(add_user)
            self.assertTrue(add_pwd)
            user_list = self.run_call('user.list_users')
            self.assertIn(USERA, str(user_list))
        except AssertionError:
            self.run_call('user.delete {0} remove=True'.format(USERA))
            self.skipTest(
                'Could not add user or password, skipping test'
                )

    def _remove_user(self):
        '''
        helper method to remove user
        '''
        user_list = self.run_call('user.list_users')
        for user in user_list:
            if USERA in user:
                self.run_call('user.delete {0} remove=True'.format(USERA))

    def test_list_accepted_args(self):
        '''
        test salt-key -l for accepted arguments
        '''
        for key in ('acc', 'pre', 'den', 'un', 'rej'):
            # These should not trigger any error
            data = self.run_key('-l {0}'.format(key), catch_stderr=True)
            self.assertNotIn('error:', '\n'.join(data[1]))
            data = self.run_key('-l foo-{0}'.format(key), catch_stderr=True)
            self.assertIn('error:', '\n'.join(data[1]))

    def test_list_all(self):
        '''
        test salt-key -L
        '''
        data = self.run_key('-L')
        expect = None
        if self.master_opts['transport'] in ('zeromq', 'tcp'):
            expect = [
                'Accepted Keys:',
                'minion',
                'sub_minion',
                'Denied Keys:',
                'Unaccepted Keys:',
                'Rejected Keys:'
            ]
        elif self.master_opts['transport'] == 'raet':
            expect = [
                'Accepted Keys:',
                'minion',
                'sub_minion',
                'Unaccepted Keys:',
                'Rejected Keys:'
            ]
        self.assertEqual(data, expect)

    def test_list_json_out(self):
        '''
        test salt-key -L --json-out
        '''
        data = self.run_key('-L --out json')
        ret = {}
        try:
            import json
            ret = json.loads('\n'.join(data))
        except ValueError:
            pass

        expect = None
        if self.master_opts['transport'] in ('zeromq', 'tcp'):
            expect = {'minions_rejected': [],
                      'minions_denied': [],
                      'minions_pre': [],
                      'minions': ['minion', 'sub_minion']}
        elif self.master_opts['transport'] == 'raet':
            expect = {'accepted': ['minion', 'sub_minion'],
                      'rejected': [],
                      'pending': []}
        self.assertEqual(ret, expect)

    def test_list_yaml_out(self):
        '''
        test salt-key -L --yaml-out
        '''
        data = self.run_key('-L --out yaml')
        ret = {}
        try:
            import yaml
            ret = yaml.load('\n'.join(data))
        except Exception:
            pass

        expect = []
        if self.master_opts['transport'] in ('zeromq', 'tcp'):
            expect = {'minions_rejected': [],
                      'minions_denied': [],
                      'minions_pre': [],
                      'minions': ['minion', 'sub_minion']}
        elif self.master_opts['transport'] == 'raet':
            expect = {'accepted': ['minion', 'sub_minion'],
                      'rejected': [],
                      'pending': []}
        self.assertEqual(ret, expect)

    def test_list_raw_out(self):
        '''
        test salt-key -L --raw-out
        '''
        data = self.run_key('-L --out raw')
        self.assertEqual(len(data), 1)

        ret = {}
        try:
            import ast
            ret = ast.literal_eval(data[0])
        except ValueError:
            pass

        expect = None
        if self.master_opts['transport'] in ('zeromq', 'tcp'):
            expect = {'minions_rejected': [],
                      'minions_denied': [],
                      'minions_pre': [],
                      'minions': ['minion', 'sub_minion']}
        elif self.master_opts['transport'] == 'raet':
            expect = {'accepted': ['minion', 'sub_minion'],
                      'rejected': [],
                      'pending': []}
        self.assertEqual(ret, expect)

    def test_list_acc(self):
        '''
        test salt-key -l
        '''
        data = self.run_key('-l acc')
        expect = ['Accepted Keys:', 'minion', 'sub_minion']
        self.assertEqual(data, expect)

    def test_list_acc_eauth(self):
        '''
        test salt-key -l with eauth
        '''
        self._add_user()
        data = self.run_key('-l acc --eauth pam --username {0} --password {1}'.format(USERA, USERA_PWD))
        expect = ['Accepted Keys:', 'minion', 'sub_minion']
        self.assertEqual(data, expect)
        self._remove_user()

    def test_list_acc_eauth_bad_creds(self):
        '''
        test salt-key -l with eauth and bad creds
        '''
        self._add_user()
        data = self.run_key('-l acc --eauth pam --username {0} --password wrongpassword'.format(USERA))
        expect = ['Authentication failure of type "eauth" occurred for user {0}.'.format(USERA)]
        self.assertEqual(data, expect)
        self._remove_user()

    def test_list_acc_wrong_eauth(self):
        '''
        test salt-key -l with wrong eauth
        '''
        data = self.run_key('-l acc --eauth wrongeauth --username {0} --password {1}'.format(USERA, USERA_PWD))
        expect = ['The specified external authentication system "wrongeauth" is not available']
        self.assertEqual(data, expect)

    def test_list_un(self):
        '''
        test salt-key -l
        '''
        data = self.run_key('-l un')
        expect = ['Unaccepted Keys:']
        self.assertEqual(data, expect)

    def test_keys_generation(self):
        tempdir = tempfile.mkdtemp(dir=integration.SYS_TMP_DIR)
        arg_str = '--gen-keys minibar --gen-keys-dir {0}'.format(tempdir)
        self.run_key(arg_str)
        try:
            key_names = None
            if self.master_opts['transport'] in ('zeromq', 'tcp'):
                key_names = ('minibar.pub', 'minibar.pem')
            elif self.master_opts['transport'] == 'raet':
                key_names = ('minibar.key',)
            for fname in key_names:
                self.assertTrue(os.path.isfile(os.path.join(tempdir, fname)))
        finally:
            shutil.rmtree(tempdir)

    def test_keys_generation_keysize_minmax(self):
        tempdir = tempfile.mkdtemp(dir=integration.SYS_TMP_DIR)
        arg_str = '--gen-keys minion --gen-keys-dir {0}'.format(tempdir)
        try:
            data, error = self.run_key(
                arg_str + ' --keysize=1024', catch_stderr=True
            )
            self.assertIn(
                'salt-key: error: The minimum value for keysize is 2048', error
            )

            data, error = self.run_key(
                arg_str + ' --keysize=32769', catch_stderr=True
            )
            self.assertIn(
                'salt-key: error: The maximum value for keysize is 32768',
                error
            )
        finally:
            shutil.rmtree(tempdir)

    def test_issue_7754(self):
        old_cwd = os.getcwd()
        config_dir = os.path.join(integration.TMP, 'issue-7754')
        if not os.path.isdir(config_dir):
            os.makedirs(config_dir)

        os.chdir(config_dir)

        config_file_name = 'master'
        with salt.utils.fopen(self.get_config_file_path(config_file_name), 'r') as fhr:
            config = yaml.load(fhr.read())
            config['log_file'] = 'file:///dev/log/LOG_LOCAL3'
            with salt.utils.fopen(os.path.join(config_dir, config_file_name), 'w') as fhw:
                fhw.write(
                    yaml.dump(config, default_flow_style=False)
                )
        ret = self.run_script(
            self._call_binary_,
            '--config-dir {0} -L'.format(
                config_dir
            ),
            timeout=15
        )
        try:
            self.assertIn('minion', '\n'.join(ret))
            self.assertFalse(os.path.isdir(os.path.join(config_dir, 'file:')))
        finally:
            self.chdir(old_cwd)
            if os.path.isdir(config_dir):
                shutil.rmtree(config_dir)


if __name__ == '__main__':
    from integration import run_tests
    run_tests(KeyTest)
