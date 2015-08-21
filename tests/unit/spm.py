# coding: utf-8

# Import Python libs
from __future__ import absolute_import
import os
import shutil
import tarfile
import tempfile

# Import Salt Testing libs
from salttesting import TestCase
from salttesting.helpers import ensure_in_syspath

import salt.config
import salt.spm

ensure_in_syspath('../')


_TMP_SPM = tempfile.mkdtemp()

config = salt.config.minion_config(None)
config['file_roots'] = {'base': [os.path.join(_TMP_SPM, 'salt')]}
config['pillar_roots'] = {'base': [os.path.join(_TMP_SPM, 'pillar')]}

__opts__ = {
    'spm_logfile': os.path.join(_TMP_SPM, 'log'),
    'spm_repos_config': os.path.join(_TMP_SPM, 'etc', 'spm.repos'),
    'spm_cache_dir': os.path.join(_TMP_SPM, 'cache'),
    'spm_build_dir': os.path.join(_TMP_SPM, 'build'),
    'spm_build_exclude': ['.git'],
    'spm_db_provider': 'sqlite3',
    'spm_files_provider': 'roots',
    'spm_db': os.path.join(_TMP_SPM, 'packages.db'),
    'extension_modules': os.path.join(_TMP_SPM, 'modules'),
    'file_roots': {'base': [os.path.join(_TMP_SPM, 'salt')]},
    'pillar_roots': {'base': [os.path.join(_TMP_SPM, 'pillar')]},
    'assume_yes': True,
}

_F1 = {
    'definition': {
        'name': 'formula1',
        'version': '1.2',
        'release': '2',
        'summary': 'test',
        'description': 'testing, nothing to see here',
    }
}

_F1['contents'] = (
    ('FORMULA', ('name: {name}\n'
                 'version: {version}\n'
                 'release: {release}\n'
                 'summary: {summary}\n'
                 'description: {description}').format(**_F1['definition'])),
    ('modules/mod1.py', '# mod1.py'),
    ('modules/mod2.py', '# mod2.py'),
    ('states/state1.sls', '# state1.sls'),
    ('states/state2.sls', '# state2.sls'),
)


class SPMTestUserInterface(salt.spm.SPMUserInterface):
    '''
    Unit test user interface to SPMClient
    '''
    def __init__(self):
        self._status = []
        self._confirm = []

    def status(self, msg):
        self._status.append(msg)

    def confirm(self, action):
        self._confirm.append(action)


class SPMTest(TestCase):
    def setUp(self):
        shutil.rmtree(_TMP_SPM, ignore_errors=True)
        os.mkdir(_TMP_SPM)
        self.ui = SPMTestUserInterface()
        self.client = salt.spm.SPMClient(self.ui, __opts__)

    def tearDown(self):
        shutil.rmtree(_TMP_SPM, ignore_errors=True)

    def _create_formula_files(self, formula):
        fdir = os.path.join(_TMP_SPM, formula['definition']['name'])
        shutil.rmtree(fdir, ignore_errors=True)
        os.mkdir(fdir)
        for path, contents in formula['contents']:
            path = os.path.join(fdir, path)
            dirname, _ = os.path.split(path)
            if not os.path.exists(dirname):
                os.makedirs(dirname)
            with open(path, 'w') as f:
                f.write(contents)
        return fdir

    def test_build_install(self):
        # Build package
        fdir = self._create_formula_files(_F1)
        self.client.run(['build', fdir])
        pkgpath = self.ui._status[-1].split()[-1]
        assert os.path.exists(pkgpath)
        # Install package
        self.client.run(['local', 'install', pkgpath])
        # Check filesystem
        for path, contents in _F1['contents']:
            path = os.path.join(__opts__['file_roots']['base'][0], _F1['definition']['name'], path)
            assert os.path.exists(path)
            assert open(path, 'r').read() == contents
        # Check database
        self.client.run(['info', _F1['definition']['name']])
        lines = self.ui._status[-1].split('\n')
        for key, line in (
                ('name', 'Name: {0}'),
                ('version', 'Version: {0}'),
                ('release', 'Release: {0}'),
                ('summary', 'Summary: {0}')):
            assert line.format(_F1['definition'][key]) in lines


if __name__ == '__main__':
    from integration import run_tests
    run_tests(SPMTest, needs_daemon=False)
