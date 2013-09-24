#!/usr/bin/env python
'''
The setup script for salt
'''

# For Python 2.5.  A no-op on 2.6 and above.
from __future__ import with_statement

import os
import sys
from datetime import datetime
from distutils.cmd import Command
from distutils.command.build import build
from distutils.command.clean import clean

# Change to salt source's directory prior to running any command
try:
    SETUP_DIRNAME = os.path.dirname(__file__)
except NameError:
    # We're most likely being frozen and __file__ triggered this NameError
    # Let's work around that
    SETUP_DIRNAME = os.path.dirname(sys.argv[0])

if SETUP_DIRNAME != '':
    os.chdir(SETUP_DIRNAME)

# Store a reference to the executing platform
IS_WINDOWS_PLATFORM = sys.platform.startswith('win')

# Use setuptools only if the user opts-in by setting the USE_SETUPTOOLS env var
# Or if setuptools was previously imported (which is the case when using
# 'distribute')
# This ensures consistent behavior but allows for advanced usage with
# virtualenv, buildout, and others.
WITH_SETUPTOOLS = False
if 'USE_SETUPTOOLS' in os.environ or 'setuptools' in sys.modules:
    try:
        from setuptools import setup
        from setuptools.command.install import install
        WITH_SETUPTOOLS = True
    except ImportError:
        WITH_SETUPTOOLS = False

if WITH_SETUPTOOLS is False:
    import warnings
    from distutils.command.install import install
    from distutils.core import setup
    warnings.filterwarnings(
        'ignore',
        'Unknown distribution option: \'(tests_require|install_requires|zip_safe)\'',
        UserWarning,
        'distutils.dist'
    )

try:
    # Add the esky bdist target if the module is available
    # may require additional modules depending on platform
    from esky import bdist_esky
    # bbfreeze chosen for its tight integration with distutils
    import bbfreeze
    HAS_ESKY = True
except ImportError:
    HAS_ESKY = False

SALT_VERSION = os.path.join(
    os.path.abspath(SETUP_DIRNAME), 'salt', 'version.py'
)

SALT_REQS = os.path.join(
    os.path.abspath(SETUP_DIRNAME), 'requirements.txt'
)

SALT_SYSPATHS = os.path.join(
    os.path.abspath(SETUP_DIRNAME), 'salt', 'syspaths.py'
)

exec(compile(open(SALT_VERSION).read(), SALT_VERSION, 'exec'))
exec(compile(open(SALT_SYSPATHS).read(), SALT_SYSPATHS, 'exec'))


class TestCommand(Command):
    description = 'Run tests'
    user_options = [
        ('runtests-opts=', 'R', 'Command line options to pass to runtests.py')
    ]

    def initialize_options(self):
        self.runtests_opts = None

    def finalize_options(self):
        pass

    def run(self):
        from subprocess import Popen
        self.run_command('build')
        build_cmd = self.get_finalized_command('build_ext')
        runner = os.path.abspath('tests/runtests.py')
        test_cmd = sys.executable + ' {0}'.format(runner)
        if self.runtests_opts:
            test_cmd += ' {0}'.format(self.runtests_opts)

        print('running test')
        test_process = Popen(
            test_cmd, shell=True,
            stdout=sys.stdout, stderr=sys.stderr,
            cwd=build_cmd.build_lib
        )
        test_process.communicate()
        sys.exit(test_process.returncode)


class Clean(clean):
    def run(self):
        clean.run(self)
        # Let's clean compiled *.py[c,o]
        remove_extensions = ('.pyc', '.pyo')
        for subdir in ('salt', 'tests'):
            root = os.path.join(os.path.dirname(__file__), subdir)
            for dirname, dirnames, filenames in os.walk(root):
                for filename in filenames:
                    for ext in remove_extensions:
                        if filename.endswith(ext):
                            os.remove(os.path.join(dirname, filename))
                            break


INSTALL_VERSION_TEMPLATE = '''\
# This file was auto-generated by salt's setup on \
{date:%A, %d %B %Y @ %H:%m:%S UTC}.

__version__ = {version!r}
__version_info__ = {version_info!r}
'''


INSTALL_SYSPATHS_TEMPLATE = '''\
# This file was auto-generated by salt's setup on \
{date:%A, %d %B %Y @ %H:%m:%S UTC}.

ROOT_DIR = {root_dir!r}
CONFIG_DIR = {config_dir!r}
CACHE_DIR = {cache_dir!r}
SOCK_DIR = {sock_dir!r}
SRV_ROOT_DIR= {srv_root_dir!r}
BASE_FILE_ROOTS_DIR = {base_file_roots_dir!r}
BASE_PILLAR_ROOTS_DIR = {base_pillar_roots_dir!r}
BASE_MASTER_ROOTS_DIR = {base_master_roots_dir!r}
LOGS_DIR = {logs_dir!r}
PIDFILE_DIR = {pidfile_dir!r}
'''


class Build(build):
    def run(self):
        # Run build.run function
        build.run(self)
        if getattr(self.distribution, 'running_salt_install', False):
            # If our install attribute is present and set to True, we'll go
            # ahead and write our install time python modules.

            # Write the version file
            version_file_path = os.path.join(
                self.build_lib, 'salt', '_version.py'
            )
            open(version_file_path, 'w').write(
                INSTALL_VERSION_TEMPLATE.format(
                    date=datetime.utcnow(),
                    version=__version__,
                    version_info=__version_info__
                )
            )

            # Write the system paths file
            system_paths_file_path = os.path.join(
                self.build_lib, 'salt', '_syspaths.py'
            )
            open(system_paths_file_path, 'w').write(
                INSTALL_SYSPATHS_TEMPLATE.format(
                    date=datetime.utcnow(),
                    root_dir=self.distribution.salt_root_dir,
                    config_dir=self.distribution.salt_config_dir,
                    cache_dir=self.distribution.salt_cache_dir,
                    sock_dir=self.distribution.salt_sock_dir,
                    srv_root_dir=self.distribution.salt_srv_root_dir,
                    base_file_roots_dir=self.distribution.salt_base_file_roots_dir,
                    base_pillar_roots_dir=self.distribution.salt_base_pillar_roots_dir,
                    base_master_roots_dir=self.distribution.salt_base_master_roots_dir,
                    logs_dir=self.distribution.salt_logs_dir,
                    pidfile_dir=self.distribution.salt_pidfile_dir,
                )
            )


class Install(install):
    user_options = install.user_options + [
        ('salt-root-dir=', None,
         'Salt\'s pre-configured root directory'),
        ('salt-config-dir=', None,
         'Salt\'s pre-configured configuration directory'),
        ('salt-cache-dir=', None,
         'Salt\'s pre-configured cache directory'),
        ('salt-sock-dir=', None,
         'Salt\'s pre-configured socket directory'),
        ('salt-srv-root-dir=', None,
         'Salt\'s pre-configured service directory'),
        ('salt-base-file-roots-dir=', None,
         'Salt\'s pre-configured file roots directory'),
        ('salt-base-pillar-roots-dir=', None,
         'Salt\'s pre-configured pillar roots directory'),
        ('salt-base-master-roots-dir=', None,
         'Salt\'s pre-configured master roots directory'),
        ('salt-logs-dir=', None,
         'Salt\'s pre-configured logs directory'),
        ('salt-pidfile-dir=', None,
         'Salt\'s pre-configured pidfiles directory'),
    ]

    def initialize_options(self):
        install.initialize_options(self)
        self.salt_root_dir = ROOT_DIR
        self.salt_config_dir = CONFIG_DIR
        self.salt_cache_dir = CACHE_DIR
        self.salt_sock_dir = SOCK_DIR
        self.salt_srv_root_dir = SRV_ROOT_DIR
        self.salt_base_file_roots_dir = BASE_FILE_ROOTS_DIR
        self.salt_base_pillar_roots_dir = BASE_PILLAR_ROOTS_DIR
        self.salt_base_master_roots_dir = BASE_MASTER_ROOTS_DIR
        self.salt_logs_dir = LOGS_DIR
        self.salt_pidfile_dir = PIDFILE_DIR

    def finalize_options(self):
        install.finalize_options(self)
        for optname in ('root_dir', 'config_dir', 'cache_dir', 'sock_dir',
                        'srv_root_dir', 'base_file_roots_dir',
                        'base_pillar_roots_dir', 'base_master_roots_dir',
                        'logs_dir', 'pidfile_dir'):
            optvalue = getattr(self, 'salt_{0}'.format(optname))
            if not optvalue:
                raise RuntimeError(
                    'The value of --salt-{0} needs a proper path value'.format(
                        optname.replace('_', '-')
                    )
                )
            setattr(self.distribution, 'salt_{0}'.format(optname), optvalue)

    def run(self):
        # Let's set the running_salt_install attribute so we can add
        # _version.py in the build command
        self.distribution.running_salt_install = True
        # Run install.run
        install.run(self)


NAME = 'salt'
VER = __version__
DESC = ('Portable, distributed, remote execution and '
        'configuration management system')

with open(SALT_REQS) as f:
    REQUIREMENTS = [line for line in f.read().split('\n') if line]


SETUP_KWARGS = {'name': NAME,
                'version': VER,
                'description': DESC,
                'author': 'Thomas S Hatch',
                'author_email': 'thatch45@gmail.com',
                'url': 'http://saltstack.org',
                'cmdclass': {
                    'test': TestCommand,
                    'clean': Clean,
                    'build': Build,
                    'install': Install
                },
                'classifiers': ['Programming Language :: Python',
                                'Programming Language :: Cython',
                                'Programming Language :: Python :: 2.6',
                                'Programming Language :: Python :: 2.7',
                                'Development Status :: 5 - Production/Stable',
                                'Environment :: Console',
                                'Intended Audience :: Developers',
                                'Intended Audience :: Information Technology',
                                'Intended Audience :: System Administrators',
                                ('License :: OSI Approved ::'
                                 ' Apache Software License'),
                                'Operating System :: POSIX :: Linux',
                                'Topic :: System :: Clustering',
                                'Topic :: System :: Distributed Computing',
                                ],
                'packages': ['salt',
                             'salt.cli',
                             'salt.client',
                             'salt.client.ssh',
                             'salt.client.ssh.wrapper',
                             'salt.ext',
                             'salt.auth',
                             'salt.wheel',
                             'salt.tops',
                             'salt.grains',
                             'salt.modules',
                             'salt.pillar',
                             'salt.renderers',
                             'salt.returners',
                             'salt.runners',
                             'salt.states',
                             'salt.fileserver',
                             'salt.search',
                             'salt.output',
                             'salt.utils',
                             'salt.roster',
                             'salt.log',
                             'salt.log.handlers',
                             ],
                'package_data': {'salt.templates': ['rh_ip/*.jinja']},
                'data_files': [('share/man/man1',
                                ['doc/man/salt-master.1',
                                 'doc/man/salt-key.1',
                                 'doc/man/salt.1',
                                 'doc/man/salt-cp.1',
                                 'doc/man/salt-call.1',
                                 'doc/man/salt-syndic.1',
                                 'doc/man/salt-run.1',
                                 'doc/man/salt-ssh.1',
                                 'doc/man/salt-minion.1',
                                 ]),
                               ('share/man/man7', ['doc/man/salt.7']),
                               ],
                # Required for esky builds
                'install_requires': REQUIREMENTS,
                # The dynamic module loading in salt.modules makes this
                # package zip unsafe. Required for esky builds
                'zip_safe': False
                }


# bbfreeze explicit includes
# Sometimes the auto module traversal doesn't find everything, so we
# explicitly add it. The auto dependency tracking especially does not work for
# imports occurring in salt.modules, as they are loaded at salt runtime.
# Specifying includes that don't exist doesn't appear to cause a freezing
# error.
FREEZER_INCLUDES = [
    'zmq.core.*',
    'zmq.utils.*',
    'ast',
    'difflib',
    'distutils',
    'distutils.version',
    'numbers',
    'json',
]

if IS_WINDOWS_PLATFORM:
    FREEZER_INCLUDES.extend([
        'win32api',
        'win32file',
        'win32con',
        'win32security',
        'ntsecuritycon',
        '_winreg',
        'wmi',
    ])
    SETUP_KWARGS['install_requires'].append('WMI')
elif sys.platform.startswith('linux'):
    FREEZER_INCLUDES.append('spwd')
    try:
        import yum
        FREEZER_INCLUDES.append('yum')
    except ImportError:
        pass

if HAS_ESKY:
    # if the user has the esky / bbfreeze libraries installed, add the
    # appropriate kwargs to setup
    OPTIONS = SETUP_KWARGS.get('options', {})
    OPTIONS['bdist_esky'] = {
        'freezer_module': 'bbfreeze',
        'freezer_options': {
            'includes': FREEZER_INCLUDES
        }
    }
    SETUP_KWARGS['options'] = OPTIONS

if WITH_SETUPTOOLS:
    SETUP_KWARGS['entry_points'] = {
        'console_scripts': ['salt-master = salt.scripts:salt_master',
                            'salt-minion = salt.scripts:salt_minion',
                            'salt-syndic = salt.scripts:salt_syndic',
                            'salt-key = salt.scripts:salt_key',
                            'salt-cp = salt.scripts:salt_cp',
                            'salt-call = salt.scripts:salt_call',
                            'salt-run = salt.scripts:salt_run',
                            'salt-ssh = salt.scripts:salt_ssh',
                            'salt = salt.scripts:salt_main'
                            ],
    }

    # Required for running the tests suite
    SETUP_KWARGS['dependency_links'] = [
        'https://github.com/saltstack/salt-testing/tarball/develop#egg=SaltTesting'
    ]
    SETUP_KWARGS['tests_require'] = ['SaltTesting']
else:
    SETUP_KWARGS['scripts'] = ['scripts/salt-master',
                               'scripts/salt-minion',
                               'scripts/salt-syndic',
                               'scripts/salt-key',
                               'scripts/salt-cp',
                               'scripts/salt-call',
                               'scripts/salt-run',
                               'scripts/salt-ssh',
                               'scripts/salt']

if __name__ == '__main__':
    setup(**SETUP_KWARGS)
