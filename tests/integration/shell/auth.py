# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Pedro Algarvio (pedro@algarvio.me)`


    tests.integration.shell.cp
    ~~~~~~~~~~~~~~~~~~~~~~~~~~
'''

# Import python libs
import os
import yaml
import pipes
import shutil

# Import Salt Testing libs
from salttesting.helpers import ensure_in_syspath
ensure_in_syspath('../../')

# Import salt libs
import integration
import salt.utils

from salttesting import skipIf


class AuthTest(integration.ShellCase, integration.ShellCaseCommonTestsMixIn):

    _call_binary_ = 'salt'

    is_root = os.geteuid() != 0

    @skipIf(is_root, 'You must be logged in as root to run this test')
    def test_pam_auth_valid_user(self):
        '''
        test pam auth mechanism is working with a valid user
        '''
        cmd = '-a pam \* test.ping --username saltdev --password ubuntu'
        resp = self.run_salt(cmd)
        self.assertTrue(
            'minion:' in resp
        )

    @skipIf(is_root, 'You must be logged in as root to run this test')
    def test_pam_auth_invalid_user(self):
        '''
        test pam auth mechanism errors for an invalid user
        '''
        cmd = '-a pam \* test.ping --username nouser --password ubuntu'
        resp = self.run_salt(cmd)
        self.assertTrue(
            'Failed to authenticate' in ''.join(resp)
        )


    # def test_cp_testfile(self):
    #     '''
    #     test salt-cp
    #     '''
    #     print self.run_salt('-a pam \* test.ping --username ubuntu --password ubuntu')
    #     print self.run_salt('\* test.ping')
    #     self.assertTrue(False)
        # minions = []

        # for line in self.run_salt('--out yaml "*" test.ping'):
        #     if not line:
        #         continue
        #     data = yaml.load(line)
        #     minions.extend(data.keys())

        # self.assertNotEqual(minions, [])

        # testfile = os.path.abspath(
        #     os.path.join(
        #         os.path.dirname(os.path.dirname(__file__)),
        #         'files', 'file', 'base', 'testfile'
        #     )
        # )
        # testfile_contents = salt.utils.fopen(testfile, 'r').read()

        # for idx, minion in enumerate(minions):
        #     ret = self.run_salt(
        #         '--out yaml {0} file.directory_exists {1}'.format(
        #             pipes.quote(minion), integration.TMP
        #         )
        #     )
        #     data = yaml.load('\n'.join(ret))
        #     if data[minion] is False:
        #         ret = self.run_salt(
        #             '--out yaml {0} file.makedirs {1}'.format(
        #                 pipes.quote(minion),
        #                 integration.TMP
        #             )
        #         )

        #         data = yaml.load('\n'.join(ret))
        #         self.assertTrue(data[minion])

        #     minion_testfile = os.path.join(
        #         integration.TMP, 'cp_{0}_testfile'.format(idx)
        #     )

        #     ret = self.run_cp('{0} {1} {2}'.format(
        #         pipes.quote(minion),
        #         pipes.quote(testfile),
        #         pipes.quote(minion_testfile)
        #     ))

        #     data = yaml.load('\n'.join(ret))
        #     for part in data.values():
        #         self.assertTrue(part[minion_testfile])

        #     ret = self.run_salt(
        #         '--out yaml {0} file.file_exists {1}'.format(
        #             pipes.quote(minion),
        #             pipes.quote(minion_testfile)
        #         )
        #     )
        #     data = yaml.load('\n'.join(ret))
        #     self.assertTrue(data[minion])

        #     ret = self.run_salt(
        #         '--out yaml {0} file.contains {1} {2}'.format(
        #             pipes.quote(minion),
        #             pipes.quote(minion_testfile),
        #             pipes.quote(testfile_contents)
        #         )
        #     )
        #     data = yaml.load('\n'.join(ret))
        #     self.assertTrue(data[minion])
        #     ret = self.run_salt(
        #         '--out yaml {0} file.remove {1}'.format(
        #             pipes.quote(minion),
        #             pipes.quote(minion_testfile)
        #         )
        #     )
        #     data = yaml.load('\n'.join(ret))
        #     self.assertTrue(data[minion])

if __name__ == '__main__':
    from integration import run_tests
    run_tests(AuthTest)
