'''
tests for user state
user absent
user present
user present with custom homedir
'''
import os
from saltunittest import skipIf, destructiveTest
import integration
import grp


class UserTest(integration.ModuleCase,
               integration.SaltReturnAssertsMixIn):
    '''
    test for user absent
    '''
    def test_user_absent(self):
        ret = self.run_state('user.absent', name='unpossible')
        self.assertSaltTrueReturn(ret)

    def test_user_if_present(self):
        ret = self.run_state('user.present', name='nobody')
        self.assertSaltTrueReturn(ret)

    def test_user_if_present_with_gid(self):
        # TODO:dc fix failing test. Exception in ret
        ret = self.run_state('user.present', name='nobody', gid="nobody")
        self.assertSaltTrueReturn(ret)

    @destructiveTest
    @skipIf(os.geteuid() is not 0, 'you must be this root to run this test')
    def test_user_not_present(self):
        """
        This is a DESTRUCTIVE TEST it creates a new user on the minion.
        And then destroys that user.
        Assume that it will break any system you run it on.
        """
        ret = self.run_state('user.present', name='salt_test')
        self.assertSaltTrueReturn(ret)
        ret = self.run_state('user.absent', name='salt_test')
        self.assertSaltTrueReturn(ret)

    @destructiveTest
    @skipIf(os.geteuid() is not 0, 'you must be this root to run this test')
    def test_user_present_nondefault(self):
        """
        This is a DESTRUCTIVE TEST it creates a new user on the on the minion.
        """
        ret = self.run_state('user.present', name='salt_test',
                             home='/var/lib/salt_test')
        self.assertSaltTrueReturn(ret)
        self.assertTrue(os.path.isdir('/var/lib/salt_test'))
        ret = self.run_state('user.absent', name='salt_test')
        self.assertSaltTrueReturn(ret)

    @destructiveTest
    @skipIf(os.geteuid() is not 0, 'you must be this root to run this test')
    def test_user_present_gid_from_name_default(self):
        """
        This is a DESTRUCTIVE TEST. It creates a new user on the on the minion.
        This is an integration test. Not all systems will automatically create
        a group of the same name as the user, but I don't have access to any.
        If you run the test and it fails, please fix the code it's testing to
        work on your operating system.
        """
        ret = self.run_state('user.present', name='salt_test',
                             gid_from_name=True, home='/var/lib/salt_test')
        self.assertSaltTrueReturn(ret)

        ret = self.run_function('user.info', ['salt_test'])
        self.assertReturnNonEmptySaltType(ret)
        group_name = grp.getgrgid(ret['gid']).gr_name

        self.assertTrue(os.path.isdir('/var/lib/salt_test'))
        self.assertEqual(group_name, 'salt_test')

        ret = self.run_state('user.absent', name='salt_test')
        self.assertSaltTrueReturn(ret)

    @destructiveTest
    @skipIf(os.geteuid() is not 0, 'you must be this root to run this test')
    def test_user_present_gid_from_name(self):
        """
        This is a DESTRUCTIVE TEST it creates a new user on the on the minion.
        This is a unit test, NOT an integration test. We create a group of the
        same name as the user beforehand, so it should all run smoothly.
        """
        ret = self.run_state('group.present', name='salt_test')
        self.assertSaltTrueReturn(ret)
        ret = self.run_state('user.present', name='salt_test',
                             gid_from_name=True, home='/var/lib/salt_test')
        self.assertSaltTrueReturn(ret)

        ret = self.run_function('user.info', ['salt_test'])
        self.assertReturnNonEmptySaltType(ret)
        group_name = grp.getgrgid(ret['gid']).gr_name

        self.assertTrue(os.path.isdir('/var/lib/salt_test'))
        self.assertEqual(group_name, 'salt_test')
        ret = self.run_state('user.absent', name='salt_test')
        self.assertSaltTrueReturn(ret)
        ret = self.run_state('group.absent', name='salt_test')
        self.assertSaltTrueReturn(ret)

    @destructiveTest
    @skipIf(os.geteuid() is not 0, 'you must be root to run this test')
    def test_user_present_groups_is_none(self):
        """
        This is a DESTRUCTIVE TEST, it creates a new user and two groups on the
        minion.
        """
        ret = self.run_state('group.present', name='salt_test')
        self.assertSaltTrueReturn(ret)
        ret = self.run_state('group.present', name='salt_test_2')
        self.assertSaltTrueReturn(ret)
        ret = self.run_state('user.present', name='salt_test',
                             gid_from_name=True, home='/var/lib/salt_test',
                             groups=['salt_test_2'])
        self.assertSaltTrueReturn(ret)

        ret = self.run_function('user.info', ['salt_test'])
        self.assertReturnNonEmptySaltType(ret)
        in_groups = set(ret['groups'])
        self.assertEqual(in_groups, set(['salt_test', 'salt_test_2']))

        ret = self.run_state('user.present', name='salt_test')
        self.assertSaltTrueReturn(ret)

        ret = self.run_function('user.info', ['salt_test'])
        self.assertReturnNonEmptySaltType(ret)
        in_groups = set(ret['groups'])
        self.assertEqual(in_groups, set(['salt_test', 'salt_test_2']))

        ret = self.run_state('user.absent', name='salt_test')
        self.assertSaltTrueReturn(ret)
        ret = self.run_state('group.absent', name='salt_test')
        self.assertSaltTrueReturn(ret)
        ret = self.run_state('group.absent', name='salt_test_2')
        self.assertSaltTrueReturn(ret)

    @destructiveTest
    @skipIf(os.geteuid() is not 0, 'you must be root to run this test')
    def test_user_present_groups_is_empty_list(self):
        """
        This is a DESTRUCTIVE TEST, it creates a new user and two groups on the
        minion.
        """
        ret = self.run_state('group.present', name='salt_test')
        self.assertSaltTrueReturn(ret)
        ret = self.run_state('group.present', name='salt_test_2')
        self.assertSaltTrueReturn(ret)
        ret = self.run_state('user.present', name='salt_test',
                             gid_from_name=True, home='/var/lib/salt_test',
                             groups=['salt_test_2'])
        self.assertSaltTrueReturn(ret)

        ret = self.run_function('user.info', ['salt_test'])
        self.assertReturnNonEmptySaltType(ret)
        in_groups = set(ret['groups'])
        self.assertEqual(in_groups, set(['salt_test', 'salt_test_2']))

        ret = self.run_state('user.present', name='salt_test', groups=[])
        self.assertSaltTrueReturn(ret)

        ret = self.run_function('user.info', ['salt_test'])
        self.assertReturnNonEmptySaltType(ret)
        in_groups = set(ret['groups'])
        self.assertEqual(in_groups, set(['salt_test']))

        ret = self.run_state('user.absent', name='salt_test')
        self.assertSaltTrueReturn(ret)
        ret = self.run_state('group.absent', name='salt_test')
        self.assertSaltTrueReturn(ret)
        ret = self.run_state('group.absent', name='salt_test_2')
        self.assertSaltTrueReturn(ret)


if __name__ == '__main__':
    from integration import run_tests
    run_tests(UserTest)
