# -*- coding: utf-8 -*-
'''
    tests.unit.config_test
    ~~~~~~~~~~~~~~~~~~~~~~

    :codeauthor: :email:`Pedro Algarvio (pedro@algarvio.me)`
    :copyright: © 2012-2013 by the SaltStack Team, see AUTHORS for more details
    :license: Apache 2.0, see LICENSE for more details.
'''

# Import python libs
import os
import shutil
import tempfile

# Import Salt Testing libs
from salttesting import TestCase
from salttesting.helpers import ensure_in_syspath

ensure_in_syspath('../')

# Import salt libs
import salt.minion
import salt.utils
import integration
from salt import config as sconfig


class ConfigTestCase(TestCase):
    def test_proper_path_joining(self):
        fpath = tempfile.mktemp()
        try:
            salt.utils.fopen(fpath, 'w').write(
                "root_dir: /\n"
                "key_logfile: key\n"
            )
            config = sconfig.master_config(fpath)
            # os.path.join behaviour
            self.assertEqual(config['key_logfile'], os.path.join('/', 'key'))
            # os.sep.join behaviour
            self.assertNotEqual(config['key_logfile'], '//key')
        finally:
            if os.path.isfile(fpath):
                os.unlink(fpath)

    def test_common_prefix_stripping(self):
        tempdir = tempfile.mkdtemp()
        try:
            root_dir = os.path.join(tempdir, 'foo', 'bar')
            os.makedirs(root_dir)
            fpath = os.path.join(root_dir, 'config')
            salt.utils.fopen(fpath, 'w').write(
                'root_dir: {0}\n'
                'log_file: {1}\n'.format(root_dir, fpath)
            )
            config = sconfig.master_config(fpath)
            self.assertEqual(config['log_file'], fpath)
        finally:
            if os.path.isdir(tempdir):
                shutil.rmtree(tempdir)

    def test_load_master_config_from_environ_var(self):
        original_environ = os.environ.copy()

        tempdir = tempfile.mkdtemp()
        try:
            env_root_dir = os.path.join(tempdir, 'foo', 'env')
            os.makedirs(env_root_dir)
            env_fpath = os.path.join(env_root_dir, 'config-env')

            salt.utils.fopen(env_fpath, 'w').write(
                'root_dir: {0}\n'
                'log_file: {1}\n'.format(env_root_dir, env_fpath)
            )

            os.environ['SALT_MASTER_CONFIG'] = env_fpath
            # Should load from env variable, not the default configuration file.
            config = sconfig.master_config('/etc/salt/master')
            self.assertEqual(config['log_file'], env_fpath)
            os.environ.clear()
            os.environ.update(original_environ)

            root_dir = os.path.join(tempdir, 'foo', 'bar')
            os.makedirs(root_dir)
            fpath = os.path.join(root_dir, 'config')
            salt.utils.fopen(fpath, 'w').write(
                'root_dir: {0}\n'
                'log_file: {1}\n'.format(root_dir, fpath)
            )
            # Let's set the environment variable, yet, since the configuration
            # file path is not the default one, ie, the user has passed an
            # alternative configuration file form the CLI parser, the
            # environment variable will be ignored.
            os.environ['SALT_MASTER_CONFIG'] = env_fpath
            config = sconfig.master_config(fpath)
            self.assertEqual(config['log_file'], fpath)
            os.environ.clear()
            os.environ.update(original_environ)

        finally:
            if os.path.isdir(tempdir):
                shutil.rmtree(tempdir)

    def test_load_minion_config_from_environ_var(self):
        original_environ = os.environ.copy()

        tempdir = tempfile.mkdtemp()
        try:
            env_root_dir = os.path.join(tempdir, 'foo', 'env')
            os.makedirs(env_root_dir)
            env_fpath = os.path.join(env_root_dir, 'config-env')

            salt.utils.fopen(env_fpath, 'w').write(
                'root_dir: {0}\n'
                'log_file: {1}\n'.format(env_root_dir, env_fpath)
            )

            os.environ['SALT_MINION_CONFIG'] = env_fpath
            # Should load from env variable, not the default configuration file
            config = sconfig.minion_config('/etc/salt/minion')
            self.assertEqual(config['log_file'], env_fpath)
            os.environ.clear()
            os.environ.update(original_environ)

            root_dir = os.path.join(tempdir, 'foo', 'bar')
            os.makedirs(root_dir)
            fpath = os.path.join(root_dir, 'config')
            salt.utils.fopen(fpath, 'w').write(
                'root_dir: {0}\n'
                'log_file: {1}\n'.format(root_dir, fpath)
            )
            # Let's set the environment variable, yet, since the configuration
            # file path is not the default one, ie, the user has passed an
            # alternative configuration file form the CLI parser, the
            # environment variable will be ignored.
            os.environ['SALT_MINION_CONFIG'] = env_fpath
            config = sconfig.minion_config(fpath)
            self.assertEqual(config['log_file'], fpath)
            os.environ.clear()
            os.environ.update(original_environ)
        finally:
            if os.path.isdir(tempdir):
                shutil.rmtree(tempdir)

    def test_load_client_config_from_environ_var(self):
        original_environ = os.environ.copy()
        try:
            tempdir = tempfile.mkdtemp()
            env_root_dir = os.path.join(tempdir, 'foo', 'env')
            os.makedirs(env_root_dir)

            # Let's populate a master configuration file which should not get
            # picked up since the client configuration tries to load the master
            # configuration settings using the provided client configuration
            # file
            master_config = os.path.join(env_root_dir, 'master')
            salt.utils.fopen(master_config, 'w').write(
                'blah: true\n'
                'root_dir: {0}\n'
                'log_file: {1}\n'.format(env_root_dir, master_config)
            )
            os.environ['SALT_MASTER_CONFIG'] = master_config

            # Now the client configuration file
            env_fpath = os.path.join(env_root_dir, 'config-env')
            salt.utils.fopen(env_fpath, 'w').write(
                'root_dir: {0}\n'
                'log_file: {1}\n'.format(env_root_dir, env_fpath)
            )

            os.environ['SALT_CLIENT_CONFIG'] = env_fpath
            # Should load from env variable, not the default configuration file
            config = sconfig.client_config(os.path.expanduser('~/.salt'))
            self.assertEqual(config['log_file'], env_fpath)
            self.assertTrue('blah' not in config)
            os.environ.clear()
            os.environ.update(original_environ)

            root_dir = os.path.join(tempdir, 'foo', 'bar')
            os.makedirs(root_dir)
            fpath = os.path.join(root_dir, 'config')
            salt.utils.fopen(fpath, 'w').write(
                'root_dir: {0}\n'
                'log_file: {1}\n'.format(root_dir, fpath)
            )
            # Let's set the environment variable, yet, since the configuration
            # file path is not the default one, ie, the user has passed an
            # alternative configuration file form the CLI parser, the
            # environment variable will be ignored.
            os.environ['SALT_MASTER_CONFIG'] = env_fpath
            config = sconfig.master_config(fpath)
            self.assertEqual(config['log_file'], fpath)
            os.environ.clear()
            os.environ.update(original_environ)

        finally:
            if os.path.isdir(tempdir):
                shutil.rmtree(tempdir)

    def test_issue_5970_minion_confd_inclusion(self):
        try:
            tempdir = tempfile.mkdtemp()
            minion_config = os.path.join(tempdir, 'minion')
            minion_confd = os.path.join(tempdir, 'minion.d')
            os.makedirs(minion_confd)

            # Let's populate a minion configuration file with some basic
            # settings
            salt.utils.fopen(minion_config, 'w').write(
                'blah: false\n'
                'root_dir: {0}\n'
                'log_file: {1}\n'.format(tempdir, minion_config)
            )

            # Now, let's populate an extra configuration file under minion.d
            # Notice that above we've set blah as False and bellow as True.
            # Since the minion.d files are loaded after the main configuration
            # file so overrides can happen, the final value of blah should be
            # True.
            extra_config = os.path.join(minion_confd, 'extra.conf')
            salt.utils.fopen(extra_config, 'w').write(
                'blah: true\n'
            )

            # Let's load the configuration
            config = sconfig.minion_config(minion_config)

            self.assertEqual(config['log_file'], minion_config)
            # As proven by the assertion below, blah is True
            self.assertTrue(config['blah'])
        finally:
            if os.path.isdir(tempdir):
                shutil.rmtree(tempdir)

    def test_master_confd_inclusion(self):
        try:
            tempdir = tempfile.mkdtemp()
            master_config = os.path.join(tempdir, 'master')
            master_confd = os.path.join(tempdir, 'master.d')
            os.makedirs(master_confd)

            # Let's populate a master configuration file with some basic
            # settings
            salt.utils.fopen(master_config, 'w').write(
                'blah: false\n'
                'root_dir: {0}\n'
                'log_file: {1}\n'.format(tempdir, master_config)
            )

            # Now, let's populate an extra configuration file under master.d
            # Notice that above we've set blah as False and bellow as True.
            # Since the master.d files are loaded after the main configuration
            # file so overrides can happen, the final value of blah should be
            # True.
            extra_config = os.path.join(master_confd, 'extra.conf')
            salt.utils.fopen(extra_config, 'w').write(
                'blah: true\n'
            )

            # Let's load the configuration
            config = sconfig.master_config(master_config)

            self.assertEqual(config['log_file'], master_config)
            # As proven by the assertion below, blah is True
            self.assertTrue(config['blah'])
        finally:
            if os.path.isdir(tempdir):
                shutil.rmtree(tempdir)

    def test_syndic_config(self):
        syndic_conf_path = os.path.join(
            integration.INTEGRATION_TEST_DIR, 'files', 'conf', 'syndic'
        )
        minion_config_path = os.path.join(
            integration.INTEGRATION_TEST_DIR, 'files', 'conf', 'minion'
        )
        syndic_opts = sconfig.syndic_config(
            syndic_conf_path, minion_config_path
        )
        syndic_opts.update(salt.minion.resolve_dns(syndic_opts))
        # id & pki dir are shared & so configured on the minion side
        self.assertEquals(syndic_opts['id'], 'minion')
        self.assertEquals(syndic_opts['pki_dir'], '/tmp/salttest/pki')
        # the rest is configured master side
        self.assertEquals(syndic_opts['master_uri'], 'tcp://127.0.0.1:54506')
        self.assertEquals(syndic_opts['master_port'], 54506)
        self.assertEquals(syndic_opts['master_ip'], '127.0.0.1')
        self.assertEquals(syndic_opts['master'], 'localhost')
        self.assertEquals(syndic_opts['sock_dir'], '/tmp/salttest/minion_sock')
        self.assertEquals(syndic_opts['cachedir'], '/tmp/salttest/cachedir')
        self.assertEquals(syndic_opts['log_file'], '/tmp/salttest/osyndic.log')
        self.assertEquals(syndic_opts['pidfile'], '/tmp/salttest/osyndic.pid')
        # Show that the options of localclient that repub to local master
        # are not merged with syndic ones
        self.assertEquals(syndic_opts['_master_conf_file'], minion_config_path)
        self.assertEquals(syndic_opts['_minion_conf_file'], syndic_conf_path)


if __name__ == '__main__':
    from integration import run_tests
    run_tests(ConfigTestCase, needs_daemon=False)
