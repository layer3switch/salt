# -*- coding: utf-8 -*-
'''
    tests.unit.states.pip_test
    ~~~~~~~~~~~~~~~~~~~~~~~~~~

    :codeauthor: :email:`Pedro Algarvio (pedro@algarvio.me)`
    :copyright: © 2013 by the SaltStack Team, see AUTHORS for more details.
    :license: Apache 2.0, see LICENSE for more details.
'''

# Import python libs
import warnings

# Import Salt Testing libs
from salttesting import skipIf, TestCase
from salttesting.helpers import ensure_in_syspath
ensure_in_syspath('../../')

# Import salt libs
import integration
from salt.states import pip_state as pip
from salt.exceptions import CommandExecutionError

# Import 3rd-party libs
try:
    from mock import MagicMock, patch
    HAS_MOCK = True
except ImportError:
    HAS_MOCK = False

pip.__opts__ = {'test': False}
pip.__salt__ = {'cmd.which_bin': lambda _: 'pip'}


@skipIf(HAS_MOCK is False, 'mock python module is unavailable')
class PipStateTest(TestCase, integration.SaltReturnAssertsMixIn):

    def test_installed_deprecated_runas(self):
        # We *always* want *all* warnings thrown on this module
        warnings.resetwarnings()
        warnings.filterwarnings('always', '', DeprecationWarning, __name__)

        mock = MagicMock(return_value={'retcode': 0, 'stdout': ''})
        pip_list = MagicMock(return_value=[])
        pip_install = MagicMock(return_value={'retcode': 0})
        with patch.dict(pip.__salt__, {'cmd.run_all': mock,
                                       'pip.list': pip_list,
                                       'pip.install': pip_install}):
            with warnings.catch_warnings(record=True) as w:
                ret = pip.installed('pep8', runas='me!')
                self.assertEqual(
                    'The \'runas\' argument to pip.installed is deprecated, '
                    'and will be removed in 0.18.0. Please use \'user\' '
                    'instead.', str(w[-1].message)
                )
                self.assertSaltTrueReturn({'testsuite': ret})
                # Is the state returning a warnings key with the deprecation
                # message?
                self.assertInSalStatetWarning(
                    'The \'runas\' argument to pip.installed is deprecated, '
                    'and will be removed in 0.18.0. Please use \'user\' '
                    'instead.', {'testsuite': ret}
                )

    def test_installed_runas_and_user_raises_exception(self):
        mock = MagicMock(return_value={'retcode': 0, 'stdout': ''})
        with patch.dict(pip.__salt__, {'cmd.run_all': mock}):
            self.assertRaises(
                CommandExecutionError,
                pip.installed,
                'pep8',
                user='Me!',
                runas='Not Me!'
            )

    def test_removed_deprecated_runas(self):
        # We *always* want *all* warnings thrown on this module
        warnings.resetwarnings()
        warnings.filterwarnings('always', '', DeprecationWarning, __name__)

        mock = MagicMock(return_value={'retcode': 0, 'stdout': ''})
        pip_list = MagicMock(return_value=['pep8'])
        pip_uninstall = MagicMock(return_value=True)
        with patch.dict(pip.__salt__, {'cmd.run_all': mock,
                                       'pip.list': pip_list,
                                       'pip.uninstall': pip_uninstall}):
            with warnings.catch_warnings(record=True) as w:
                ret = pip.removed('pep8', runas='me!')
                self.assertEqual(
                    'The \'runas\' argument to pip.installed is deprecated, '
                    'and will be removed in 0.18.0. Please use \'user\' '
                    'instead.', str(w[-1].message)
                )
                self.assertSaltTrueReturn({'testsuite': ret})
                # Is the state returning a warnings key with the deprecation
                # message?
                self.assertInSalStatetWarning(
                    'The \'runas\' argument to pip.installed is deprecated, '
                    'and will be removed in 0.18.0. Please use \'user\' '
                    'instead.', {'testsuite': ret}
                )

    def test_removed_runas_and_user_raises_exception(self):
        mock = MagicMock(return_value={'retcode': 0, 'stdout': ''})
        with patch.dict(pip.__salt__, {'cmd.run_all': mock}):
            self.assertRaises(
                CommandExecutionError,
                pip.removed,
                'pep8',
                user='Me!',
                runas='Not Me!'
            )

    def test_install_requirements_parsing(self):
        mock = MagicMock(return_value={'retcode': 0, 'stdout': ''})
        pip_list = MagicMock(return_value={'pep8': '1.3.3'})
        with patch.dict(pip.__salt__, {'cmd.run_all': mock,
                                       'pip.list': pip_list}):
            with patch.dict(pip.__opts__, {'test': True}):
                ret = pip.installed('pep8=1.3.2')
                self.assertSaltFalseReturn({'test': ret})
                self.assertInSaltComment(
                    'Invalid version specification in package pep8=1.3.2. '
                    '\'=\' is not supported, use \'==\' instead.',
                    {'test': ret}
                )

        mock = MagicMock(return_value={'retcode': 0, 'stdout': ''})
        pip_list = MagicMock(return_value={'pep8': '1.3.3'})
        with patch.dict(pip.__salt__, {'cmd.run_all': mock,
                                       'pip.list': pip_list}):
            with patch.dict(pip.__opts__, {'test': True}):
                ret = pip.installed('pep8>=1.3.2')
                self.assertSaltTrueReturn({'test': ret})
                self.assertInSaltComment(
                    'Python package pep8>=1.3.2 already installed',
                    {'test': ret}
                )

        mock = MagicMock(return_value={'retcode': 0, 'stdout': ''})
        pip_list = MagicMock(return_value={'pep8': '1.3.3'})
        with patch.dict(pip.__salt__, {'cmd.run_all': mock,
                                       'pip.list': pip_list}):
            with patch.dict(pip.__opts__, {'test': True}):
                ret = pip.installed('pep8<1.3.2')
                self.assertSaltNoneReturn({'test': ret})
                self.assertInSaltComment(
                    'Python package pep8<1.3.2 is set to be installed',
                    {'test': ret}
                )

        mock = MagicMock(return_value={'retcode': 0, 'stdout': ''})
        pip_list = MagicMock(return_value={'pep8': '1.3.2'})
        with patch.dict(pip.__salt__, {'cmd.run_all': mock,
                                       'pip.list': pip_list}):
            with patch.dict(pip.__opts__, {'test': True}):
                ret = pip.installed('pep8>1.3.1,<1.3.3')
                self.assertSaltTrueReturn({'test': ret})
                self.assertInSaltComment(
                    'Python package pep8>1.3.1;<1.3.3 already installed',
                    {'test': ret}
                )

        mock = MagicMock(return_value={'retcode': 0, 'stdout': ''})
        pip_list = MagicMock(return_value={'pep8': '1.3.1'})
        with patch.dict(pip.__salt__, {'cmd.run_all': mock,
                                       'pip.list': pip_list}):
            with patch.dict(pip.__opts__, {'test': True}):
                ret = pip.installed('pep8>1.3.1,<1.3.3')
                self.assertSaltNoneReturn({'test': ret})
                self.assertInSaltComment(
                    'Python package pep8>1.3.1;<1.3.3 is set to be installed',
                    {'test': ret}
                )

        mock = MagicMock(return_value={'retcode': 0, 'stdout': ''})
        pip_list = MagicMock(return_value={'pep8': '1.3.1'})
        with patch.dict(pip.__salt__, {'cmd.run_all': mock,
                                       'pip.list': pip_list}):
            with patch.dict(pip.__opts__, {'test': True}):
                ret = pip.installed(
                    'git+https://github.com/saltstack/salt-testing.git#egg=SaltTesting>=0.5.1'
                )
                self.assertSaltNoneReturn({'test': ret})
                self.assertInSaltComment(
                    'Python package git+https://github.com/saltstack/'
                    'salt-testing.git#egg=SaltTesting>=0.5.1 is set to be '
                    'installed',
                    {'test': ret}
                )

        mock = MagicMock(return_value={'retcode': 0, 'stdout': ''})
        pip_list = MagicMock(return_value={'pep8': '1.3.1'})
        with patch.dict(pip.__salt__, {'cmd.run_all': mock,
                                       'pip.list': pip_list}):
            with patch.dict(pip.__opts__, {'test': True}):
                ret = pip.installed(
                    'https://pypi.python.org/packages/source/S/SaltTesting/'
                    'SaltTesting-0.5.0.tar.gz'
                    '#md5=e6760af92b7165f8be53b5763e40bc24'
                )
                self.assertSaltNoneReturn({'test': ret})
                self.assertInSaltComment(
                    'Python package https://pypi.python.org/packages/source/'
                    'S/SaltTesting/SaltTesting-0.5.0.tar.gz'
                    '#md5=e6760af92b7165f8be53b5763e40bc24 is set to be '
                    'installed',
                    {'test': ret}
                )

        mock = MagicMock(return_value={'retcode': 0, 'stdout': ''})
        pip_list = MagicMock(return_value={'SaltTesting': '0.5.0'})
        pip_install = MagicMock(return_value={
            'retcode': 0,
            'stderr' :'',
            'stdout': 'Downloading/unpacking https://pypi.python.org/packages'
                      '/source/S/SaltTesting/SaltTesting-0.5.0.tar.gz\n  '
                      'Downloading SaltTesting-0.5.0.tar.gz\n  Running '
                      'setup.py egg_info for package from '
                      'https://pypi.python.org/packages/source/S/SaltTesting/'
                      'SaltTesting-0.5.0.tar.gz\n    \nCleaning up...'
        })
        with patch.dict(pip.__salt__, {'cmd.run_all': mock,
                                       'pip.list': pip_list,
                                       'pip.install': pip_install}):
            ret = pip.installed(
                'https://pypi.python.org/packages/source/S/SaltTesting/'
                'SaltTesting-0.5.0.tar.gz'
                '#md5=e6760af92b7165f8be53b5763e40bc24'
            )
            self.assertSaltTrueReturn({'test': ret})
            self.assertInSaltComment(
                'There was no error installing package '
                '\'https://pypi.python.org/packages/source/S/SaltTesting/'
                'SaltTesting-0.5.0.tar.gz#md5=e6760af92b7165f8be53b5763e40bc24\' '
                'although it does not show when calling \'pip.freeze\'.',
                {'test': ret}
            )
            self.assertInSaltReturn(
                'Installed',
                {'test': ret},
                ('changes', 'https://pypi.python.org/packages/source/S/'
                            'SaltTesting/SaltTesting-0.5.0.tar.gz'
                            '#md5=e6760af92b7165f8be53b5763e40bc24==???')
            )


if __name__ == '__main__':
    from integration import run_tests
    run_tests(PipStateTest, needs_daemon=False)
