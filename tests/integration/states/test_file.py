# -*- coding: utf-8 -*-

'''
Tests for the file state
'''

# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals
import errno
import logging
import os
import re
import sys
import shutil
import stat
import tempfile
import textwrap
import filecmp

log = logging.getLogger(__name__)

# Import Salt Testing libs
from tests.support.case import ModuleCase
from tests.support.unit import skipIf
from tests.support.paths import FILES, TMP, TMP_STATE_TREE
from tests.support.helpers import (
    skip_if_not_root,
    with_system_user_and_group,
    with_tempdir,
    with_tempfile,
    Webserver,
)
from tests.support.mixins import SaltReturnAssertsMixin

# Import Salt libs
import salt.utils.data
import salt.utils.files
import salt.utils.path
import salt.utils.platform
import salt.utils.stringutils

HAS_PWD = True
try:
    import pwd
except ImportError:
    HAS_PWD = False

HAS_GRP = True
try:
    import grp
except ImportError:
    HAS_GRP = False

# Import 3rd-party libs
from salt.ext import six
from salt.ext.six.moves import range  # pylint: disable=import-error,redefined-builtin

IS_WINDOWS = salt.utils.platform.is_windows()

BINARY_FILE = b'GIF89a\x01\x00\x01\x00\x80\x00\x00\x05\x04\x04\x00\x00\x00,\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02D\x01\x00;'

STATE_DIR = os.path.join(FILES, 'file', 'base')
if IS_WINDOWS:
    FILEPILLAR = 'C:\\Windows\\Temp\\filepillar-python'
    FILEPILLARDEF = 'C:\\Windows\\Temp\\filepillar-defaultvalue'
    FILEPILLARGIT = 'C:\\Windows\\Temp\\filepillar-bar'
else:
    FILEPILLAR = '/tmp/filepillar-python'
    FILEPILLARDEF = '/tmp/filepillar-defaultvalue'
    FILEPILLARGIT = '/tmp/filepillar-bar'


def _test_managed_file_mode_keep_helper(testcase, local=False):
    '''
    DRY helper function to run the same test with a local or remote path
    '''
    name = os.path.join(TMP, 'scene33')
    grail_fs_path = os.path.join(FILES, 'file', 'base', 'grail', 'scene33')
    grail = 'salt://grail/scene33' if not local else grail_fs_path

    # Get the current mode so that we can put the file back the way we
    # found it when we're done.
    grail_fs_mode = int(testcase.run_function('file.get_mode', [grail_fs_path]), 8)
    initial_mode = 0o770
    new_mode_1 = 0o600
    new_mode_2 = 0o644

    # Set the initial mode, so we can be assured that when we set the mode
    # to "keep", we're actually changing the permissions of the file to the
    # new mode.
    ret = testcase.run_state(
        'file.managed',
        name=name,
        mode=oct(initial_mode),
        source=grail,
    )

    if IS_WINDOWS:
        testcase.assertSaltFalseReturn(ret)
        return

    testcase.assertSaltTrueReturn(ret)

    try:
        # Update the mode on the fileserver (pass 1)
        os.chmod(grail_fs_path, new_mode_1)
        ret = testcase.run_state(
            'file.managed',
            name=name,
            mode='keep',
            source=grail,
        )
        testcase.assertSaltTrueReturn(ret)
        managed_mode = stat.S_IMODE(os.stat(name).st_mode)
        testcase.assertEqual(oct(managed_mode), oct(new_mode_1))
        # Update the mode on the fileserver (pass 2)
        # This assures us that if the file in file_roots was originally set
        # to the same mode as new_mode_1, we definitely get an updated mode
        # this time.
        os.chmod(grail_fs_path, new_mode_2)
        ret = testcase.run_state(
            'file.managed',
            name=name,
            mode='keep',
            source=grail,
        )
        testcase.assertSaltTrueReturn(ret)
        managed_mode = stat.S_IMODE(os.stat(name).st_mode)
        testcase.assertEqual(oct(managed_mode), oct(new_mode_2))
    except Exception:
        raise
    finally:
        # Set the mode of the file in the file_roots back to what it
        # originally was.
        os.chmod(grail_fs_path, grail_fs_mode)


class FileTest(ModuleCase, SaltReturnAssertsMixin):
    '''
    Validate the file state
    '''
    def tearDown(self):
        '''
        remove files created in previous tests
        '''
        for path in (FILEPILLAR, FILEPILLARDEF, FILEPILLARGIT):
            try:
                os.remove(path)
            except OSError as exc:
                if exc.errno != os.errno.ENOENT:
                    log.error('Failed to remove %s: %s', path, exc)

    def test_symlink(self):
        '''
        file.symlink
        '''
        name = os.path.join(TMP, 'symlink')
        tgt = os.path.join(TMP, 'target')

        # Windows must have a source directory to link to
        if IS_WINDOWS and not os.path.isdir(tgt):
            os.mkdir(tgt)

        # Windows cannot create a symlink if it already exists
        if IS_WINDOWS and self.run_function('file.is_link', [name]):
            self.run_function('file.remove', [name])

        ret = self.run_state('file.symlink', name=name, target=tgt)
        self.assertSaltTrueReturn(ret)

    def test_test_symlink(self):
        '''
        file.symlink test interface
        '''
        name = os.path.join(TMP, 'symlink2')
        tgt = os.path.join(TMP, 'target')
        ret = self.run_state('file.symlink', test=True, name=name, target=tgt)
        self.assertSaltNoneReturn(ret)

    def test_absent_file(self):
        '''
        file.absent
        '''
        name = os.path.join(TMP, 'file_to_kill')
        with salt.utils.files.fopen(name, 'w+') as fp_:
            fp_.write('killme')
        ret = self.run_state('file.absent', name=name)
        self.assertSaltTrueReturn(ret)
        self.assertFalse(os.path.isfile(name))

    def test_absent_dir(self):
        '''
        file.absent
        '''
        name = os.path.join(TMP, 'dir_to_kill')
        if not os.path.isdir(name):
            # left behind... Don't fail because of this!
            os.makedirs(name)
        ret = self.run_state('file.absent', name=name)
        self.assertSaltTrueReturn(ret)
        self.assertFalse(os.path.isdir(name))

    def test_absent_link(self):
        '''
        file.absent
        '''
        name = os.path.join(TMP, 'link_to_kill')
        tgt = '{0}.tgt'.format(name)

        # Windows must have a source directory to link to
        if IS_WINDOWS and not os.path.isdir(tgt):
            os.mkdir(tgt)

        if not self.run_function('file.is_link', [name]):
            self.run_function('file.symlink', [tgt, name])

        ret = self.run_state('file.absent', name=name)

        try:
            self.assertSaltTrueReturn(ret)
            self.assertFalse(self.run_function('file.is_link', [name]))
        finally:
            if self.run_function('file.is_link', [name]):
                self.run_function('file.remove', [name])

    @with_tempfile()
    def test_test_absent(self, name):
        '''
        file.absent test interface
        '''
        with salt.utils.files.fopen(name, 'w+') as fp_:
            fp_.write('killme')
        ret = self.run_state('file.absent', test=True, name=name)
        self.assertSaltNoneReturn(ret)
        self.assertTrue(os.path.isfile(name))

    def test_managed(self):
        '''
        file.managed
        '''
        name = os.path.join(TMP, 'grail_scene33')
        ret = self.run_state(
            'file.managed', name=name, source='salt://grail/scene33'
        )
        src = os.path.join(
            FILES, 'file', 'base', 'grail', 'scene33'
        )
        with salt.utils.files.fopen(src, 'r') as fp_:
            master_data = fp_.read()
        with salt.utils.files.fopen(name, 'r') as fp_:
            minion_data = fp_.read()
        self.assertEqual(master_data, minion_data)
        self.assertSaltTrueReturn(ret)

    def test_managed_file_mode(self):
        '''
        file.managed, correct file permissions
        '''
        desired_mode = 504    # 0770 octal
        name = os.path.join(TMP, 'grail_scene33')
        ret = self.run_state(
            'file.managed', name=name, mode='0770', source='salt://grail/scene33'
        )

        if IS_WINDOWS:
            expected = 'The \'mode\' option is not supported on Windows'
            self.assertEqual(ret[ret.keys()[0]]['comment'], expected)
            self.assertSaltFalseReturn(ret)
            return

        resulting_mode = stat.S_IMODE(
            os.stat(name).st_mode
        )
        self.assertEqual(oct(desired_mode), oct(resulting_mode))
        self.assertSaltTrueReturn(ret)

    def test_managed_file_mode_keep(self):
        '''
        Test using "mode: keep" in a file.managed state
        '''
        _test_managed_file_mode_keep_helper(self, local=False)

    def test_managed_file_mode_keep_local_source(self):
        '''
        Test using "mode: keep" in a file.managed state, with a local file path
        as the source.
        '''
        _test_managed_file_mode_keep_helper(self, local=True)

    def test_managed_file_mode_file_exists_replace(self):
        '''
        file.managed, existing file with replace=True, change permissions
        '''
        initial_mode = 504    # 0770 octal
        desired_mode = 384    # 0600 octal
        name = os.path.join(TMP, 'grail_scene33')
        ret = self.run_state(
            'file.managed', name=name, mode=oct(initial_mode), source='salt://grail/scene33'
        )

        if IS_WINDOWS:
            expected = 'The \'mode\' option is not supported on Windows'
            self.assertEqual(ret[ret.keys()[0]]['comment'], expected)
            self.assertSaltFalseReturn(ret)
            return

        resulting_mode = stat.S_IMODE(
            os.stat(name).st_mode
        )
        self.assertEqual(oct(initial_mode), oct(resulting_mode))

        name = os.path.join(TMP, 'grail_scene33')
        ret = self.run_state(
            'file.managed', name=name, replace=True, mode=oct(desired_mode), source='salt://grail/scene33'
        )
        resulting_mode = stat.S_IMODE(
            os.stat(name).st_mode
        )
        self.assertEqual(oct(desired_mode), oct(resulting_mode))
        self.assertSaltTrueReturn(ret)

    def test_managed_file_mode_file_exists_noreplace(self):
        '''
        file.managed, existing file with replace=False, change permissions
        '''
        initial_mode = 504    # 0770 octal
        desired_mode = 384    # 0600 octal
        name = os.path.join(TMP, 'grail_scene33')
        ret = self.run_state(
            'file.managed', name=name, replace=True, mode=oct(initial_mode), source='salt://grail/scene33'
        )

        if IS_WINDOWS:
            expected = 'The \'mode\' option is not supported on Windows'
            self.assertEqual(ret[ret.keys()[0]]['comment'], expected)
            self.assertSaltFalseReturn(ret)
            return

        ret = self.run_state(
            'file.managed', name=name, replace=False, mode=oct(desired_mode), source='salt://grail/scene33'
        )
        resulting_mode = stat.S_IMODE(
            os.stat(name).st_mode
        )
        self.assertEqual(oct(desired_mode), oct(resulting_mode))
        self.assertSaltTrueReturn(ret)

    def test_managed_file_with_grains_data(self):
        '''
        Test to ensure we can render grains data into a managed
        file.
        '''
        grain_path = os.path.join(TMP, 'file-grain-test')
        self.run_function('grains.set', ['grain_path', grain_path])
        state_file = 'file-grainget'

        self.run_function('state.sls', [state_file])
        self.assertTrue(os.path.exists(grain_path))

        with salt.utils.files.fopen(grain_path, 'r') as fp_:
            file_contents = fp_.readlines()

        self.assertTrue(re.match('^minion$', file_contents[0]))

    def test_managed_file_with_pillar_sls(self):
        '''
        Test to ensure pillar data in sls file
        is rendered properly and file is created.
        '''
        state_name = 'file-pillarget'

        ret = self.run_function('state.sls', [state_name])
        self.assertSaltTrueReturn(ret)

        # Check to make sure the file was created
        check_file = self.run_function('file.file_exists', [FILEPILLAR])
        self.assertTrue(check_file)

    def test_managed_file_with_pillardefault_sls(self):
        '''
        Test to ensure when pillar data is not available
        in sls file with pillar.get it uses the default
        value.
        '''
        state_name = 'file-pillardefaultget'

        ret = self.run_function('state.sls', [state_name])
        self.assertSaltTrueReturn(ret)

        # Check to make sure the file was created
        check_file = self.run_function('file.file_exists', [FILEPILLARDEF])
        self.assertTrue(check_file)

    @skip_if_not_root
    def test_managed_dir_mode(self):
        '''
        Tests to ensure that file.managed creates directories with the
        permissions requested with the dir_mode argument
        '''
        desired_mode = 511  # 0777 in octal
        name = os.path.join(TMP, 'a', 'managed_dir_mode_test_file')
        desired_owner = 'nobody'
        ret = self.run_state(
            'file.managed',
            name=name,
            source='salt://grail/scene33',
            mode=600,
            makedirs=True,
            user=desired_owner,
            dir_mode=oct(desired_mode)  # 0777
        )
        if IS_WINDOWS:
            expected = 'The \'mode\' option is not supported on Windows'
            self.assertEqual(ret[ret.keys()[0]]['comment'], expected)
            self.assertSaltFalseReturn(ret)
            return

        resulting_mode = stat.S_IMODE(
            os.stat(os.path.join(TMP, 'a')).st_mode
        )
        resulting_owner = pwd.getpwuid(os.stat(os.path.join(TMP, 'a')).st_uid).pw_name
        self.assertEqual(oct(desired_mode), oct(resulting_mode))
        self.assertSaltTrueReturn(ret)
        self.assertEqual(desired_owner, resulting_owner)

    def test_test_managed(self):
        '''
        file.managed test interface
        '''
        name = os.path.join(TMP, 'grail_not_not_scene33')
        ret = self.run_state(
            'file.managed', test=True, name=name, source='salt://grail/scene33'
        )
        self.assertSaltNoneReturn(ret)
        self.assertFalse(os.path.isfile(name))

    def test_managed_show_changes_false(self):
        '''
        file.managed test interface
        '''
        name = os.path.join(TMP, 'grail_not_scene33')
        with salt.utils.files.fopen(name, 'wb') as fp_:
            fp_.write(b'test_managed_show_changes_false\n')

        ret = self.run_state(
            'file.managed', name=name, source='salt://grail/scene33',
            show_changes=False
        )

        changes = next(six.itervalues(ret))['changes']
        self.assertEqual('<show_changes=False>', changes['diff'])

    @skipIf(IS_WINDOWS, 'Don\'t know how to fix for Windows')
    def test_managed_escaped_file_path(self):
        '''
        file.managed test that 'salt://|' protects unusual characters in file path
        '''
        funny_file = salt.utils.files.mkstemp(prefix='?f!le? n@=3&', suffix='.file type')
        funny_file_name = os.path.split(funny_file)[1]
        funny_url = 'salt://|' + funny_file_name
        funny_url_path = os.path.join(STATE_DIR, funny_file_name)

        state_name = 'funny_file'
        state_file_name = state_name + '.sls'
        state_file = os.path.join(STATE_DIR, state_file_name)
        state_key = 'file_|-{0}_|-{0}_|-managed'.format(funny_file)

        self.addCleanup(os.remove, state_file)
        self.addCleanup(os.remove, funny_file)
        self.addCleanup(os.remove, funny_url_path)

        with salt.utils.files.fopen(funny_url_path, 'w'):
            pass
        with salt.utils.files.fopen(state_file, 'w') as fp_:
            fp_.write(textwrap.dedent('''\
            {0}:
              file.managed:
                - source: {1}
                - makedirs: True
            '''.format(funny_file, funny_url)))

        ret = self.run_function('state.sls', [state_name])
        self.assertTrue(ret[state_key]['result'])

    def test_managed_contents(self):
        '''
        test file.managed with contents that is a boolean, string, integer,
        float, list, and dictionary
        '''
        state_name = 'file-FileTest-test_managed_contents'
        state_filename = state_name + '.sls'
        state_file = os.path.join(STATE_DIR, state_filename)

        managed_files = {}
        state_keys = {}
        for typ in ('bool', 'str', 'int', 'float', 'list', 'dict'):
            fd_, managed_files[typ] = tempfile.mkstemp()

            # Release the handle so they can be removed in Windows
            try:
                os.close(fd_)
            except OSError as exc:
                if exc.errno != errno.EBADF:
                    raise exc

            state_keys[typ] = 'file_|-{0} file_|-{1}_|-managed'.format(typ, managed_files[typ])
        try:
            with salt.utils.files.fopen(state_file, 'w') as fd_:
                fd_.write(textwrap.dedent('''\
                    bool file:
                      file.managed:
                        - name: {bool}
                        - contents: True

                    str file:
                      file.managed:
                        - name: {str}
                        - contents: Salt was here.

                    int file:
                      file.managed:
                        - name: {int}
                        - contents: 340282366920938463463374607431768211456

                    float file:
                      file.managed:
                        - name: {float}
                        - contents: 1.7518e-45  # gravitational coupling constant

                    list file:
                      file.managed:
                        - name: {list}
                        - contents: [1, 1, 2, 3, 5, 8, 13]

                    dict file:
                      file.managed:
                        - name: {dict}
                        - contents:
                            C: charge
                            P: parity
                            T: time
                    '''.format(**managed_files)))

            ret = self.run_function('state.sls', [state_name])
            for typ in state_keys:
                self.assertTrue(ret[state_keys[typ]]['result'])
                self.assertIn('diff', ret[state_keys[typ]]['changes'])
        finally:
            os.remove(state_file)
            for typ in managed_files:
                os.remove(managed_files[typ])

    @skip_if_not_root
    @skipIf(IS_WINDOWS, 'Windows does not support "mode" kwarg. Skipping.')
    @skipIf(not salt.utils.path.which('visudo'), 'sudo is missing')
    def test_managed_check_cmd(self):
        '''
        Test file.managed passing a basic check_cmd kwarg. See Issue #38111.
        '''
        r_group = 'root'
        if salt.utils.platform.is_darwin():
            r_group = 'wheel'
        try:
            ret = self.run_state(
                'file.managed',
                name='/tmp/sudoers',
                user='root',
                group=r_group,
                mode=440,
                check_cmd='visudo -c -s -f'
            )
            self.assertSaltTrueReturn(ret)
            self.assertInSaltComment('Empty file', ret)
            self.assertEqual(ret['file_|-/tmp/sudoers_|-/tmp/sudoers_|-managed']['changes'],
                             {'new': 'file /tmp/sudoers created', 'mode': '0440'})
        finally:
            # Clean Up File
            if os.path.exists('/tmp/sudoers'):
                os.remove('/tmp/sudoers')

    def test_managed_local_source_with_source_hash(self):
        '''
        Make sure that we enforce the source_hash even with local files
        '''
        name = os.path.join(TMP, 'local_source_with_source_hash')
        local_path = os.path.join(FILES, 'file', 'base', 'grail', 'scene33')
        actual_hash = '567fd840bf1548edc35c48eb66cdd78bfdfcccff'
        # Reverse the actual hash
        bad_hash = actual_hash[::-1]

        def remove_file():
            try:
                os.remove(name)
            except OSError as exc:
                if exc.errno != errno.ENOENT:
                    raise

        def do_test(clean=False):
            for proto in ('file://', ''):
                source = proto + local_path
                log.debug('Trying source %s', source)
                try:
                    ret = self.run_state(
                        'file.managed',
                        name=name,
                        source=source,
                        source_hash='sha1={0}'.format(bad_hash))
                    self.assertSaltFalseReturn(ret)
                    ret = ret[next(iter(ret))]
                    # Shouldn't be any changes
                    self.assertFalse(ret['changes'])
                    # Check that we identified a hash mismatch
                    self.assertIn(
                        'does not match actual checksum', ret['comment'])

                    ret = self.run_state(
                        'file.managed',
                        name=name,
                        source=source,
                        source_hash='sha1={0}'.format(actual_hash))
                    self.assertSaltTrueReturn(ret)
                finally:
                    if clean:
                        remove_file()

        remove_file()
        log.debug('Trying with nonexistant destination file')
        do_test()
        log.debug('Trying with destination file already present')
        with salt.utils.files.fopen(name, 'w'):
            pass
        try:
            do_test(clean=False)
        finally:
            remove_file()

    def test_managed_local_source_does_not_exist(self):
        '''
        Make sure that we exit gracefully when a local source doesn't exist
        '''
        name = os.path.join(TMP, 'local_source_does_not_exist')
        local_path = os.path.join(FILES, 'file', 'base', 'grail', 'scene99')

        for proto in ('file://', ''):
            source = proto + local_path
            log.debug('Trying source %s', source)
            ret = self.run_state(
                'file.managed',
                name=name,
                source=source)
            self.assertSaltFalseReturn(ret)
            ret = ret[next(iter(ret))]
            # Shouldn't be any changes
            self.assertFalse(ret['changes'])
            # Check that we identified a hash mismatch
            self.assertIn(
                'does not exist', ret['comment'])

    def test_directory(self):
        '''
        file.directory
        '''
        name = os.path.join(TMP, 'a_new_dir')
        ret = self.run_state('file.directory', name=name)
        self.assertSaltTrueReturn(ret)
        self.assertTrue(os.path.isdir(name))

    def test_directory_symlink_dry_run(self):
        '''
        Ensure that symlinks are followed when file.directory is run with
        test=True
        '''
        try:
            tmp_dir = os.path.join(TMP, 'pgdata')
            sym_dir = os.path.join(TMP, 'pg_data')

            if IS_WINDOWS:
                self.run_function('file.mkdir', [tmp_dir, 'Administrators'])
            else:
                os.mkdir(tmp_dir, 0o700)

            self.run_function('file.symlink', [tmp_dir, sym_dir])

            if IS_WINDOWS:
                ret = self.run_state(
                    'file.directory', test=True, name=sym_dir,
                    follow_symlinks=True, win_owner='Administrators')
            else:
                ret = self.run_state(
                    'file.directory', test=True, name=sym_dir,
                    follow_symlinks=True, mode=700)

            self.assertSaltTrueReturn(ret)
        finally:
            if os.path.isdir(tmp_dir):
                self.run_function('file.remove', [tmp_dir])
            if os.path.islink(sym_dir):
                self.run_function('file.remove', [sym_dir])

    @skip_if_not_root
    @skipIf(IS_WINDOWS, 'Mode not available in Windows')
    def test_directory_max_depth(self):
        '''
        file.directory
        Test the max_depth option by iteratively increasing the depth and
        checking that no changes deeper than max_depth have been attempted
        '''

        def _get_oct_mode(name):
            '''
            Return a string octal representation of the permissions for name
            '''
            return salt.utils.files.normalize_mode(oct(os.stat(name).st_mode & 0o777))

        top = os.path.join(TMP, 'top_dir')
        sub = os.path.join(top, 'sub_dir')
        subsub = os.path.join(sub, 'sub_sub_dir')
        dirs = [top, sub, subsub]

        initial_mode = '0111'
        changed_mode = '0555'

        if not os.path.isdir(subsub):
            os.makedirs(subsub, int(initial_mode, 8))

        try:
            for depth in range(0, 3):
                ret = self.run_state('file.directory',
                                     name=top,
                                     max_depth=depth,
                                     dir_mode=changed_mode,
                                     recurse=['mode'])
                self.assertSaltTrueReturn(ret)
                for changed_dir in dirs[0:depth+1]:
                    self.assertEqual(changed_mode,
                                     _get_oct_mode(changed_dir))
                for untouched_dir in dirs[depth+1:]:
                    self.assertEqual(initial_mode,
                                     _get_oct_mode(untouched_dir))
        finally:
            shutil.rmtree(top)

    def test_test_directory(self):
        '''
        file.directory
        '''
        name = os.path.join(TMP, 'a_not_dir')
        ret = self.run_state('file.directory', test=True, name=name)
        self.assertSaltNoneReturn(ret)
        self.assertFalse(os.path.isdir(name))

    @with_tempdir()
    def test_directory_clean(self, base_dir):
        '''
        file.directory with clean=True
        '''
        name = os.path.join(base_dir, 'directory_clean_dir')
        os.mkdir(name)

        strayfile = os.path.join(name, 'strayfile')
        with salt.utils.files.fopen(strayfile, 'w'):
            pass

        straydir = os.path.join(name, 'straydir')
        if not os.path.isdir(straydir):
            os.makedirs(straydir)

        with salt.utils.files.fopen(os.path.join(straydir, 'strayfile2'), 'w'):
            pass

        ret = self.run_state('file.directory', name=name, clean=True)
        self.assertSaltTrueReturn(ret)
        self.assertFalse(os.path.exists(strayfile))
        self.assertFalse(os.path.exists(straydir))
        self.assertTrue(os.path.isdir(name))

    @with_tempdir()
    def test_directory_clean_exclude(self, base_dir):
        '''
        file.directory with clean=True and exclude_pat set
        '''
        name = os.path.join(base_dir, 'directory_clean_dir')
        if not os.path.isdir(name):
            os.makedirs(name)

        strayfile = os.path.join(name, 'strayfile')
        with salt.utils.files.fopen(strayfile, 'w'):
            pass

        straydir = os.path.join(name, 'straydir')
        if not os.path.isdir(straydir):
            os.makedirs(straydir)

        strayfile2 = os.path.join(straydir, 'strayfile2')
        with salt.utils.files.fopen(strayfile2, 'w'):
            pass

        keepfile = os.path.join(straydir, 'keepfile')
        with salt.utils.files.fopen(keepfile, 'w'):
            pass

        exclude_pat = 'E@^straydir(|/keepfile)$'
        if IS_WINDOWS:
            exclude_pat = 'E@^straydir(|\\\\keepfile)$'

        ret = self.run_state('file.directory',
                             name=name,
                             clean=True,
                             exclude_pat=exclude_pat)

        self.assertSaltTrueReturn(ret)
        self.assertFalse(os.path.exists(strayfile))
        self.assertFalse(os.path.exists(strayfile2))
        self.assertTrue(os.path.exists(keepfile))

    @with_tempdir()
    def test_test_directory_clean_exclude(self, base_dir):
        '''
        file.directory with test=True, clean=True and exclude_pat set
        '''
        name = os.path.join(base_dir, 'directory_clean_dir')
        os.mkdir(name)

        strayfile = os.path.join(name, 'strayfile')
        with salt.utils.files.fopen(strayfile, 'w'):
            pass

        straydir = os.path.join(name, 'straydir')
        if not os.path.isdir(straydir):
            os.makedirs(straydir)

        strayfile2 = os.path.join(straydir, 'strayfile2')
        with salt.utils.files.fopen(strayfile2, 'w'):
            pass

        keepfile = os.path.join(straydir, 'keepfile')
        with salt.utils.files.fopen(keepfile, 'w'):
            pass

        exclude_pat = 'E@^straydir(|/keepfile)$'
        if IS_WINDOWS:
            exclude_pat = 'E@^straydir(|\\\\keepfile)$'

        ret = self.run_state('file.directory',
                             test=True,
                             name=name,
                             clean=True,
                             exclude_pat=exclude_pat)

        comment = next(six.itervalues(ret))['comment']

        self.assertSaltNoneReturn(ret)
        self.assertTrue(os.path.exists(strayfile))
        self.assertTrue(os.path.exists(strayfile2))
        self.assertTrue(os.path.exists(keepfile))

        self.assertIn(strayfile, comment)
        self.assertIn(strayfile2, comment)
        self.assertNotIn(keepfile, comment)

    def test_directory_clean_require_in(self):
        '''
        file.directory test with clean=True and require_in file
        '''
        state_name = 'file-FileTest-test_directory_clean_require_in'
        state_filename = state_name + '.sls'
        state_file = os.path.join(STATE_DIR, state_filename)

        directory = tempfile.mkdtemp()
        self.addCleanup(lambda: shutil.rmtree(directory))

        wrong_file = os.path.join(directory, "wrong")
        with salt.utils.files.fopen(wrong_file, "w") as fp:
            fp.write("foo")
        good_file = os.path.join(directory, "bar")

        with salt.utils.files.fopen(state_file, 'w') as fp:
            self.addCleanup(lambda: os.remove(state_file))
            fp.write(textwrap.dedent('''\
                some_dir:
                  file.directory:
                    - name: {directory}
                    - clean: true

                {good_file}:
                  file.managed:
                    - require_in:
                      - file: some_dir
                '''.format(directory=directory, good_file=good_file)))

        ret = self.run_function('state.sls', [state_name])
        self.assertTrue(os.path.exists(good_file))
        self.assertFalse(os.path.exists(wrong_file))

    def test_directory_clean_require_in_with_id(self):
        '''
        file.directory test with clean=True and require_in file with an ID
        different from the file name
        '''
        state_name = 'file-FileTest-test_directory_clean_require_in_with_id'
        state_filename = state_name + '.sls'
        state_file = os.path.join(STATE_DIR, state_filename)

        directory = tempfile.mkdtemp()
        self.addCleanup(lambda: shutil.rmtree(directory))

        wrong_file = os.path.join(directory, "wrong")
        with salt.utils.files.fopen(wrong_file, "w") as fp:
            fp.write("foo")
        good_file = os.path.join(directory, "bar")

        with salt.utils.files.fopen(state_file, 'w') as fp:
            self.addCleanup(lambda: os.remove(state_file))
            fp.write(textwrap.dedent('''\
                some_dir:
                  file.directory:
                    - name: {directory}
                    - clean: true

                some_file:
                  file.managed:
                    - name: {good_file}
                    - require_in:
                      - file: some_dir
                '''.format(directory=directory, good_file=good_file)))

        ret = self.run_function('state.sls', [state_name])
        self.assertTrue(os.path.exists(good_file))
        self.assertFalse(os.path.exists(wrong_file))

    def test_directory_clean_require_with_name(self):
        '''
        file.directory test with clean=True and require with a file state
        relatively to the state's name, not its ID.
        '''
        state_name = 'file-FileTest-test_directory_clean_require_in_with_id'
        state_filename = state_name + '.sls'
        state_file = os.path.join(STATE_DIR, state_filename)

        directory = tempfile.mkdtemp()
        self.addCleanup(lambda: shutil.rmtree(directory))

        wrong_file = os.path.join(directory, "wrong")
        with salt.utils.files.fopen(wrong_file, "w") as fp:
            fp.write("foo")
        good_file = os.path.join(directory, "bar")

        with salt.utils.files.fopen(state_file, 'w') as fp:
            self.addCleanup(lambda: os.remove(state_file))
            fp.write(textwrap.dedent('''\
                some_dir:
                  file.directory:
                    - name: {directory}
                    - clean: true
                    - require:
                      # This requirement refers to the name of the following
                      # state, not its ID.
                      - file: {good_file}

                some_file:
                  file.managed:
                    - name: {good_file}
                '''.format(directory=directory, good_file=good_file)))

        ret = self.run_function('state.sls', [state_name])
        self.assertTrue(os.path.exists(good_file))
        self.assertFalse(os.path.exists(wrong_file))

    @with_tempdir(create=False)
    def test_recurse(self, name):
        '''
        file.recurse
        '''
        ret = self.run_state('file.recurse', name=name, source='salt://grail')
        self.assertSaltTrueReturn(ret)
        self.assertTrue(os.path.isfile(os.path.join(name, '36', 'scene')))

    @with_tempdir(create=False)
    @with_tempdir(create=False)
    def test_recurse_specific_env(self, dir1, dir2):
        '''
        file.recurse passing __env__
        '''
        ret = self.run_state('file.recurse',
                             name=dir1,
                             source='salt://holy',
                             __env__='prod')
        self.assertSaltTrueReturn(ret)
        self.assertTrue(os.path.isfile(os.path.join(dir1, '32', 'scene')))

        ret = self.run_state('file.recurse',
                             name=dir2,
                             source='salt://holy',
                             saltenv='prod')
        self.assertSaltTrueReturn(ret)
        self.assertTrue(os.path.isfile(os.path.join(dir2, '32', 'scene')))

    @with_tempdir(create=False)
    @with_tempdir(create=False)
    def test_recurse_specific_env_in_url(self, dir1, dir2):
        '''
        file.recurse passing __env__
        '''
        ret = self.run_state('file.recurse',
                             name=dir1,
                             source='salt://holy?saltenv=prod')
        self.assertSaltTrueReturn(ret)
        self.assertTrue(os.path.isfile(os.path.join(dir1, '32', 'scene')))

        ret = self.run_state('file.recurse',
                             name=dir2,
                             source='salt://holy?saltenv=prod')
        self.assertSaltTrueReturn(ret)
        self.assertTrue(os.path.isfile(os.path.join(dir2, '32', 'scene')))

    @with_tempdir(create=False)
    def test_test_recurse(self, name):
        '''
        file.recurse test interface
        '''
        ret = self.run_state(
            'file.recurse', test=True, name=name, source='salt://grail',
        )
        self.assertSaltNoneReturn(ret)
        self.assertFalse(os.path.isfile(os.path.join(name, '36', 'scene')))
        self.assertFalse(os.path.exists(name))

    @with_tempdir(create=False)
    @with_tempdir(create=False)
    def test_test_recurse_specific_env(self, dir1, dir2):
        '''
        file.recurse test interface
        '''
        ret = self.run_state('file.recurse',
                             test=True,
                             name=dir1,
                             source='salt://holy',
                             __env__='prod'
        )
        self.assertSaltNoneReturn(ret)
        self.assertFalse(os.path.isfile(os.path.join(dir1, '32', 'scene')))
        self.assertFalse(os.path.exists(dir1))

        ret = self.run_state('file.recurse',
                             test=True,
                             name=dir2,
                             source='salt://holy',
                             saltenv='prod'
        )
        self.assertSaltNoneReturn(ret)
        self.assertFalse(os.path.isfile(os.path.join(dir2, '32', 'scene')))
        self.assertFalse(os.path.exists(dir2))

    @with_tempdir(create=False)
    def test_recurse_template(self, name):
        '''
        file.recurse with jinja template enabled
        '''
        _ts = 'TEMPLATE TEST STRING'
        ret = self.run_state(
            'file.recurse', name=name, source='salt://grail',
            template='jinja', defaults={'spam': _ts})
        self.assertSaltTrueReturn(ret)
        with salt.utils.files.fopen(os.path.join(name, 'scene33'), 'r') as fp_:
            contents = fp_.read()
        self.assertIn(_ts, contents)

    @with_tempdir()
    def test_recurse_clean(self, name):
        '''
        file.recurse with clean=True
        '''
        strayfile = os.path.join(name, 'strayfile')
        with salt.utils.files.fopen(strayfile, 'w'):
            pass

        # Corner cases: replacing file with a directory and vice versa
        with salt.utils.files.fopen(os.path.join(name, '36'), 'w'):
            pass
        os.makedirs(os.path.join(name, 'scene33'))
        ret = self.run_state(
            'file.recurse', name=name, source='salt://grail', clean=True)
        self.assertSaltTrueReturn(ret)
        self.assertFalse(os.path.exists(strayfile))
        self.assertTrue(os.path.isfile(os.path.join(name, '36', 'scene')))
        self.assertTrue(os.path.isfile(os.path.join(name, 'scene33')))

    @with_tempdir()
    def test_recurse_clean_specific_env(self, name):
        '''
        file.recurse with clean=True and __env__=prod
        '''
        strayfile = os.path.join(name, 'strayfile')
        with salt.utils.files.fopen(strayfile, 'w'):
            pass

        # Corner cases: replacing file with a directory and vice versa
        with salt.utils.files.fopen(os.path.join(name, '32'), 'w'):
            pass
        os.makedirs(os.path.join(name, 'scene34'))
        ret = self.run_state('file.recurse',
                             name=name,
                             source='salt://holy',
                             clean=True,
                             __env__='prod')
        self.assertSaltTrueReturn(ret)
        self.assertFalse(os.path.exists(strayfile))
        self.assertTrue(os.path.isfile(os.path.join(name, '32', 'scene')))
        self.assertTrue(os.path.isfile(os.path.join(name, 'scene34')))

    @with_tempdir()
    def test_recurse_issue_34945(self, base_dir):
        '''
        This tests the case where the source dir for the file.recurse state
        does not contain any files (only subdirectories), and the dir_mode is
        being managed. For a long time, this corner case resulted in the top
        level of the destination directory being created with the wrong initial
        permissions, a problem that would be corrected later on in the
        file.recurse state via running state.directory. However, the
        file.directory state only gets called when there are files to be
        managed in that directory, and when the source directory contains only
        subdirectories, the incorrectly-set initial perms would not be
        repaired.

        This was fixed in https://github.com/saltstack/salt/pull/35309
        '''
        dir_mode = '2775'
        issue_dir = 'issue-34945'
        name = os.path.join(base_dir, issue_dir)

        ret = self.run_state('file.recurse',
                             name=name,
                             source='salt://' + issue_dir,
                             dir_mode=dir_mode)
        self.assertSaltTrueReturn(ret)
        actual_dir_mode = oct(stat.S_IMODE(os.stat(name).st_mode))[-4:]
        self.assertEqual(dir_mode, actual_dir_mode)

    @with_tempdir(create=False)
    def test_recurse_issue_40578(self, name):
        '''
        This ensures that the state doesn't raise an exception when it
        encounters a file with a unicode filename in the process of invoking
        file.source_list.
        '''
        ret = self.run_state('file.recurse',
                             name=name,
                             source='salt://соль')
        self.assertSaltTrueReturn(ret)
        self.assertEqual(
            sorted(salt.utils.data.decode(os.listdir(name), normalize=True)),
            sorted(['foo.txt', 'спам.txt', 'яйца.txt']),
        )

    @with_tempfile()
    def test_replace(self, name):
        '''
        file.replace
        '''
        with salt.utils.files.fopen(name, 'w+') as fp_:
            fp_.write('change_me')

        ret = self.run_state('file.replace',
                name=name, pattern='change', repl='salt', backup=False)

        with salt.utils.files.fopen(name, 'r') as fp_:
            self.assertIn('salt', fp_.read())

        self.assertSaltTrueReturn(ret)

    @with_tempdir()
    def test_replace_issue_18612(self, base_dir):
        '''
        Test the (mis-)behaviour of file.replace as described in #18612:

        Using 'prepend_if_not_found' or 'append_if_not_found' resulted in
        an infinitely growing file as 'file.replace' didn't check beforehand
        whether the changes had already been done to the file

        # Case description:

        The tested file contains one commented line
        The commented line should be uncommented in the end, nothing else should change
        '''
        test_name = 'test_replace_issue_18612'
        path_test = os.path.join(base_dir, test_name)

        with salt.utils.files.fopen(path_test, 'w+') as fp_test_:
            fp_test_.write('# en_US.UTF-8')

        ret = []
        for x in range(0, 3):
            ret.append(self.run_state('file.replace',
                name=path_test, pattern='^# en_US.UTF-8$', repl='en_US.UTF-8', append_if_not_found=True))

        # ensure, the number of lines didn't change, even after invoking 'file.replace' 3 times
        with salt.utils.files.fopen(path_test, 'r') as fp_test_:
            self.assertTrue((sum(1 for _ in fp_test_) == 1))

        # ensure, the replacement succeeded
        with salt.utils.files.fopen(path_test, 'r') as fp_test_:
            self.assertTrue(fp_test_.read().startswith('en_US.UTF-8'))

        # ensure, all runs of 'file.replace' reported success
        for item in ret:
            self.assertSaltTrueReturn(item)

    @with_tempdir()
    def test_replace_issue_18612_prepend(self, base_dir):
        '''
        Test the (mis-)behaviour of file.replace as described in #18612:

        Using 'prepend_if_not_found' or 'append_if_not_found' resulted in
        an infinitely growing file as 'file.replace' didn't check beforehand
        whether the changes had already been done to the file

        # Case description:

        The tested multifile contains multiple lines not matching the pattern or replacement in any way
        The replacement pattern should be prepended to the file
        '''
        test_name = 'test_replace_issue_18612_prepend'
        path_in = os.path.join(
            FILES, 'file.replace', '{0}.in'.format(test_name)
        )
        path_out = os.path.join(
            FILES, 'file.replace', '{0}.out'.format(test_name)
        )
        path_test = os.path.join(base_dir, test_name)

        # create test file based on initial template
        shutil.copyfile(path_in, path_test)

        ret = []
        for x in range(0, 3):
            ret.append(self.run_state('file.replace',
                name=path_test, pattern='^# en_US.UTF-8$', repl='en_US.UTF-8', prepend_if_not_found=True))

        # ensure, the resulting file contains the expected lines
        self.assertTrue(filecmp.cmp(path_test, path_out))

        # ensure the initial file was properly backed up
        self.assertTrue(filecmp.cmp(path_test + '.bak', path_in))

        # ensure, all runs of 'file.replace' reported success
        for item in ret:
            self.assertSaltTrueReturn(item)

    @with_tempdir()
    def test_replace_issue_18612_append(self, base_dir):
        '''
        Test the (mis-)behaviour of file.replace as described in #18612:

        Using 'prepend_if_not_found' or 'append_if_not_found' resulted in
        an infinitely growing file as 'file.replace' didn't check beforehand
        whether the changes had already been done to the file

        # Case description:

        The tested multifile contains multiple lines not matching the pattern or replacement in any way
        The replacement pattern should be appended to the file
        '''
        test_name = 'test_replace_issue_18612_append'
        path_in = os.path.join(
            FILES, 'file.replace', '{0}.in'.format(test_name)
        )
        path_out = os.path.join(
            FILES, 'file.replace', '{0}.out'.format(test_name)
        )
        path_test = os.path.join(base_dir, test_name)

        # create test file based on initial template
        shutil.copyfile(path_in, path_test)

        ret = []
        for x in range(0, 3):
            ret.append(self.run_state('file.replace',
                name=path_test, pattern='^# en_US.UTF-8$', repl='en_US.UTF-8', append_if_not_found=True))

        # ensure, the resulting file contains the expected lines
        self.assertTrue(filecmp.cmp(path_test, path_out))

        # ensure the initial file was properly backed up
        self.assertTrue(filecmp.cmp(path_test + '.bak', path_in))

        # ensure, all runs of 'file.replace' reported success
        for item in ret:
            self.assertSaltTrueReturn(item)

    @with_tempdir()
    def test_replace_issue_18612_append_not_found_content(self, base_dir):
        '''
        Test the (mis-)behaviour of file.replace as described in #18612:

        Using 'prepend_if_not_found' or 'append_if_not_found' resulted in
        an infinitely growing file as 'file.replace' didn't check beforehand
        whether the changes had already been done to the file

        # Case description:

        The tested multifile contains multiple lines not matching the pattern or replacement in any way
        The 'not_found_content' value should be appended to the file
        '''
        test_name = 'test_replace_issue_18612_append_not_found_content'
        path_in = os.path.join(
            FILES, 'file.replace', '{0}.in'.format(test_name)
        )
        path_out = os.path.join(
            FILES, 'file.replace', '{0}.out'.format(test_name)
        )
        path_test = os.path.join(base_dir, test_name)

        # create test file based on initial template
        shutil.copyfile(path_in, path_test)

        ret = []
        for x in range(0, 3):
            ret.append(
                self.run_state('file.replace',
                    name=path_test,
                    pattern='^# en_US.UTF-8$',
                    repl='en_US.UTF-8',
                    append_if_not_found=True,
                    not_found_content='THIS LINE WASN\'T FOUND! SO WE\'RE APPENDING IT HERE!'
            ))

        # ensure, the resulting file contains the expected lines
        self.assertTrue(filecmp.cmp(path_test, path_out))

        # ensure the initial file was properly backed up
        self.assertTrue(filecmp.cmp(path_test + '.bak', path_in))

        # ensure, all runs of 'file.replace' reported success
        for item in ret:
            self.assertSaltTrueReturn(item)

    @with_tempdir()
    def test_replace_issue_18612_change_mid_line_with_comment(self, base_dir):
        '''
        Test the (mis-)behaviour of file.replace as described in #18612:

        Using 'prepend_if_not_found' or 'append_if_not_found' resulted in
        an infinitely growing file as 'file.replace' didn't check beforehand
        whether the changes had already been done to the file

        # Case description:

        The tested file contains 5 key=value pairs
        The commented key=value pair #foo=bar should be changed to foo=salt
        The comment char (#) in front of foo=bar should be removed
        '''
        test_name = 'test_replace_issue_18612_change_mid_line_with_comment'
        path_in = os.path.join(
            FILES, 'file.replace', '{0}.in'.format(test_name)
        )
        path_out = os.path.join(
            FILES, 'file.replace', '{0}.out'.format(test_name)
        )
        path_test = os.path.join(base_dir, test_name)

        # create test file based on initial template
        shutil.copyfile(path_in, path_test)

        ret = []
        for x in range(0, 3):
            ret.append(self.run_state('file.replace',
                name=path_test, pattern='^#foo=bar$', repl='foo=salt', append_if_not_found=True))

        # ensure, the resulting file contains the expected lines
        self.assertTrue(filecmp.cmp(path_test, path_out))

        # ensure the initial file was properly backed up
        self.assertTrue(filecmp.cmp(path_test + '.bak', path_in))

        # ensure, all 'file.replace' runs reported success
        for item in ret:
            self.assertSaltTrueReturn(item)

    @with_tempdir()
    def test_replace_issue_18841_no_changes(self, base_dir):
        '''
        Test the (mis-)behaviour of file.replace as described in #18841:

        Using file.replace in a way which shouldn't modify the file at all
        results in changed mtime of the original file and a backup file being created.

        # Case description

        The tested file contains multiple lines
        The tested file contains a line already matching the replacement (no change needed)
        The tested file's content shouldn't change at all
        The tested file's mtime shouldn't change at all
        No backup file should be created
        '''
        test_name = 'test_replace_issue_18841_no_changes'
        path_in = os.path.join(
            FILES, 'file.replace', '{0}.in'.format(test_name)
        )
        path_test = os.path.join(base_dir, test_name)

        # create test file based on initial template
        shutil.copyfile(path_in, path_test)

        # get (m|a)time of file
        fstats_orig = os.stat(path_test)

        # define how far we predate the file
        age = 5*24*60*60

        # set (m|a)time of file 5 days into the past
        os.utime(path_test, (fstats_orig.st_mtime-age, fstats_orig.st_atime-age))

        ret = self.run_state('file.replace',
            name=path_test,
            pattern='^hello world$',
            repl='goodbye world',
            show_changes=True,
            flags=['IGNORECASE'],
            backup=False
        )

        # get (m|a)time of file
        fstats_post = os.stat(path_test)

        # ensure, the file content didn't change
        self.assertTrue(filecmp.cmp(path_in, path_test))

        # ensure no backup file was created
        self.assertFalse(os.path.exists(path_test + '.bak'))

        # ensure the file's mtime didn't change
        self.assertTrue(fstats_post.st_mtime, fstats_orig.st_mtime-age)

        # ensure, all 'file.replace' runs reported success
        self.assertSaltTrueReturn(ret)

    def test_serialize(self):
        '''
        Test to ensure that file.serialize returns a data structure that's
        both serialized and formatted properly
        '''
        path_test = os.path.join(TMP, 'test_serialize')
        ret = self.run_state('file.serialize',
                name=path_test,
                dataset={'name': 'naive',
                    'description': 'A basic test',
                    'a_list': ['first_element', 'second_element'],
                    'finally': 'the last item'},
                formatter='json')

        with salt.utils.files.fopen(path_test, 'r') as fp_:
            serialized_file = fp_.read()

        expected_file = '''{
  "a_list": [
    "first_element",
    "second_element"
  ],
  "description": "A basic test",
  "finally": "the last item",
  "name": "naive"
}
'''
        self.assertEqual(serialized_file, expected_file)

    @with_tempdir()
    def test_replace_issue_18841_omit_backup(self, base_dir):
        '''
        Test the (mis-)behaviour of file.replace as described in #18841:

        Using file.replace in a way which shouldn't modify the file at all
        results in changed mtime of the original file and a backup file being created.

        # Case description

        The tested file contains multiple lines
        The tested file contains a line already matching the replacement (no change needed)
        The tested file's content shouldn't change at all
        The tested file's mtime shouldn't change at all
        No backup file should be created, although backup=False isn't explicitly defined
        '''
        test_name = 'test_replace_issue_18841_omit_backup'
        path_in = os.path.join(
            FILES, 'file.replace', '{0}.in'.format(test_name)
        )
        path_test = os.path.join(base_dir, test_name)

        # create test file based on initial template
        shutil.copyfile(path_in, path_test)

        # get (m|a)time of file
        fstats_orig = os.stat(path_test)

        # define how far we predate the file
        age = 5*24*60*60

        # set (m|a)time of file 5 days into the past
        os.utime(path_test, (fstats_orig.st_mtime-age, fstats_orig.st_atime-age))

        ret = self.run_state('file.replace',
            name=path_test,
            pattern='^hello world$',
            repl='goodbye world',
            show_changes=True,
            flags=['IGNORECASE']
        )

        # get (m|a)time of file
        fstats_post = os.stat(path_test)

        # ensure, the file content didn't change
        self.assertTrue(filecmp.cmp(path_in, path_test))

        # ensure no backup file was created
        self.assertFalse(os.path.exists(path_test + '.bak'))

        # ensure the file's mtime didn't change
        self.assertTrue(fstats_post.st_mtime, fstats_orig.st_mtime-age)

        # ensure, all 'file.replace' runs reported success
        self.assertSaltTrueReturn(ret)

    @with_tempfile()
    def test_comment(self, name):
        '''
        file.comment
        '''
        # write a line to file
        with salt.utils.files.fopen(name, 'w+') as fp_:
            fp_.write('comment_me')

        # Look for changes with test=True: return should be "None" at the first run
        ret = self.run_state('file.comment', test=True, name=name, regex='^comment')
        self.assertSaltNoneReturn(ret)

        # comment once
        ret = self.run_state('file.comment', name=name, regex='^comment')
        # result is positive
        self.assertSaltTrueReturn(ret)
        # line is commented
        with salt.utils.files.fopen(name, 'r') as fp_:
            self.assertTrue(fp_.read().startswith('#comment'))

        # comment twice
        ret = self.run_state('file.comment', name=name, regex='^comment')

        # result is still positive
        self.assertSaltTrueReturn(ret)
        # line is still commented
        with salt.utils.files.fopen(name, 'r') as fp_:
            self.assertTrue(fp_.read().startswith('#comment'))

        # Test previously commented file returns "True" now and not "None" with test=True
        ret = self.run_state('file.comment', test=True, name=name, regex='^comment')
        self.assertSaltTrueReturn(ret)

    @with_tempfile()
    def test_test_comment(self, name):
        '''
        file.comment test interface
        '''
        with salt.utils.files.fopen(name, 'w+') as fp_:
            fp_.write('comment_me')
        ret = self.run_state(
            'file.comment', test=True, name=name, regex='.*comment.*',
        )
        with salt.utils.files.fopen(name, 'r') as fp_:
            self.assertNotIn('#comment', fp_.read())
        self.assertSaltNoneReturn(ret)

    @with_tempfile()
    def test_uncomment(self, name):
        '''
        file.uncomment
        '''
        with salt.utils.files.fopen(name, 'w+') as fp_:
            fp_.write('#comment_me')
        ret = self.run_state('file.uncomment', name=name, regex='^comment')
        with salt.utils.files.fopen(name, 'r') as fp_:
            self.assertNotIn('#comment', fp_.read())
        self.assertSaltTrueReturn(ret)

    @with_tempfile()
    def test_test_uncomment(self, name):
        '''
        file.comment test interface
        '''
        with salt.utils.files.fopen(name, 'w+') as fp_:
            fp_.write('#comment_me')
        ret = self.run_state(
            'file.uncomment', test=True, name=name, regex='^comment.*'
        )
        with salt.utils.files.fopen(name, 'r') as fp_:
            self.assertIn('#comment', fp_.read())
        self.assertSaltNoneReturn(ret)

    @with_tempfile()
    def test_append(self, name):
        '''
        file.append
        '''
        with salt.utils.files.fopen(name, 'w+') as fp_:
            fp_.write('#salty!')
        ret = self.run_state('file.append', name=name, text='cheese')
        with salt.utils.files.fopen(name, 'r') as fp_:
            self.assertIn('cheese', fp_.read())
        self.assertSaltTrueReturn(ret)

    @with_tempfile()
    def test_test_append(self, name):
        '''
        file.append test interface
        '''
        with salt.utils.files.fopen(name, 'w+') as fp_:
            fp_.write('#salty!')
        ret = self.run_state(
            'file.append', test=True, name=name, text='cheese'
        )
        with salt.utils.files.fopen(name, 'r') as fp_:
            self.assertNotIn('cheese', fp_.read())
        self.assertSaltNoneReturn(ret)

    @with_tempdir()
    def test_append_issue_1864_makedirs(self, base_dir):
        '''
        file.append but create directories if needed as an option, and create
        the file if it doesn't exist
        '''
        fname = 'append_issue_1864_makedirs'
        name = os.path.join(base_dir, fname)

        # Non existing file get's touched
        ret = self.run_state(
            'file.append', name=name, text='cheese', makedirs=True
        )
        self.assertSaltTrueReturn(ret)

        # Nested directory and file get's touched
        name = os.path.join(base_dir, 'issue_1864', fname)
        ret = self.run_state(
            'file.append', name=name, text='cheese', makedirs=True
        )
        self.assertSaltTrueReturn(ret)

        # Parent directory exists but file does not and makedirs is False
        name = os.path.join(base_dir, 'issue_1864', fname + '2')
        ret = self.run_state(
            'file.append', name=name, text='cheese'
        )
        self.assertSaltTrueReturn(ret)
        self.assertTrue(os.path.isfile(name))

    @with_tempdir()
    def test_prepend_issue_27401_makedirs(self, base_dir):
        '''
        file.prepend but create directories if needed as an option, and create
        the file if it doesn't exist
        '''
        fname = 'prepend_issue_27401'
        name = os.path.join(base_dir, fname)

        # Non existing file get's touched
        ret = self.run_state(
            'file.prepend', name=name, text='cheese', makedirs=True
        )
        self.assertSaltTrueReturn(ret)

        # Nested directory and file get's touched
        name = os.path.join(base_dir, 'issue_27401', fname)
        ret = self.run_state(
            'file.prepend', name=name, text='cheese', makedirs=True
        )
        self.assertSaltTrueReturn(ret)

        # Parent directory exists but file does not and makedirs is False
        name = os.path.join(base_dir, 'issue_27401', fname + '2')
        ret = self.run_state(
            'file.prepend', name=name, text='cheese'
        )
        self.assertSaltTrueReturn(ret)
        self.assertTrue(os.path.isfile(name))

    @with_tempfile()
    def test_touch(self, name):
        '''
        file.touch
        '''
        ret = self.run_state('file.touch', name=name)
        self.assertTrue(os.path.isfile(name))
        self.assertSaltTrueReturn(ret)

    @with_tempfile(create=False)
    def test_test_touch(self, name):
        '''
        file.touch test interface
        '''
        ret = self.run_state('file.touch', test=True, name=name)
        self.assertFalse(os.path.isfile(name))
        self.assertSaltNoneReturn(ret)

    @with_tempdir()
    def test_touch_directory(self, base_dir):
        '''
        file.touch a directory
        '''
        name = os.path.join(base_dir, 'touch_test_dir')
        os.mkdir(name)

        ret = self.run_state('file.touch', name=name)
        self.assertSaltTrueReturn(ret)
        self.assertTrue(os.path.isdir(name))

    @with_tempdir()
    def test_issue_2227_file_append(self, base_dir):
        '''
        Text to append includes a percent symbol
        '''
        # let's make use of existing state to create a file with contents to
        # test against
        tmp_file_append = os.path.join(base_dir, 'test.append')

        self.run_state('file.touch', name=tmp_file_append)
        self.run_state(
            'file.append',
            name=tmp_file_append,
            source='salt://testappend/firstif')
        self.run_state(
            'file.append',
            name=tmp_file_append,
            source='salt://testappend/secondif')

        # Now our real test
        try:
            ret = self.run_state(
                'file.append',
                name=tmp_file_append,
                text="HISTTIMEFORMAT='%F %T '")
            self.assertSaltTrueReturn(ret)
            with salt.utils.files.fopen(tmp_file_append, 'r') as fp_:
                contents_pre = fp_.read()

            # It should not append text again
            ret = self.run_state(
                'file.append',
                name=tmp_file_append,
                text="HISTTIMEFORMAT='%F %T '")
            self.assertSaltTrueReturn(ret)

            with salt.utils.files.fopen(tmp_file_append, 'r') as fp_:
                contents_post = fp_.read()

            self.assertEqual(contents_pre, contents_post)
        except AssertionError:
            if os.path.exists(tmp_file_append):
                shutil.copy(tmp_file_append, tmp_file_append + '.bak')
            raise

    def do_patch(self, patch_name='hello', src='Hello\n'):
        if not self.run_function('cmd.has_exec', ['patch']):
            self.skipTest('patch is not installed')
        src_file = os.path.join(TMP, 'src.txt')
        with salt.utils.files.fopen(src_file, 'w+') as fp:
            fp.write(src)
        ret = self.run_state(
            'file.patch',
            name=src_file,
            source='salt://{0}.patch'.format(patch_name),
            hash='md5=f0ef7081e1539ac00ef5b761b4fb01b3',
        )
        return src_file, ret

    def test_patch(self):
        src_file, ret = self.do_patch()
        self.assertSaltTrueReturn(ret)
        with salt.utils.files.fopen(src_file) as fp:
            self.assertEqual(fp.read(), 'Hello world\n')

    def test_patch_hash_mismatch(self):
        src_file, ret = self.do_patch('hello_dolly')
        self.assertSaltFalseReturn(ret)
        self.assertInSaltComment(
            'Hash mismatch after patch was applied',
            ret
        )

    def test_patch_already_applied(self):
        src_file, ret = self.do_patch(src='Hello world\n')
        self.assertSaltTrueReturn(ret)
        self.assertInSaltComment('Patch is already applied', ret)

    @with_tempdir()
    def test_issue_2401_file_comment(self, base_dir):
        # Get a path to the temporary file
        tmp_file = os.path.join(base_dir, 'issue-2041-comment.txt')
        # Write some data to it
        with salt.utils.files.fopen(tmp_file, 'w') as fp_:
            fp_.write('hello\nworld\n')
        # create the sls template
        template_lines = [
            '{0}:'.format(tmp_file),
            '  file.comment:',
            '    - regex: ^world'
        ]
        template = '\n'.join(template_lines)
        try:
            ret = self.run_function(
                'state.template_str', [template], timeout=120
            )
            self.assertSaltTrueReturn(ret)
            self.assertNotInSaltComment('Pattern already commented', ret)
            self.assertInSaltComment('Commented lines successfully', ret)

            # This next time, it is already commented.
            ret = self.run_function(
                'state.template_str', [template], timeout=120
            )

            self.assertSaltTrueReturn(ret)
            self.assertInSaltComment('Pattern already commented', ret)
        except AssertionError:
            shutil.copy(tmp_file, tmp_file + '.bak')
            raise

    @with_tempdir()
    def test_issue_2379_file_append(self, base_dir):
        # Get a path to the temporary file
        tmp_file = os.path.join(base_dir, 'issue-2379-file-append.txt')
        # Write some data to it
        with salt.utils.files.fopen(tmp_file, 'w') as fp_:
            fp_.write(
                'hello\nworld\n'           # Some junk
                '#PermitRootLogin yes\n'   # Commented text
                '# PermitRootLogin yes\n'  # Commented text with space
            )
        # create the sls template
        template_lines = [
            '{0}:'.format(tmp_file),
            '  file.append:',
            '    - text: PermitRootLogin yes'
        ]
        template = '\n'.join(template_lines)
        try:
            ret = self.run_function('state.template_str', [template])

            self.assertSaltTrueReturn(ret)
            self.assertInSaltComment('Appended 1 lines', ret)
        except AssertionError:
            shutil.copy(tmp_file, tmp_file + '.bak')
            raise

    @skipIf(IS_WINDOWS, 'Mode not available in Windows')
    @with_tempdir(create=False)
    @with_tempdir(create=False)
    def test_issue_2726_mode_kwarg(self, dir1, dir2):
        # Let's test for the wrong usage approach
        bad_mode_kwarg_testfile = os.path.join(
            dir1, 'bad_mode_kwarg', 'testfile'
        )
        bad_template = [
            '{0}:'.format(bad_mode_kwarg_testfile),
            '  file.recurse:',
            '    - source: salt://testfile',
            '    - mode: 644'
        ]
        ret = self.run_function(
            'state.template_str', [os.linesep.join(bad_template)]
        )
        self.assertSaltFalseReturn(ret)
        self.assertInSaltComment(
            '\'mode\' is not allowed in \'file.recurse\'. Please use '
            '\'file_mode\' and \'dir_mode\'.',
            ret
        )
        self.assertNotInSaltComment(
            'TypeError: managed() got multiple values for keyword '
            'argument \'mode\'',
            ret
        )

        # Now, the correct usage approach
        good_mode_kwargs_testfile = os.path.join(
            dir2, 'good_mode_kwargs', 'testappend'
        )
        good_template = [
            '{0}:'.format(good_mode_kwargs_testfile),
            '  file.recurse:',
            '    - source: salt://testappend',
            '    - dir_mode: 744',
            '    - file_mode: 644',
        ]
        ret = self.run_function(
            'state.template_str', [os.linesep.join(good_template)]
        )
        self.assertSaltTrueReturn(ret)

    @with_tempdir()
    def test_issue_8343_accumulated_require_in(self, base_dir):
        template_path = os.path.join(TMP_STATE_TREE, 'issue-8343.sls')
        testcase_filedest = os.path.join(base_dir, 'issue-8343.txt')
        sls_template = [
            '{0}:',
            '  file.managed:',
            '    - contents: |',
            '                #',
            '',
            'prepend-foo-accumulator-from-pillar:',
            '  file.accumulated:',
            '    - require_in:',
            '      - file: prepend-foo-management',
            '    - filename: {0}',
            '    - text: |',
            '            foo',
            '',
            'append-foo-accumulator-from-pillar:',
            '  file.accumulated:',
            '    - require_in:',
            '      - file: append-foo-management',
            '    - filename: {0}',
            '    - text: |',
            '            bar',
            '',
            'prepend-foo-management:',
            '  file.blockreplace:',
            '    - name: {0}',
            '    - marker_start: "#-- start salt managed zonestart -- PLEASE, DO NOT EDIT"',
            '    - marker_end: "#-- end salt managed zonestart --"',
            "    - content: ''",
            '    - prepend_if_not_found: True',
            "    - backup: '.bak'",
            '    - show_changes: True',
            '',
            'append-foo-management:',
            '  file.blockreplace:',
            '    - name: {0}',
            '    - marker_start: "#-- start salt managed zoneend -- PLEASE, DO NOT EDIT"',
            '    - marker_end: "#-- end salt managed zoneend --"',
            "    - content: ''",
            '    - append_if_not_found: True',
            "    - backup: '.bak2'",
            '    - show_changes: True',
            '']
        with salt.utils.files.fopen(template_path, 'w') as fp_:
            fp_.write(
                os.linesep.join(sls_template).format(testcase_filedest))

        ret = self.run_function('state.sls', mods='issue-8343')
        for name, step in six.iteritems(ret):
            self.assertSaltTrueReturn({name: step})
        with salt.utils.files.fopen(testcase_filedest) as fp_:
            contents = fp_.read().split(os.linesep)

        expected = [
            '#-- start salt managed zonestart -- PLEASE, DO NOT EDIT',
            'foo',
            '#-- end salt managed zonestart --',
            '#',
            '#-- start salt managed zoneend -- PLEASE, DO NOT EDIT',
            'bar',
            '#-- end salt managed zoneend --',
            '']

        self.assertEqual(expected, contents)

    @with_tempdir()
    def test_issue_11003_immutable_lazy_proxy_sum(self, base_dir):
        # causes the Import-Module ServerManager error on Windows
        template_path = os.path.join(TMP_STATE_TREE, 'issue-11003.sls')
        testcase_filedest = os.path.join(base_dir, 'issue-11003.txt')
        sls_template = [
            'a{0}:',
            '  file.absent:',
            '    - name: {0}',
            '',
            '{0}:',
            '  file.managed:',
            '    - contents: |',
            '                #',
            '',
            'test-acc1:',
            '  file.accumulated:',
            '    - require_in:',
            '      - file: final',
            '    - filename: {0}',
            '    - text: |',
            '            bar',
            '',
            'test-acc2:',
            '  file.accumulated:',
            '    - watch_in:',
            '      - file: final',
            '    - filename: {0}',
            '    - text: |',
            '            baz',
            '',
            'final:',
            '  file.blockreplace:',
            '    - name: {0}',
            '    - marker_start: "#-- start managed zone PLEASE, DO NOT EDIT"',
            '    - marker_end: "#-- end managed zone"',
            '    - content: \'\'',
            '    - append_if_not_found: True',
            '    - show_changes: True'
        ]

        with salt.utils.files.fopen(template_path, 'w') as fp_:
            fp_.write(os.linesep.join(sls_template).format(testcase_filedest))

        ret = self.run_function('state.sls', mods='issue-11003')
        for name, step in six.iteritems(ret):
            self.assertSaltTrueReturn({name: step})
        with salt.utils.files.fopen(testcase_filedest) as fp_:
            contents = fp_.read().split(os.linesep)

        begin = contents.index(
            '#-- start managed zone PLEASE, DO NOT EDIT') + 1
        end = contents.index('#-- end managed zone')
        block_contents = contents[begin:end]
        for item in ('', 'bar', 'baz'):
            block_contents.remove(item)
        self.assertEqual(block_contents, [])

    @with_tempdir()
    def test_issue_8947_utf8_sls(self, base_dir):
        '''
        Test some file operation with utf-8 characters on the sls

        This is more generic than just a file test. Feel free to move
        '''
        self.maxDiff = None
        korean_1 = '한국어 시험'
        korean_2 = '첫 번째 행'
        korean_3 = '마지막 행'
        test_file = os.path.join(base_dir, '{0}.txt'.format(korean_1))
        test_file_encoded = test_file
        template_path = os.path.join(TMP_STATE_TREE, 'issue-8947.sls')
        # create the sls template
        template = textwrap.dedent('''\
            some-utf8-file-create:
              file.managed:
                - name: {test_file}
                - contents: {korean_1}
                - makedirs: True
                - replace: True
                - show_diff: True
            some-utf8-file-create2:
              file.managed:
                - name: {test_file}
                - contents: |
                   {korean_2}
                   {korean_1}
                   {korean_3}
                - replace: True
                - show_diff: True
            some-utf8-file-content-test:
              cmd.run:
                - name: 'cat "{test_file}"'
                - require:
                  - file: some-utf8-file-create2
            '''.format(**locals()))

        # Save template file
        with salt.utils.files.fopen(template_path, 'wb') as fp_:
            fp_.write(salt.utils.stringutils.to_bytes(template))

        try:
            result = self.run_function('state.sls', mods='issue-8947')
            if not isinstance(result, dict):
                raise AssertionError(
                    ('Something went really wrong while testing this sls:'
                    ' {0}').format(repr(result))
                )
            # difflib produces different output on python 2.6 than on >=2.7
            if sys.version_info < (2, 7):
                diff = '---  \n+++  \n@@ -1,1 +1,3 @@\n'
            else:
                diff = '--- \n+++ \n@@ -1 +1,3 @@\n'
            diff += (
                '+첫 번째 행\n'
                ' 한국어 시험\n'
                '+마지막 행\n'
            )

            ret = {x.split('_|-')[1]: y for x, y in six.iteritems(result)}

            # Confirm initial creation of file
            self.assertEqual(
                ret['some-utf8-file-create']['comment'],
                'File {0} updated'.format(test_file_encoded)
            )
            self.assertEqual(
                ret['some-utf8-file-create']['changes'],
                {'diff': 'New file'}
            )

            # Confirm file was modified and that the diff was as expected
            self.assertEqual(
                ret['some-utf8-file-create2']['comment'],
                'File {0} updated'.format(test_file_encoded)
            )
            self.assertEqual(
                ret['some-utf8-file-create2']['changes'],
                {'diff': diff}
            )

            # Confirm that the file has the expected contents as specified in
            # the prior state.
            self.assertEqual(
                ret['some-utf8-file-content-test']['comment'],
                'Command "cat "{0}"" run'.format(test_file_encoded)
            )
            self.assertEqual(
                ret['some-utf8-file-content-test']['changes']['stdout'],
                '\n'.join((korean_2, korean_1, korean_3))
            )

        finally:
            try:
                os.remove(template_path)
            except OSError:
                pass

    @skip_if_not_root
    @skipIf(not HAS_PWD, "pwd not available. Skipping test")
    @skipIf(not HAS_GRP, "grp not available. Skipping test")
    @with_system_user_and_group('user12209', 'group12209',
                                on_existing='delete', delete=True)
    @with_tempdir()
    def test_issue_12209_follow_symlinks(self, tempdir, user, group):
        '''
        Ensure that symlinks are properly chowned when recursing (following
        symlinks)
        '''
        # Make the directories for this test
        onedir = os.path.join(tempdir, 'one')
        twodir = os.path.join(tempdir, 'two')
        os.mkdir(onedir)
        os.symlink(onedir, twodir)

        # Run the state
        ret = self.run_state(
            'file.directory', name=tempdir, follow_symlinks=True,
            user=user, group=group, recurse=['user', 'group']
        )
        self.assertSaltTrueReturn(ret)

        # Double-check, in case state mis-reported a True result. Since we are
        # following symlinks, we expect twodir to still be owned by root, but
        # onedir should be owned by the 'issue12209' user.
        onestats = os.stat(onedir)
        twostats = os.lstat(twodir)
        self.assertEqual(pwd.getpwuid(onestats.st_uid).pw_name, user)
        self.assertEqual(pwd.getpwuid(twostats.st_uid).pw_name, 'root')
        self.assertEqual(grp.getgrgid(onestats.st_gid).gr_name, group)
        if salt.utils.path.which('id'):
            root_group = self.run_function('user.primary_group', ['root'])
            self.assertEqual(grp.getgrgid(twostats.st_gid).gr_name, root_group)

    @skip_if_not_root
    @skipIf(not HAS_PWD, "pwd not available. Skipping test")
    @skipIf(not HAS_GRP, "grp not available. Skipping test")
    @with_system_user_and_group('user12209', 'group12209',
                                on_existing='delete', delete=True)
    @with_tempdir()
    def test_issue_12209_no_follow_symlinks(self, tempdir, user, group):
        '''
        Ensure that symlinks are properly chowned when recursing (not following
        symlinks)
        '''
        # Make the directories for this test
        onedir = os.path.join(tempdir, 'one')
        twodir = os.path.join(tempdir, 'two')
        os.mkdir(onedir)
        os.symlink(onedir, twodir)

        # Run the state
        ret = self.run_state(
            'file.directory', name=tempdir, follow_symlinks=False,
            user=user, group=group, recurse=['user', 'group']
        )
        self.assertSaltTrueReturn(ret)

        # Double-check, in case state mis-reported a True result. Since we
        # are not following symlinks, we expect twodir to now be owned by
        # the 'issue12209' user, just link onedir.
        onestats = os.stat(onedir)
        twostats = os.lstat(twodir)
        self.assertEqual(pwd.getpwuid(onestats.st_uid).pw_name, user)
        self.assertEqual(pwd.getpwuid(twostats.st_uid).pw_name, user)
        self.assertEqual(grp.getgrgid(onestats.st_gid).gr_name, group)
        self.assertEqual(grp.getgrgid(twostats.st_gid).gr_name, group)

    @with_tempfile(create=False)
    @with_tempfile()
    def test_template_local_file(self, source, dest):
        '''
        Test a file.managed state with a local file as the source. Test both
        with the file:// protocol designation prepended, and without it.
        '''
        with salt.utils.files.fopen(source, 'w') as fp_:
            fp_.write('{{ foo }}\n')

        for prefix in ('file://', ''):
            ret = self.run_state(
                'file.managed',
                name=dest,
                source=prefix + source,
                template='jinja',
                context={'foo': 'Hello world!'}
            )
            self.assertSaltTrueReturn(ret)

    @with_tempfile()
    def test_template_local_file_noclobber(self, source):
        '''
        Test the case where a source file is in the minion's local filesystem,
        and the source path is the same as the destination path.
        '''
        with salt.utils.files.fopen(source, 'w') as fp_:
            fp_.write('{{ foo }}\n')

        ret = self.run_state(
            'file.managed',
            name=source,
            source=source,
            template='jinja',
            context={'foo': 'Hello world!'}
        )
        self.assertSaltFalseReturn(ret)
        self.assertIn(
            ('Source file cannot be the same as destination'),
            ret[next(iter(ret))]['comment'],
        )

    @with_tempfile(create=False)
    @with_tempfile(create=False)
    def test_issue_25250_force_copy_deletes(self, source, dest):
        '''
        ensure force option in copy state does not delete target file
        '''
        shutil.copyfile(os.path.join(FILES, 'hosts'), source)
        shutil.copyfile(os.path.join(FILES, 'file/base/cheese'), dest)

        self.run_state('file.copy', name=dest, source=source, force=True)
        self.assertTrue(os.path.exists(dest))
        self.assertTrue(filecmp.cmp(source, dest))

    def test_contents_pillar_with_pillar_list(self):
        '''
        This tests for any regressions for this issue:
        https://github.com/saltstack/salt/issues/30934
        '''
        state_file = 'file_contents_pillar'

        ret = self.run_function('state.sls', mods=state_file)
        self.assertSaltTrueReturn(ret)

    @skip_if_not_root
    @skipIf(not HAS_PWD, "pwd not available. Skipping test")
    @skipIf(not HAS_GRP, "grp not available. Skipping test")
    @with_system_user_and_group('test_setuid_user', 'test_setuid_group',
                                on_existing='delete', delete=True)
    def test_owner_after_setuid(self, user, group):

        '''
        Test to check file user/group after setting setuid or setgid.
        Because Python os.chown() does reset the setuid/setgid to 0.
        https://github.com/saltstack/salt/pull/45257
        '''

        # Desired configuration.
        desired = {
            'file': os.path.join(TMP, 'file_with_setuid'),
            'user': user,
            'group': group,
            'mode': '4750'
        }

        # Run the state.
        ret = self.run_state(
            'file.managed', name=desired['file'],
            user=desired['user'], group=desired['group'], mode=desired['mode']
        )

        # Check result.
        file_stat = os.stat(desired['file'])
        result = {
            'user': pwd.getpwuid(file_stat.st_uid).pw_name,
            'group': grp.getgrgid(file_stat.st_gid).gr_name,
            'mode': oct(stat.S_IMODE(file_stat.st_mode))
        }

        self.assertSaltTrueReturn(ret)
        self.assertEqual(desired['user'], result['user'])
        self.assertEqual(desired['group'], result['group'])
        self.assertEqual(desired['mode'], result['mode'].lstrip('0Oo'))

    def test_binary_contents(self):
        '''
        This tests to ensure that binary contents do not cause a traceback.
        '''
        name = os.path.join(TMP, '1px.gif')
        try:
            ret = self.run_state(
                'file.managed',
                name=name,
                contents=BINARY_FILE)
            self.assertSaltTrueReturn(ret)
        finally:
            try:
                os.remove(name)
            except OSError:
                pass


class BlockreplaceTest(ModuleCase, SaltReturnAssertsMixin):
    marker_start = '# start'
    marker_end = '# end'
    content = textwrap.dedent('''\
        Line 1 of block
        Line 2 of block
        ''')
    without_block = textwrap.dedent('''\
        Hello world!

        # comment here
        ''')
    with_non_matching_block = textwrap.dedent('''\
        Hello world!

        # start
        No match here
        # end
        # comment here
        ''')
    with_non_matching_block_and_marker_end_not_after_newline = textwrap.dedent('''\
        Hello world!

        # start
        No match here# end
        # comment here
        ''')
    with_matching_block = textwrap.dedent('''\
        Hello world!

        # start
        Line 1 of block
        Line 2 of block
        # end
        # comment here
        ''')
    with_matching_block_and_extra_newline = textwrap.dedent('''\
        Hello world!

        # start
        Line 1 of block
        Line 2 of block

        # end
        # comment here
        ''')
    with_matching_block_and_marker_end_not_after_newline = textwrap.dedent('''\
        Hello world!

        # start
        Line 1 of block
        Line 2 of block# end
        # comment here
        ''')
    content_explicit_posix_newlines = ('Line 1 of block\n'
                                       'Line 2 of block\n')
    content_explicit_windows_newlines = ('Line 1 of block\r\n'
                                         'Line 2 of block\r\n')
    without_block_explicit_posix_newlines = ('Hello world!\n\n'
                                             '# comment here\n')
    without_block_explicit_windows_newlines = ('Hello world!\r\n\r\n'
                                               '# comment here\r\n')
    with_block_prepended_explicit_posix_newlines = ('# start\n'
                                                    'Line 1 of block\n'
                                                    'Line 2 of block\n'
                                                    '# end\n'
                                                    'Hello world!\n\n'
                                                    '# comment here\n')
    with_block_prepended_explicit_windows_newlines = ('# start\r\n'
                                                      'Line 1 of block\r\n'
                                                      'Line 2 of block\r\n'
                                                      '# end\r\n'
                                                      'Hello world!\r\n\r\n'
                                                      '# comment here\r\n')
    with_block_appended_explicit_posix_newlines = ('Hello world!\n\n'
                                                   '# comment here\n'
                                                   '# start\n'
                                                   'Line 1 of block\n'
                                                   'Line 2 of block\n'
                                                   '# end\n')
    with_block_appended_explicit_windows_newlines = ('Hello world!\r\n\r\n'
                                                     '# comment here\r\n'
                                                     '# start\r\n'
                                                     'Line 1 of block\r\n'
                                                     'Line 2 of block\r\n'
                                                     '# end\r\n')

    @staticmethod
    def _write(dest, content):
        with salt.utils.files.fopen(dest, 'wb') as fp_:
            fp_.write(salt.utils.stringutils.to_bytes(content))

    @staticmethod
    def _read(src):
        with salt.utils.files.fopen(src, 'rb') as fp_:
            return salt.utils.stringutils.to_unicode(fp_.read())

    @with_tempfile()
    def test_prepend(self, name):
        '''
        Test blockreplace when prepend_if_not_found=True and block doesn't
        exist in file.
        '''
        expected = self.marker_start + os.linesep + self.content + \
            self.marker_end + os.linesep + self.without_block

        # Pass 1: content ends in newline
        self._write(name, self.without_block)
        ret = self.run_state('file.blockreplace',
                             name=name,
                             content=self.content,
                             marker_start=self.marker_start,
                             marker_end=self.marker_end,
                             prepend_if_not_found=True)
        self.assertSaltTrueReturn(ret)
        self.assertTrue(ret[next(iter(ret))]['changes'])
        self.assertEqual(self._read(name), expected)
        # Pass 1a: Re-run state, no changes should be made
        ret = self.run_state('file.blockreplace',
                             name=name,
                             content=self.content,
                             marker_start=self.marker_start,
                             marker_end=self.marker_end,
                             prepend_if_not_found=True)
        self.assertSaltTrueReturn(ret)
        self.assertFalse(ret[next(iter(ret))]['changes'])
        self.assertEqual(self._read(name), expected)

        # Pass 2: content does not end in newline
        self._write(name, self.without_block)
        ret = self.run_state('file.blockreplace',
                             name=name,
                             content=self.content.rstrip('\r\n'),
                             marker_start=self.marker_start,
                             marker_end=self.marker_end,
                             prepend_if_not_found=True)
        self.assertSaltTrueReturn(ret)
        self.assertTrue(ret[next(iter(ret))]['changes'])
        self.assertEqual(self._read(name), expected)
        # Pass 2a: Re-run state, no changes should be made
        ret = self.run_state('file.blockreplace',
                             name=name,
                             content=self.content.rstrip('\r\n'),
                             marker_start=self.marker_start,
                             marker_end=self.marker_end,
                             prepend_if_not_found=True)
        self.assertSaltTrueReturn(ret)
        self.assertFalse(ret[next(iter(ret))]['changes'])
        self.assertEqual(self._read(name), expected)

    @with_tempfile()
    def test_prepend_append_newline(self, name):
        '''
        Test blockreplace when prepend_if_not_found=True and block doesn't
        exist in file. Test with append_newline explicitly set to True.
        '''
        # Pass 1: content ends in newline
        expected = self.marker_start + os.linesep + self.content + \
            os.linesep + self.marker_end + os.linesep + self.without_block
        self._write(name, self.without_block)
        ret = self.run_state('file.blockreplace',
                             name=name,
                             content=self.content,
                             marker_start=self.marker_start,
                             marker_end=self.marker_end,
                             prepend_if_not_found=True,
                             append_newline=True)
        self.assertSaltTrueReturn(ret)
        self.assertTrue(ret[next(iter(ret))]['changes'])
        self.assertEqual(self._read(name), expected)
        # Pass 1a: Re-run state, no changes should be made
        ret = self.run_state('file.blockreplace',
                             name=name,
                             content=self.content,
                             marker_start=self.marker_start,
                             marker_end=self.marker_end,
                             prepend_if_not_found=True,
                             append_newline=True)
        self.assertSaltTrueReturn(ret)
        self.assertFalse(ret[next(iter(ret))]['changes'])
        self.assertEqual(self._read(name), expected)

        # Pass 2: content does not end in newline
        expected = self.marker_start + os.linesep + self.content + \
            self.marker_end + os.linesep + self.without_block
        self._write(name, self.without_block)
        ret = self.run_state('file.blockreplace',
                             name=name,
                             content=self.content.rstrip('\r\n'),
                             marker_start=self.marker_start,
                             marker_end=self.marker_end,
                             prepend_if_not_found=True,
                             append_newline=True)
        self.assertSaltTrueReturn(ret)
        self.assertTrue(ret[next(iter(ret))]['changes'])
        self.assertEqual(self._read(name), expected)
        # Pass 2a: Re-run state, no changes should be made
        ret = self.run_state('file.blockreplace',
                             name=name,
                             content=self.content.rstrip('\r\n'),
                             marker_start=self.marker_start,
                             marker_end=self.marker_end,
                             prepend_if_not_found=True,
                             append_newline=True)
        self.assertSaltTrueReturn(ret)
        self.assertFalse(ret[next(iter(ret))]['changes'])
        self.assertEqual(self._read(name), expected)

    @with_tempfile()
    def test_prepend_no_append_newline(self, name):
        '''
        Test blockreplace when prepend_if_not_found=True and block doesn't
        exist in file. Test with append_newline explicitly set to False.
        '''
        # Pass 1: content ends in newline
        expected = self.marker_start + os.linesep + self.content + \
            self.marker_end + os.linesep + self.without_block
        self._write(name, self.without_block)
        ret = self.run_state('file.blockreplace',
                             name=name,
                             content=self.content,
                             marker_start=self.marker_start,
                             marker_end=self.marker_end,
                             prepend_if_not_found=True,
                             append_newline=False)
        self.assertSaltTrueReturn(ret)
        self.assertTrue(ret[next(iter(ret))]['changes'])
        self.assertEqual(self._read(name), expected)
        # Pass 1a: Re-run state, no changes should be made
        ret = self.run_state('file.blockreplace',
                             name=name,
                             content=self.content,
                             marker_start=self.marker_start,
                             marker_end=self.marker_end,
                             prepend_if_not_found=True,
                             append_newline=False)
        self.assertSaltTrueReturn(ret)
        self.assertFalse(ret[next(iter(ret))]['changes'])
        self.assertEqual(self._read(name), expected)

        # Pass 2: content does not end in newline
        expected = self.marker_start + os.linesep + \
            self.content.rstrip('\r\n') + self.marker_end + os.linesep + \
            self.without_block
        self._write(name, self.without_block)
        ret = self.run_state('file.blockreplace',
                             name=name,
                             content=self.content.rstrip('\r\n'),
                             marker_start=self.marker_start,
                             marker_end=self.marker_end,
                             prepend_if_not_found=True,
                             append_newline=False)
        self.assertSaltTrueReturn(ret)
        self.assertTrue(ret[next(iter(ret))]['changes'])
        self.assertEqual(self._read(name), expected)
        # Pass 2a: Re-run state, no changes should be made
        ret = self.run_state('file.blockreplace',
                             name=name,
                             content=self.content.rstrip('\r\n'),
                             marker_start=self.marker_start,
                             marker_end=self.marker_end,
                             prepend_if_not_found=True,
                             append_newline=False)
        self.assertSaltTrueReturn(ret)
        self.assertFalse(ret[next(iter(ret))]['changes'])
        self.assertEqual(self._read(name), expected)

    @with_tempfile()
    def test_append(self, name):
        '''
        Test blockreplace when append_if_not_found=True and block doesn't
        exist in file.
        '''
        expected = self.without_block + self.marker_start + os.linesep + \
            self.content + self.marker_end + os.linesep

        # Pass 1: content ends in newline
        self._write(name, self.without_block)
        ret = self.run_state('file.blockreplace',
                             name=name,
                             content=self.content,
                             marker_start=self.marker_start,
                             marker_end=self.marker_end,
                             append_if_not_found=True)
        self.assertSaltTrueReturn(ret)
        self.assertTrue(ret[next(iter(ret))]['changes'])
        self.assertEqual(self._read(name), expected)
        # Pass 1a: Re-run state, no changes should be made
        ret = self.run_state('file.blockreplace',
                             name=name,
                             content=self.content,
                             marker_start=self.marker_start,
                             marker_end=self.marker_end,
                             append_if_not_found=True)
        self.assertSaltTrueReturn(ret)
        self.assertFalse(ret[next(iter(ret))]['changes'])
        self.assertEqual(self._read(name), expected)

        # Pass 2: content does not end in newline
        self._write(name, self.without_block)
        ret = self.run_state('file.blockreplace',
                             name=name,
                             content=self.content.rstrip('\r\n'),
                             marker_start=self.marker_start,
                             marker_end=self.marker_end,
                             append_if_not_found=True)
        self.assertSaltTrueReturn(ret)
        self.assertTrue(ret[next(iter(ret))]['changes'])
        self.assertEqual(self._read(name), expected)
        # Pass 2a: Re-run state, no changes should be made
        ret = self.run_state('file.blockreplace',
                             name=name,
                             content=self.content.rstrip('\r\n'),
                             marker_start=self.marker_start,
                             marker_end=self.marker_end,
                             append_if_not_found=True)
        self.assertSaltTrueReturn(ret)
        self.assertFalse(ret[next(iter(ret))]['changes'])
        self.assertEqual(self._read(name), expected)

    @with_tempfile()
    def test_append_append_newline(self, name):
        '''
        Test blockreplace when append_if_not_found=True and block doesn't
        exist in file. Test with append_newline explicitly set to True.
        '''
        # Pass 1: content ends in newline
        expected = self.without_block + self.marker_start + os.linesep + \
            self.content + os.linesep + self.marker_end + os.linesep
        self._write(name, self.without_block)
        ret = self.run_state('file.blockreplace',
                             name=name,
                             content=self.content,
                             marker_start=self.marker_start,
                             marker_end=self.marker_end,
                             append_if_not_found=True,
                             append_newline=True)
        self.assertSaltTrueReturn(ret)
        self.assertTrue(ret[next(iter(ret))]['changes'])
        self.assertEqual(self._read(name), expected)
        # Pass 1a: Re-run state, no changes should be made
        ret = self.run_state('file.blockreplace',
                             name=name,
                             content=self.content,
                             marker_start=self.marker_start,
                             marker_end=self.marker_end,
                             append_if_not_found=True,
                             append_newline=True)
        self.assertSaltTrueReturn(ret)
        self.assertFalse(ret[next(iter(ret))]['changes'])
        self.assertEqual(self._read(name), expected)

        # Pass 2: content does not end in newline
        expected = self.without_block + self.marker_start + os.linesep + \
            self.content + self.marker_end + os.linesep
        self._write(name, self.without_block)
        ret = self.run_state('file.blockreplace',
                             name=name,
                             content=self.content.rstrip('\r\n'),
                             marker_start=self.marker_start,
                             marker_end=self.marker_end,
                             append_if_not_found=True,
                             append_newline=True)
        self.assertSaltTrueReturn(ret)
        self.assertTrue(ret[next(iter(ret))]['changes'])
        self.assertEqual(self._read(name), expected)
        # Pass 2a: Re-run state, no changes should be made
        ret = self.run_state('file.blockreplace',
                             name=name,
                             content=self.content.rstrip('\r\n'),
                             marker_start=self.marker_start,
                             marker_end=self.marker_end,
                             append_if_not_found=True,
                             append_newline=True)
        self.assertSaltTrueReturn(ret)
        self.assertFalse(ret[next(iter(ret))]['changes'])
        self.assertEqual(self._read(name), expected)

    @with_tempfile()
    def test_append_no_append_newline(self, name):
        '''
        Test blockreplace when append_if_not_found=True and block doesn't
        exist in file. Test with append_newline explicitly set to False.
        '''
        # Pass 1: content ends in newline
        expected = self.without_block + self.marker_start + os.linesep + \
            self.content + self.marker_end + os.linesep
        self._write(name, self.without_block)
        ret = self.run_state('file.blockreplace',
                             name=name,
                             content=self.content,
                             marker_start=self.marker_start,
                             marker_end=self.marker_end,
                             append_if_not_found=True,
                             append_newline=False)
        self.assertSaltTrueReturn(ret)
        self.assertTrue(ret[next(iter(ret))]['changes'])
        self.assertEqual(self._read(name), expected)
        # Pass 1a: Re-run state, no changes should be made
        ret = self.run_state('file.blockreplace',
                             name=name,
                             content=self.content,
                             marker_start=self.marker_start,
                             marker_end=self.marker_end,
                             append_if_not_found=True,
                             append_newline=False)
        self.assertSaltTrueReturn(ret)
        self.assertFalse(ret[next(iter(ret))]['changes'])
        self.assertEqual(self._read(name), expected)

        # Pass 2: content does not end in newline
        expected = self.without_block + self.marker_start + os.linesep + \
            self.content.rstrip('\r\n') + self.marker_end + os.linesep
        self._write(name, self.without_block)
        ret = self.run_state('file.blockreplace',
                             name=name,
                             content=self.content.rstrip('\r\n'),
                             marker_start=self.marker_start,
                             marker_end=self.marker_end,
                             append_if_not_found=True,
                             append_newline=False)
        self.assertSaltTrueReturn(ret)
        self.assertTrue(ret[next(iter(ret))]['changes'])
        self.assertEqual(self._read(name), expected)
        # Pass 2a: Re-run state, no changes should be made
        ret = self.run_state('file.blockreplace',
                             name=name,
                             content=self.content.rstrip('\r\n'),
                             marker_start=self.marker_start,
                             marker_end=self.marker_end,
                             append_if_not_found=True,
                             append_newline=False)
        self.assertSaltTrueReturn(ret)
        self.assertFalse(ret[next(iter(ret))]['changes'])
        self.assertEqual(self._read(name), expected)

    @with_tempfile()
    def test_prepend_auto_line_separator(self, name):
        '''
        This tests the line separator auto-detection when prepending the block
        '''
        # POSIX newlines to Windows newlines
        self._write(name, self.without_block_explicit_windows_newlines)
        ret = self.run_state('file.blockreplace',
                             name=name,
                             content=self.content_explicit_posix_newlines,
                             marker_start=self.marker_start,
                             marker_end=self.marker_end,
                             prepend_if_not_found=True)
        self.assertSaltTrueReturn(ret)
        self.assertTrue(ret[next(iter(ret))]['changes'])
        self.assertEqual(
            self._read(name),
            self.with_block_prepended_explicit_windows_newlines)
        # Re-run state, no changes should be made
        ret = self.run_state('file.blockreplace',
                             name=name,
                             content=self.content_explicit_posix_newlines,
                             marker_start=self.marker_start,
                             marker_end=self.marker_end,
                             prepend_if_not_found=True)
        self.assertSaltTrueReturn(ret)
        self.assertFalse(ret[next(iter(ret))]['changes'])
        self.assertEqual(
            self._read(name),
            self.with_block_prepended_explicit_windows_newlines)

        # Windows newlines to POSIX newlines
        self._write(name, self.without_block_explicit_posix_newlines)
        ret = self.run_state('file.blockreplace',
                             name=name,
                             content=self.content_explicit_windows_newlines,
                             marker_start=self.marker_start,
                             marker_end=self.marker_end,
                             prepend_if_not_found=True)
        self.assertSaltTrueReturn(ret)
        self.assertTrue(ret[next(iter(ret))]['changes'])
        self.assertEqual(
            self._read(name),
            self.with_block_prepended_explicit_posix_newlines)
        # Re-run state, no changes should be made
        ret = self.run_state('file.blockreplace',
                             name=name,
                             content=self.content_explicit_windows_newlines,
                             marker_start=self.marker_start,
                             marker_end=self.marker_end,
                             prepend_if_not_found=True)
        self.assertSaltTrueReturn(ret)
        self.assertFalse(ret[next(iter(ret))]['changes'])
        self.assertEqual(
            self._read(name),
            self.with_block_prepended_explicit_posix_newlines)

    @with_tempfile()
    def test_append_auto_line_separator(self, name):
        '''
        This tests the line separator auto-detection when appending the block
        '''
        # POSIX newlines to Windows newlines
        self._write(name, self.without_block_explicit_windows_newlines)
        ret = self.run_state('file.blockreplace',
                             name=name,
                             content=self.content_explicit_posix_newlines,
                             marker_start=self.marker_start,
                             marker_end=self.marker_end,
                             append_if_not_found=True)
        self.assertSaltTrueReturn(ret)
        self.assertTrue(ret[next(iter(ret))]['changes'])
        self.assertEqual(
            self._read(name),
            self.with_block_appended_explicit_windows_newlines)
        # Re-run state, no changes should be made
        ret = self.run_state('file.blockreplace',
                             name=name,
                             content=self.content_explicit_posix_newlines,
                             marker_start=self.marker_start,
                             marker_end=self.marker_end,
                             append_if_not_found=True)
        self.assertSaltTrueReturn(ret)
        self.assertFalse(ret[next(iter(ret))]['changes'])
        self.assertEqual(
            self._read(name),
            self.with_block_appended_explicit_windows_newlines)

        # Windows newlines to POSIX newlines
        self._write(name, self.without_block_explicit_posix_newlines)
        ret = self.run_state('file.blockreplace',
                             name=name,
                             content=self.content_explicit_windows_newlines,
                             marker_start=self.marker_start,
                             marker_end=self.marker_end,
                             append_if_not_found=True)
        self.assertSaltTrueReturn(ret)
        self.assertTrue(ret[next(iter(ret))]['changes'])
        self.assertEqual(
            self._read(name),
            self.with_block_appended_explicit_posix_newlines)
        # Re-run state, no changes should be made
        ret = self.run_state('file.blockreplace',
                             name=name,
                             content=self.content_explicit_windows_newlines,
                             marker_start=self.marker_start,
                             marker_end=self.marker_end,
                             append_if_not_found=True)
        self.assertSaltTrueReturn(ret)
        self.assertFalse(ret[next(iter(ret))]['changes'])
        self.assertEqual(
            self._read(name),
            self.with_block_appended_explicit_posix_newlines)

    @with_tempfile()
    def test_non_matching_block(self, name):
        '''
        Test blockreplace when block exists but its contents are not a
        match.
        '''
        # Pass 1: content ends in newline
        self._write(name, self.with_non_matching_block)
        ret = self.run_state('file.blockreplace',
                             name=name,
                             content=self.content,
                             marker_start=self.marker_start,
                             marker_end=self.marker_end)
        self.assertSaltTrueReturn(ret)
        self.assertTrue(ret[next(iter(ret))]['changes'])
        self.assertEqual(self._read(name), self.with_matching_block)
        # Pass 1a: Re-run state, no changes should be made
        ret = self.run_state('file.blockreplace',
                             name=name,
                             content=self.content,
                             marker_start=self.marker_start,
                             marker_end=self.marker_end)
        self.assertSaltTrueReturn(ret)
        self.assertFalse(ret[next(iter(ret))]['changes'])
        self.assertEqual(self._read(name), self.with_matching_block)

        # Pass 2: content does not end in newline
        self._write(name, self.with_non_matching_block)
        ret = self.run_state('file.blockreplace',
                             name=name,
                             content=self.content.rstrip('\r\n'),
                             marker_start=self.marker_start,
                             marker_end=self.marker_end)
        self.assertSaltTrueReturn(ret)
        self.assertTrue(ret[next(iter(ret))]['changes'])
        self.assertEqual(self._read(name), self.with_matching_block)
        # Pass 2a: Re-run state, no changes should be made
        ret = self.run_state('file.blockreplace',
                             name=name,
                             content=self.content.rstrip('\r\n'),
                             marker_start=self.marker_start,
                             marker_end=self.marker_end)
        self.assertSaltTrueReturn(ret)
        self.assertFalse(ret[next(iter(ret))]['changes'])
        self.assertEqual(self._read(name), self.with_matching_block)

    @with_tempfile()
    def test_non_matching_block_append_newline(self, name):
        '''
        Test blockreplace when block exists but its contents are not a
        match. Test with append_newline explicitly set to True.
        '''
        # Pass 1: content ends in newline
        self._write(name, self.with_non_matching_block)
        ret = self.run_state('file.blockreplace',
                             name=name,
                             content=self.content,
                             marker_start=self.marker_start,
                             marker_end=self.marker_end,
                             append_newline=True)
        self.assertSaltTrueReturn(ret)
        self.assertTrue(ret[next(iter(ret))]['changes'])
        self.assertEqual(
            self._read(name),
            self.with_matching_block_and_extra_newline)
        # Pass 1a: Re-run state, no changes should be made
        ret = self.run_state('file.blockreplace',
                             name=name,
                             content=self.content,
                             marker_start=self.marker_start,
                             marker_end=self.marker_end,
                             append_newline=True)
        self.assertSaltTrueReturn(ret)
        self.assertFalse(ret[next(iter(ret))]['changes'])
        self.assertEqual(
            self._read(name),
            self.with_matching_block_and_extra_newline)

        # Pass 2: content does not end in newline
        self._write(name, self.with_non_matching_block)
        ret = self.run_state('file.blockreplace',
                             name=name,
                             content=self.content.rstrip('\r\n'),
                             marker_start=self.marker_start,
                             marker_end=self.marker_end,
                             append_newline=True)
        self.assertSaltTrueReturn(ret)
        self.assertTrue(ret[next(iter(ret))]['changes'])
        self.assertEqual(self._read(name), self.with_matching_block)
        # Pass 2a: Re-run state, no changes should be made
        ret = self.run_state('file.blockreplace',
                             name=name,
                             content=self.content.rstrip('\r\n'),
                             marker_start=self.marker_start,
                             marker_end=self.marker_end,
                             append_newline=True)
        self.assertSaltTrueReturn(ret)
        self.assertFalse(ret[next(iter(ret))]['changes'])
        self.assertEqual(self._read(name), self.with_matching_block)

    @with_tempfile()
    def test_non_matching_block_no_append_newline(self, name):
        '''
        Test blockreplace when block exists but its contents are not a
        match. Test with append_newline explicitly set to False.
        '''
        # Pass 1: content ends in newline
        self._write(name, self.with_non_matching_block)
        ret = self.run_state('file.blockreplace',
                             name=name,
                             content=self.content,
                             marker_start=self.marker_start,
                             marker_end=self.marker_end,
                             append_newline=False)
        self.assertSaltTrueReturn(ret)
        self.assertTrue(ret[next(iter(ret))]['changes'])
        self.assertEqual(self._read(name), self.with_matching_block)
        # Pass 1a: Re-run state, no changes should be made
        ret = self.run_state('file.blockreplace',
                             name=name,
                             content=self.content,
                             marker_start=self.marker_start,
                             marker_end=self.marker_end,
                             append_newline=False)
        self.assertSaltTrueReturn(ret)
        self.assertFalse(ret[next(iter(ret))]['changes'])
        self.assertEqual(self._read(name), self.with_matching_block)

        # Pass 2: content does not end in newline
        self._write(name, self.with_non_matching_block)
        ret = self.run_state('file.blockreplace',
                             name=name,
                             content=self.content.rstrip('\r\n'),
                             marker_start=self.marker_start,
                             marker_end=self.marker_end,
                             append_newline=False)
        self.assertSaltTrueReturn(ret)
        self.assertTrue(ret[next(iter(ret))]['changes'])
        self.assertEqual(
            self._read(name),
            self.with_matching_block_and_marker_end_not_after_newline)
        # Pass 2a: Re-run state, no changes should be made
        ret = self.run_state('file.blockreplace',
                             name=name,
                             content=self.content.rstrip('\r\n'),
                             marker_start=self.marker_start,
                             marker_end=self.marker_end,
                             append_newline=False)
        self.assertSaltTrueReturn(ret)
        self.assertFalse(ret[next(iter(ret))]['changes'])
        self.assertEqual(
            self._read(name),
            self.with_matching_block_and_marker_end_not_after_newline)

    @with_tempfile()
    def test_non_matching_block_and_marker_not_after_newline(self, name):
        '''
        Test blockreplace when block exists but its contents are not a
        match, and the marker_end is not directly preceded by a newline.
        '''
        # Pass 1: content ends in newline
        self._write(
            name,
            self.with_non_matching_block_and_marker_end_not_after_newline)
        ret = self.run_state('file.blockreplace',
                             name=name,
                             content=self.content,
                             marker_start=self.marker_start,
                             marker_end=self.marker_end)
        self.assertSaltTrueReturn(ret)
        self.assertTrue(ret[next(iter(ret))]['changes'])
        self.assertEqual(self._read(name), self.with_matching_block)
        # Pass 1a: Re-run state, no changes should be made
        ret = self.run_state('file.blockreplace',
                             name=name,
                             content=self.content,
                             marker_start=self.marker_start,
                             marker_end=self.marker_end)
        self.assertSaltTrueReturn(ret)
        self.assertFalse(ret[next(iter(ret))]['changes'])
        self.assertEqual(self._read(name), self.with_matching_block)

        # Pass 2: content does not end in newline
        self._write(
            name,
            self.with_non_matching_block_and_marker_end_not_after_newline)
        ret = self.run_state('file.blockreplace',
                             name=name,
                             content=self.content.rstrip('\r\n'),
                             marker_start=self.marker_start,
                             marker_end=self.marker_end)
        self.assertSaltTrueReturn(ret)
        self.assertTrue(ret[next(iter(ret))]['changes'])
        self.assertEqual(self._read(name), self.with_matching_block)
        # Pass 2a: Re-run state, no changes should be made
        ret = self.run_state('file.blockreplace',
                             name=name,
                             content=self.content.rstrip('\r\n'),
                             marker_start=self.marker_start,
                             marker_end=self.marker_end)
        self.assertSaltTrueReturn(ret)
        self.assertFalse(ret[next(iter(ret))]['changes'])
        self.assertEqual(self._read(name), self.with_matching_block)

    @with_tempfile()
    def test_non_matching_block_and_marker_not_after_newline_append_newline(self, name):
        '''
        Test blockreplace when block exists but its contents are not a match,
        and the marker_end is not directly preceded by a newline. Test with
        append_newline explicitly set to True.
        '''
        # Pass 1: content ends in newline
        self._write(
            name,
            self.with_non_matching_block_and_marker_end_not_after_newline)
        ret = self.run_state('file.blockreplace',
                             name=name,
                             content=self.content,
                             marker_start=self.marker_start,
                             marker_end=self.marker_end,
                             append_newline=True)
        self.assertSaltTrueReturn(ret)
        self.assertTrue(ret[next(iter(ret))]['changes'])
        self.assertEqual(
            self._read(name),
            self.with_matching_block_and_extra_newline)
        # Pass 1a: Re-run state, no changes should be made
        ret = self.run_state('file.blockreplace',
                             name=name,
                             content=self.content,
                             marker_start=self.marker_start,
                             marker_end=self.marker_end,
                             append_newline=True)
        self.assertSaltTrueReturn(ret)
        self.assertFalse(ret[next(iter(ret))]['changes'])
        self.assertEqual(
            self._read(name),
            self.with_matching_block_and_extra_newline)

        # Pass 2: content does not end in newline
        self._write(
            name,
            self.with_non_matching_block_and_marker_end_not_after_newline)
        ret = self.run_state('file.blockreplace',
                             name=name,
                             content=self.content.rstrip('\r\n'),
                             marker_start=self.marker_start,
                             marker_end=self.marker_end,
                             append_newline=True)
        self.assertSaltTrueReturn(ret)
        self.assertTrue(ret[next(iter(ret))]['changes'])
        self.assertEqual(self._read(name), self.with_matching_block)
        # Pass 2a: Re-run state, no changes should be made
        ret = self.run_state('file.blockreplace',
                             name=name,
                             content=self.content.rstrip('\r\n'),
                             marker_start=self.marker_start,
                             marker_end=self.marker_end,
                             append_newline=True)
        self.assertSaltTrueReturn(ret)
        self.assertFalse(ret[next(iter(ret))]['changes'])
        self.assertEqual(self._read(name), self.with_matching_block)

    @with_tempfile()
    def test_non_matching_block_and_marker_not_after_newline_no_append_newline(self, name):
        '''
        Test blockreplace when block exists but its contents are not a match,
        and the marker_end is not directly preceded by a newline. Test with
        append_newline explicitly set to False.
        '''
        # Pass 1: content ends in newline
        self._write(
            name,
            self.with_non_matching_block_and_marker_end_not_after_newline)
        ret = self.run_state('file.blockreplace',
                             name=name,
                             content=self.content,
                             marker_start=self.marker_start,
                             marker_end=self.marker_end,
                             append_newline=False)
        self.assertSaltTrueReturn(ret)
        self.assertTrue(ret[next(iter(ret))]['changes'])
        self.assertEqual(self._read(name), self.with_matching_block)
        # Pass 1a: Re-run state, no changes should be made
        ret = self.run_state('file.blockreplace',
                             name=name,
                             content=self.content,
                             marker_start=self.marker_start,
                             marker_end=self.marker_end,
                             append_newline=False)
        self.assertSaltTrueReturn(ret)
        self.assertFalse(ret[next(iter(ret))]['changes'])
        self.assertEqual(self._read(name), self.with_matching_block)

        # Pass 2: content does not end in newline
        self._write(
            name,
            self.with_non_matching_block_and_marker_end_not_after_newline)
        ret = self.run_state('file.blockreplace',
                             name=name,
                             content=self.content.rstrip('\r\n'),
                             marker_start=self.marker_start,
                             marker_end=self.marker_end,
                             append_newline=False)
        self.assertSaltTrueReturn(ret)
        self.assertTrue(ret[next(iter(ret))]['changes'])
        self.assertEqual(
            self._read(name),
            self.with_matching_block_and_marker_end_not_after_newline)
        # Pass 2a: Re-run state, no changes should be made
        ret = self.run_state('file.blockreplace',
                             name=name,
                             content=self.content.rstrip('\r\n'),
                             marker_start=self.marker_start,
                             marker_end=self.marker_end,
                             append_newline=False)
        self.assertSaltTrueReturn(ret)
        self.assertFalse(ret[next(iter(ret))]['changes'])
        self.assertEqual(
            self._read(name),
            self.with_matching_block_and_marker_end_not_after_newline)

    @with_tempfile()
    def test_matching_block(self, name):
        '''
        Test blockreplace when block exists and its contents are a match. No
        changes should be made.
        '''
        # Pass 1: content ends in newline
        self._write(name, self.with_matching_block)
        ret = self.run_state('file.blockreplace',
                             name=name,
                             content=self.content,
                             marker_start=self.marker_start,
                             marker_end=self.marker_end)
        self.assertSaltTrueReturn(ret)
        self.assertFalse(ret[next(iter(ret))]['changes'])
        self.assertEqual(self._read(name), self.with_matching_block)
        # Pass 1a: Re-run state, no changes should be made
        ret = self.run_state('file.blockreplace',
                             name=name,
                             content=self.content,
                             marker_start=self.marker_start,
                             marker_end=self.marker_end)
        self.assertSaltTrueReturn(ret)
        self.assertFalse(ret[next(iter(ret))]['changes'])
        self.assertEqual(self._read(name), self.with_matching_block)

        # Pass 2: content does not end in newline
        self._write(name, self.with_matching_block)
        ret = self.run_state('file.blockreplace',
                             name=name,
                             content=self.content.rstrip('\r\n'),
                             marker_start=self.marker_start,
                             marker_end=self.marker_end)
        self.assertSaltTrueReturn(ret)
        self.assertFalse(ret[next(iter(ret))]['changes'])
        self.assertEqual(self._read(name), self.with_matching_block)
        # Pass 2a: Re-run state, no changes should be made
        ret = self.run_state('file.blockreplace',
                             name=name,
                             content=self.content.rstrip('\r\n'),
                             marker_start=self.marker_start,
                             marker_end=self.marker_end)
        self.assertSaltTrueReturn(ret)
        self.assertFalse(ret[next(iter(ret))]['changes'])
        self.assertEqual(self._read(name), self.with_matching_block)

    @with_tempfile()
    def test_matching_block_append_newline(self, name):
        '''
        Test blockreplace when block exists and its contents are a match. Test
        with append_newline explicitly set to True. This will result in an
        extra newline when the content ends in a newline, and will not when the
        content does not end in a newline.
        '''
        # Pass 1: content ends in newline
        self._write(name, self.with_matching_block)
        ret = self.run_state('file.blockreplace',
                             name=name,
                             content=self.content,
                             marker_start=self.marker_start,
                             marker_end=self.marker_end,
                             append_newline=True)
        self.assertSaltTrueReturn(ret)
        self.assertTrue(ret[next(iter(ret))]['changes'])
        self.assertEqual(
            self._read(name),
            self.with_matching_block_and_extra_newline)
        # Pass 1a: Re-run state, no changes should be made
        ret = self.run_state('file.blockreplace',
                             name=name,
                             content=self.content,
                             marker_start=self.marker_start,
                             marker_end=self.marker_end,
                             append_newline=True)
        self.assertSaltTrueReturn(ret)
        self.assertFalse(ret[next(iter(ret))]['changes'])
        self.assertEqual(
            self._read(name),
            self.with_matching_block_and_extra_newline)

        # Pass 2: content does not end in newline
        self._write(name, self.with_matching_block)
        ret = self.run_state('file.blockreplace',
                             name=name,
                             content=self.content.rstrip('\r\n'),
                             marker_start=self.marker_start,
                             marker_end=self.marker_end,
                             append_newline=True)
        self.assertSaltTrueReturn(ret)
        self.assertFalse(ret[next(iter(ret))]['changes'])
        self.assertEqual(self._read(name), self.with_matching_block)
        # Pass 2a: Re-run state, no changes should be made
        ret = self.run_state('file.blockreplace',
                             name=name,
                             content=self.content.rstrip('\r\n'),
                             marker_start=self.marker_start,
                             marker_end=self.marker_end,
                             append_newline=True)
        self.assertSaltTrueReturn(ret)
        self.assertFalse(ret[next(iter(ret))]['changes'])
        self.assertEqual(self._read(name), self.with_matching_block)

    @with_tempfile()
    def test_matching_block_no_append_newline(self, name):
        '''
        Test blockreplace when block exists and its contents are a match. Test
        with append_newline explicitly set to False. This will result in the
        marker_end not being directly preceded by a newline when the content
        does not end in a newline.
        '''
        # Pass 1: content ends in newline
        self._write(name, self.with_matching_block)
        ret = self.run_state('file.blockreplace',
                             name=name,
                             content=self.content,
                             marker_start=self.marker_start,
                             marker_end=self.marker_end,
                             append_newline=False)
        self.assertSaltTrueReturn(ret)
        self.assertFalse(ret[next(iter(ret))]['changes'])
        self.assertEqual(self._read(name), self.with_matching_block)

        # Pass 1a: Re-run state, no changes should be made
        ret = self.run_state('file.blockreplace',
                             name=name,
                             content=self.content,
                             marker_start=self.marker_start,
                             marker_end=self.marker_end,
                             append_newline=False)
        self.assertSaltTrueReturn(ret)
        self.assertFalse(ret[next(iter(ret))]['changes'])
        self.assertEqual(self._read(name), self.with_matching_block)

        # Pass 2: content does not end in newline
        self._write(name, self.with_matching_block)
        ret = self.run_state('file.blockreplace',
                             name=name,
                             content=self.content.rstrip('\r\n'),
                             marker_start=self.marker_start,
                             marker_end=self.marker_end,
                             append_newline=False)
        self.assertSaltTrueReturn(ret)
        self.assertTrue(ret[next(iter(ret))]['changes'])
        self.assertEqual(
            self._read(name),
            self.with_matching_block_and_marker_end_not_after_newline)

        # Pass 2a: Re-run state, no changes should be made
        ret = self.run_state('file.blockreplace',
                             name=name,
                             content=self.content.rstrip('\r\n'),
                             marker_start=self.marker_start,
                             marker_end=self.marker_end,
                             append_newline=False)
        self.assertSaltTrueReturn(ret)
        self.assertFalse(ret[next(iter(ret))]['changes'])
        self.assertEqual(
            self._read(name),
            self.with_matching_block_and_marker_end_not_after_newline)

    @with_tempfile()
    def test_matching_block_and_marker_not_after_newline(self, name):
        '''
        Test blockreplace when block exists and its contents are a match, but
        the marker_end is not directly preceded by a newline.
        '''
        # Pass 1: content ends in newline
        self._write(
            name,
            self.with_matching_block_and_marker_end_not_after_newline)
        ret = self.run_state('file.blockreplace',
                             name=name,
                             content=self.content,
                             marker_start=self.marker_start,
                             marker_end=self.marker_end)
        self.assertSaltTrueReturn(ret)
        self.assertTrue(ret[next(iter(ret))]['changes'])
        self.assertEqual(self._read(name), self.with_matching_block)
        # Pass 1a: Re-run state, no changes should be made
        ret = self.run_state('file.blockreplace',
                             name=name,
                             content=self.content,
                             marker_start=self.marker_start,
                             marker_end=self.marker_end)
        self.assertSaltTrueReturn(ret)
        self.assertFalse(ret[next(iter(ret))]['changes'])
        self.assertEqual(self._read(name), self.with_matching_block)

        # Pass 2: content does not end in newline
        self._write(
            name,
            self.with_matching_block_and_marker_end_not_after_newline)
        ret = self.run_state('file.blockreplace',
                             name=name,
                             content=self.content.rstrip('\r\n'),
                             marker_start=self.marker_start,
                             marker_end=self.marker_end)
        self.assertSaltTrueReturn(ret)
        self.assertTrue(ret[next(iter(ret))]['changes'])
        self.assertEqual(self._read(name), self.with_matching_block)
        # Pass 2a: Re-run state, no changes should be made
        ret = self.run_state('file.blockreplace',
                             name=name,
                             content=self.content.rstrip('\r\n'),
                             marker_start=self.marker_start,
                             marker_end=self.marker_end)
        self.assertSaltTrueReturn(ret)
        self.assertFalse(ret[next(iter(ret))]['changes'])
        self.assertEqual(self._read(name), self.with_matching_block)

    @with_tempfile()
    def test_matching_block_and_marker_not_after_newline_append_newline(self, name):
        '''
        Test blockreplace when block exists and its contents are a match, but
        the marker_end is not directly preceded by a newline. Test with
        append_newline explicitly set to True. This will result in an extra
        newline when the content ends in a newline, and will not when the
        content does not end in a newline.
        '''
        # Pass 1: content ends in newline
        self._write(
            name,
            self.with_matching_block_and_marker_end_not_after_newline)
        ret = self.run_state('file.blockreplace',
                             name=name,
                             content=self.content,
                             marker_start=self.marker_start,
                             marker_end=self.marker_end,
                             append_newline=True)
        self.assertSaltTrueReturn(ret)
        self.assertTrue(ret[next(iter(ret))]['changes'])
        self.assertEqual(
            self._read(name),
            self.with_matching_block_and_extra_newline)
        # Pass 1a: Re-run state, no changes should be made
        ret = self.run_state('file.blockreplace',
                             name=name,
                             content=self.content,
                             marker_start=self.marker_start,
                             marker_end=self.marker_end,
                             append_newline=True)
        self.assertSaltTrueReturn(ret)
        self.assertFalse(ret[next(iter(ret))]['changes'])
        self.assertEqual(
            self._read(name),
            self.with_matching_block_and_extra_newline)

        # Pass 2: content does not end in newline
        self._write(
            name,
            self.with_matching_block_and_marker_end_not_after_newline)
        ret = self.run_state('file.blockreplace',
                             name=name,
                             content=self.content.rstrip('\r\n'),
                             marker_start=self.marker_start,
                             marker_end=self.marker_end,
                             append_newline=True)
        self.assertSaltTrueReturn(ret)
        self.assertTrue(ret[next(iter(ret))]['changes'])
        self.assertEqual(self._read(name), self.with_matching_block)
        # Pass 2a: Re-run state, no changes should be made
        ret = self.run_state('file.blockreplace',
                             name=name,
                             content=self.content.rstrip('\r\n'),
                             marker_start=self.marker_start,
                             marker_end=self.marker_end,
                             append_newline=True)
        self.assertSaltTrueReturn(ret)
        self.assertFalse(ret[next(iter(ret))]['changes'])
        self.assertEqual(self._read(name), self.with_matching_block)

    @with_tempfile()
    def test_matching_block_and_marker_not_after_newline_no_append_newline(self, name):
        '''
        Test blockreplace when block exists and its contents are a match, but
        the marker_end is not directly preceded by a newline. Test with
        append_newline explicitly set to False.
        '''
        # Pass 1: content ends in newline
        self._write(
            name,
            self.with_matching_block_and_marker_end_not_after_newline)
        ret = self.run_state('file.blockreplace',
                             name=name,
                             content=self.content,
                             marker_start=self.marker_start,
                             marker_end=self.marker_end,
                             append_newline=False)
        self.assertSaltTrueReturn(ret)
        self.assertTrue(ret[next(iter(ret))]['changes'])
        self.assertEqual(self._read(name), self.with_matching_block)
        # Pass 1a: Re-run state, no changes should be made
        ret = self.run_state('file.blockreplace',
                             name=name,
                             content=self.content,
                             marker_start=self.marker_start,
                             marker_end=self.marker_end,
                             append_newline=False)
        self.assertSaltTrueReturn(ret)
        self.assertFalse(ret[next(iter(ret))]['changes'])
        self.assertEqual(self._read(name), self.with_matching_block)

        # Pass 2: content does not end in newline
        self._write(
            name,
            self.with_matching_block_and_marker_end_not_after_newline)
        ret = self.run_state('file.blockreplace',
                             name=name,
                             content=self.content.rstrip('\r\n'),
                             marker_start=self.marker_start,
                             marker_end=self.marker_end,
                             append_newline=False)
        self.assertSaltTrueReturn(ret)
        self.assertFalse(ret[next(iter(ret))]['changes'])
        self.assertEqual(
            self._read(name),
            self.with_matching_block_and_marker_end_not_after_newline)
        # Pass 2a: Re-run state, no changes should be made
        ret = self.run_state('file.blockreplace',
                             name=name,
                             content=self.content.rstrip('\r\n'),
                             marker_start=self.marker_start,
                             marker_end=self.marker_end,
                             append_newline=False)
        self.assertSaltTrueReturn(ret)
        self.assertFalse(ret[next(iter(ret))]['changes'])
        self.assertEqual(
            self._read(name),
            self.with_matching_block_and_marker_end_not_after_newline)


class RemoteFileTest(ModuleCase, SaltReturnAssertsMixin):
    '''
    Uses a local tornado webserver to test http(s) file.managed states with and
    without skip_verify
    '''
    @classmethod
    def setUpClass(cls):
        cls.webserver = Webserver()
        cls.webserver.start()
        cls.source = cls.webserver.url('grail/scene33')
        cls.source_hash = 'd2feb3beb323c79fc7a0f44f1408b4a3'

    @classmethod
    def tearDownClass(cls):
        cls.webserver.stop()

    @with_tempfile(create=False)
    def setUp(self, name):  # pylint: disable=arguments-differ
        self.name = name

    def tearDown(self):
        try:
            os.remove(self.name)
        except OSError as exc:
            if exc.errno != errno.ENOENT:
                raise exc

    def test_file_managed_http_source_no_hash(self):
        '''
        Test a remote file with no hash
        '''
        ret = self.run_state('file.managed',
                             name=self.name,
                             source=self.source,
                             skip_verify=False)
        log.debug('ret = %s', ret)
        # This should fail because no hash was provided
        self.assertSaltFalseReturn(ret)

    def test_file_managed_http_source(self):
        '''
        Test a remote file with no hash
        '''
        ret = self.run_state('file.managed',
                             name=self.name,
                             source=self.source,
                             source_hash=self.source_hash,
                             skip_verify=False)
        log.debug('ret = %s', ret)
        self.assertSaltTrueReturn(ret)

    def test_file_managed_http_source_skip_verify(self):
        '''
        Test a remote file using skip_verify
        '''
        ret = self.run_state('file.managed',
                             name=self.name,
                             source=self.source,
                             skip_verify=True)
        log.debug('ret = %s', ret)
        self.assertSaltTrueReturn(ret)


@skipIf(not salt.utils.path.which('patch'), 'patch is not installed')
class PatchTest(ModuleCase, SaltReturnAssertsMixin):

    @classmethod
    def setUpClass(cls):
        cls.webserver = Webserver()
        cls.webserver.start()

        cls.numbers_patch_name = 'numbers.patch'
        cls.math_patch_name = 'math.patch'
        cls.all_patch_name = 'all.patch'
        cls.numbers_patch_template_name = cls.numbers_patch_name + '.jinja'
        cls.math_patch_template_name = cls.math_patch_name + '.jinja'
        cls.all_patch_template_name = cls.all_patch_name + '.jinja'

        cls.numbers_patch_path = 'patches/' + cls.numbers_patch_name
        cls.math_patch_path = 'patches/' + cls.math_patch_name
        cls.all_patch_path = 'patches/' + cls.all_patch_name
        cls.numbers_patch_template_path = \
            'patches/' + cls.numbers_patch_template_name
        cls.math_patch_template_path = \
            'patches/' + cls.math_patch_template_name
        cls.all_patch_template_path = \
            'patches/' + cls.all_patch_template_name

        cls.numbers_patch = 'salt://' + cls.numbers_patch_path
        cls.math_patch = 'salt://' + cls.math_patch_path
        cls.all_patch = 'salt://' + cls.all_patch_path
        cls.numbers_patch_template = 'salt://' + cls.numbers_patch_template_path
        cls.math_patch_template = 'salt://' + cls.math_patch_template_path
        cls.all_patch_template = 'salt://' + cls.all_patch_template_path

        cls.numbers_patch_http = cls.webserver.url(cls.numbers_patch_path)
        cls.math_patch_http = cls.webserver.url(cls.math_patch_path)
        cls.all_patch_http = cls.webserver.url(cls.all_patch_path)
        cls.numbers_patch_template_http = \
            cls.webserver.url(cls.numbers_patch_template_path)
        cls.math_patch_template_http = \
            cls.webserver.url(cls.math_patch_template_path)
        cls.all_patch_template_http = \
            cls.webserver.url(cls.all_patch_template_path)

        patches_dir = os.path.join(FILES, 'file', 'base', 'patches')
        cls.numbers_patch_hash = salt.utils.hashutils.get_hash(
            os.path.join(patches_dir, cls.numbers_patch_name)
        )
        cls.math_patch_hash = salt.utils.hashutils.get_hash(
            os.path.join(patches_dir, cls.math_patch_name)
        )
        cls.all_patch_hash = salt.utils.hashutils.get_hash(
            os.path.join(patches_dir, cls.all_patch_name)
        )
        cls.numbers_patch_template_hash = salt.utils.hashutils.get_hash(
            os.path.join(patches_dir, cls.numbers_patch_template_name)
        )
        cls.math_patch_template_hash = salt.utils.hashutils.get_hash(
            os.path.join(patches_dir, cls.math_patch_template_name)
        )
        cls.all_patch_template_hash = salt.utils.hashutils.get_hash(
            os.path.join(patches_dir, cls.all_patch_template_name)
        )

        cls.context = {'two': 'two', 'ten': 10}

    @classmethod
    def tearDownClass(cls):
        cls.webserver.stop()

    def setUp(self):
        '''
        Create a new unpatched set of files
        '''
        self.base_dir = tempfile.mkdtemp(dir=TMP)
        os.makedirs(os.path.join(self.base_dir, 'foo', 'bar'))
        self.numbers_file = os.path.join(self.base_dir, 'foo', 'numbers.txt')
        self.math_file = os.path.join(self.base_dir, 'foo', 'bar', 'math.txt')
        with salt.utils.files.fopen(self.numbers_file, 'w') as fp_:
            fp_.write(textwrap.dedent('''\
                one
                two
                three

                1
                2
                3
                '''))
        with salt.utils.files.fopen(self.math_file, 'w') as fp_:
            fp_.write(textwrap.dedent('''\
                Five plus five is ten

                Four squared is sixteen
                '''))

        self.addCleanup(shutil.rmtree, self.base_dir, ignore_errors=True)

    def test_patch_single_file(self):
        '''
        Test file.patch using a patch applied to a single file
        '''
        ret = self.run_state(
            'file.patch',
            name=self.numbers_file,
            source=self.numbers_patch,
        )
        self.assertSaltTrueReturn(ret)
        ret = ret[next(iter(ret))]
        self.assertEqual(ret['comment'], 'Patch successfully applied')

        # Re-run the state, should succeed and there should be a message about
        # a partially-applied hunk.
        ret = self.run_state(
            'file.patch',
            name=self.numbers_file,
            source=self.numbers_patch,
        )
        self.assertSaltTrueReturn(ret)
        ret = ret[next(iter(ret))]
        self.assertEqual(ret['comment'], 'Patch was already applied')
        self.assertEqual(ret['changes'], {})

    def test_patch_directory(self):
        '''
        Test file.patch using a patch applied to a directory, with changes
        spanning multiple files.
        '''
        ret = self.run_state(
            'file.patch',
            name=self.base_dir,
            source=self.all_patch,
            strip=1,
        )
        self.assertSaltTrueReturn(ret)
        ret = ret[next(iter(ret))]
        self.assertEqual(ret['comment'], 'Patch successfully applied')

        # Re-run the state, should succeed and there should be a message about
        # a partially-applied hunk.
        ret = self.run_state(
            'file.patch',
            name=self.base_dir,
            source=self.all_patch,
            strip=1,
        )
        self.assertSaltTrueReturn(ret)
        ret = ret[next(iter(ret))]
        self.assertEqual(ret['comment'], 'Patch was already applied')
        self.assertEqual(ret['changes'], {})

    def test_patch_strip_parsing(self):
        '''
        Test that we successfuly parse -p/--strip when included in the options
        '''
        # Run the state using -p1
        ret = self.run_state(
            'file.patch',
            name=self.base_dir,
            source=self.all_patch,
            options='-p1',
        )
        self.assertSaltTrueReturn(ret)
        ret = ret[next(iter(ret))]
        self.assertEqual(ret['comment'], 'Patch successfully applied')

        # Re-run the state using --strip=1
        ret = self.run_state(
            'file.patch',
            name=self.base_dir,
            source=self.all_patch,
            options='--strip=1',
        )
        self.assertSaltTrueReturn(ret)
        ret = ret[next(iter(ret))]
        self.assertEqual(ret['comment'], 'Patch was already applied')
        self.assertEqual(ret['changes'], {})

        # Re-run the state using --strip 1
        ret = self.run_state(
            'file.patch',
            name=self.base_dir,
            source=self.all_patch,
            options='--strip 1',
        )
        self.assertSaltTrueReturn(ret)
        ret = ret[next(iter(ret))]
        self.assertEqual(ret['comment'], 'Patch was already applied')
        self.assertEqual(ret['changes'], {})

    def test_patch_saltenv(self):
        '''
        Test that we attempt to download the patch from a non-base saltenv
        '''
        # This state will fail because we don't have a patch file in that
        # environment, but that is OK, we just want to test that we're looking
        # in an environment other than base.
        ret = self.run_state(
            'file.patch',
            name=self.math_file,
            source=self.math_patch,
            saltenv='prod',
        )
        self.assertSaltFalseReturn(ret)
        ret = ret[next(iter(ret))]
        self.assertEqual(
            ret['comment'],
            "Source file {0} not found in saltenv 'prod'".format(self.math_patch)
        )

    def test_patch_single_file_failure(self):
        '''
        Test file.patch using a patch applied to a single file. This tests a
        failed patch.
        '''
        # Empty the file to ensure that the patch doesn't apply cleanly
        with salt.utils.files.fopen(self.numbers_file, 'w'):
            pass

        ret = self.run_state(
            'file.patch',
            name=self.numbers_file,
            source=self.numbers_patch,
        )
        self.assertSaltFalseReturn(ret)
        ret = ret[next(iter(ret))]
        self.assertIn('Patch would not apply cleanly', ret['comment'])

        # Test the reject_file option and ensure that the rejects are written
        # to the path specified.
        reject_file = salt.utils.files.mkstemp()
        ret = self.run_state(
            'file.patch',
            name=self.numbers_file,
            source=self.numbers_patch,
            reject_file=reject_file,
            strip=1,
        )
        self.assertSaltFalseReturn(ret)
        ret = ret[next(iter(ret))]
        self.assertIn('Patch would not apply cleanly', ret['comment'])
        self.assertIn(
            'saving rejects to file {0}'.format(reject_file),
            ret['comment']
        )

    def test_patch_directory_failure(self):
        '''
        Test file.patch using a patch applied to a directory, with changes
        spanning multiple files.
        '''
        # Empty the file to ensure that the patch doesn't apply
        with salt.utils.files.fopen(self.math_file, 'w'):
            pass

        ret = self.run_state(
            'file.patch',
            name=self.base_dir,
            source=self.all_patch,
            strip=1,
        )
        self.assertSaltFalseReturn(ret)
        ret = ret[next(iter(ret))]
        self.assertIn('Patch would not apply cleanly', ret['comment'])

        # Test the reject_file option and ensure that the rejects are written
        # to the path specified.
        reject_file = salt.utils.files.mkstemp()
        ret = self.run_state(
            'file.patch',
            name=self.base_dir,
            source=self.all_patch,
            reject_file=reject_file,
            strip=1,
        )
        self.assertSaltFalseReturn(ret)
        ret = ret[next(iter(ret))]
        self.assertIn('Patch would not apply cleanly', ret['comment'])
        self.assertIn(
            'saving rejects to file {0}'.format(reject_file),
            ret['comment']
        )

    def test_patch_single_file_remote_source(self):
        '''
        Test file.patch using a patch applied to a single file, with the patch
        coming from a remote source.
        '''
        # Try without a source_hash and without skip_verify=True, this should
        # fail with a message about the source_hash
        ret = self.run_state(
            'file.patch',
            name=self.math_file,
            source=self.math_patch_http,
        )
        self.assertSaltFalseReturn(ret)
        ret = ret[next(iter(ret))]
        self.assertIn('Unable to verify upstream hash', ret['comment'])

        # Re-run the state with a source hash, it should now succeed
        ret = self.run_state(
            'file.patch',
            name=self.math_file,
            source=self.math_patch_http,
            source_hash=self.math_patch_hash,
        )
        self.assertSaltTrueReturn(ret)
        ret = ret[next(iter(ret))]
        self.assertEqual(ret['comment'], 'Patch successfully applied')

        # Re-run again, this time with no hash and skip_verify=True to test
        # skipping hash verification
        ret = self.run_state(
            'file.patch',
            name=self.math_file,
            source=self.math_patch_http,
            skip_verify=True,
        )
        self.assertSaltTrueReturn(ret)
        ret = ret[next(iter(ret))]
        self.assertEqual(ret['comment'], 'Patch was already applied')
        self.assertEqual(ret['changes'], {})

    def test_patch_directory_remote_source(self):
        '''
        Test file.patch using a patch applied to a directory, with changes
        spanning multiple files, and the patch file coming from a remote
        source.
        '''
        # Try without a source_hash and without skip_verify=True, this should
        # fail with a message about the source_hash
        ret = self.run_state(
            'file.patch',
            name=self.base_dir,
            source=self.all_patch_http,
            strip=1,
        )
        self.assertSaltFalseReturn(ret)
        ret = ret[next(iter(ret))]
        self.assertIn('Unable to verify upstream hash', ret['comment'])

        # Re-run the state with a source hash, it should now succeed
        ret = self.run_state(
            'file.patch',
            name=self.base_dir,
            source=self.all_patch_http,
            source_hash=self.all_patch_hash,
            strip=1,
        )
        self.assertSaltTrueReturn(ret)
        ret = ret[next(iter(ret))]
        self.assertEqual(ret['comment'], 'Patch successfully applied')

        # Re-run again, this time with no hash and skip_verify=True to test
        # skipping hash verification
        ret = self.run_state(
            'file.patch',
            name=self.base_dir,
            source=self.all_patch_http,
            strip=1,
            skip_verify=True,
        )
        self.assertSaltTrueReturn(ret)
        ret = ret[next(iter(ret))]
        self.assertEqual(ret['comment'], 'Patch was already applied')
        self.assertEqual(ret['changes'], {})

    def test_patch_single_file_template(self):
        '''
        Test file.patch using a patch applied to a single file, with jinja
        templating applied to the patch file.
        '''
        ret = self.run_state(
            'file.patch',
            name=self.numbers_file,
            source=self.numbers_patch_template,
            template='jinja',
            context=self.context,
        )
        self.assertSaltTrueReturn(ret)
        ret = ret[next(iter(ret))]
        self.assertEqual(ret['comment'], 'Patch successfully applied')

        # Re-run the state, should succeed and there should be a message about
        # a partially-applied hunk.
        ret = self.run_state(
            'file.patch',
            name=self.numbers_file,
            source=self.numbers_patch_template,
            template='jinja',
            context=self.context,
        )
        self.assertSaltTrueReturn(ret)
        ret = ret[next(iter(ret))]
        self.assertEqual(ret['comment'], 'Patch was already applied')
        self.assertEqual(ret['changes'], {})

    def test_patch_directory_template(self):
        '''
        Test file.patch using a patch applied to a directory, with changes
        spanning multiple files, and with jinja templating applied to the patch
        file.
        '''
        ret = self.run_state(
            'file.patch',
            name=self.base_dir,
            source=self.all_patch_template,
            template='jinja',
            context=self.context,
            strip=1,
        )
        self.assertSaltTrueReturn(ret)
        ret = ret[next(iter(ret))]
        self.assertEqual(ret['comment'], 'Patch successfully applied')

        # Re-run the state, should succeed and there should be a message about
        # a partially-applied hunk.
        ret = self.run_state(
            'file.patch',
            name=self.base_dir,
            source=self.all_patch_template,
            template='jinja',
            context=self.context,
            strip=1,
        )
        self.assertSaltTrueReturn(ret)
        ret = ret[next(iter(ret))]
        self.assertEqual(ret['comment'], 'Patch was already applied')
        self.assertEqual(ret['changes'], {})

    def test_patch_single_file_remote_source_template(self):
        '''
        Test file.patch using a patch applied to a single file, with the patch
        coming from a remote source.
        '''
        # Try without a source_hash and without skip_verify=True, this should
        # fail with a message about the source_hash
        ret = self.run_state(
            'file.patch',
            name=self.math_file,
            source=self.math_patch_template_http,
            template='jinja',
            context=self.context,
        )
        self.assertSaltFalseReturn(ret)
        ret = ret[next(iter(ret))]
        self.assertIn('Unable to verify upstream hash', ret['comment'])

        # Re-run the state with a source hash, it should now succeed
        ret = self.run_state(
            'file.patch',
            name=self.math_file,
            source=self.math_patch_template_http,
            source_hash=self.math_patch_template_hash,
            template='jinja',
            context=self.context,
        )
        self.assertSaltTrueReturn(ret)
        ret = ret[next(iter(ret))]
        self.assertEqual(ret['comment'], 'Patch successfully applied')

        # Re-run again, this time with no hash and skip_verify=True to test
        # skipping hash verification
        ret = self.run_state(
            'file.patch',
            name=self.math_file,
            source=self.math_patch_template_http,
            template='jinja',
            context=self.context,
            skip_verify=True,
        )
        self.assertSaltTrueReturn(ret)
        ret = ret[next(iter(ret))]
        self.assertEqual(ret['comment'], 'Patch was already applied')
        self.assertEqual(ret['changes'], {})

    def test_patch_directory_remote_source_template(self):
        '''
        Test file.patch using a patch applied to a directory, with changes
        spanning multiple files, and the patch file coming from a remote
        source.
        '''
        # Try without a source_hash and without skip_verify=True, this should
        # fail with a message about the source_hash
        ret = self.run_state(
            'file.patch',
            name=self.base_dir,
            source=self.all_patch_template_http,
            template='jinja',
            context=self.context,
            strip=1,
        )
        self.assertSaltFalseReturn(ret)
        ret = ret[next(iter(ret))]
        self.assertIn('Unable to verify upstream hash', ret['comment'])

        # Re-run the state with a source hash, it should now succeed
        ret = self.run_state(
            'file.patch',
            name=self.base_dir,
            source=self.all_patch_template_http,
            source_hash=self.all_patch_template_hash,
            template='jinja',
            context=self.context,
            strip=1,
        )
        self.assertSaltTrueReturn(ret)
        ret = ret[next(iter(ret))]
        self.assertEqual(ret['comment'], 'Patch successfully applied')

        # Re-run again, this time with no hash and skip_verify=True to test
        # skipping hash verification
        ret = self.run_state(
            'file.patch',
            name=self.base_dir,
            source=self.all_patch_template_http,
            template='jinja',
            context=self.context,
            strip=1,
            skip_verify=True,
        )
        self.assertSaltTrueReturn(ret)
        ret = ret[next(iter(ret))]
        self.assertEqual(ret['comment'], 'Patch was already applied')
        self.assertEqual(ret['changes'], {})

    def test_patch_test_mode(self):
        '''
        Test file.patch using test=True
        '''
        # Try without a source_hash and without skip_verify=True, this should
        # fail with a message about the source_hash
        ret = self.run_state(
            'file.patch',
            name=self.numbers_file,
            source=self.numbers_patch,
            test=True,
        )
        self.assertSaltNoneReturn(ret)
        ret = ret[next(iter(ret))]
        self.assertEqual(ret['comment'], 'The patch would be applied')
        self.assertTrue(ret['changes'])

        # Apply the patch for real. We'll then be able to test below that we
        # exit with a True rather than a None result if test=True is used on an
        # already-applied patch.
        ret = self.run_state(
            'file.patch',
            name=self.numbers_file,
            source=self.numbers_patch,
        )
        self.assertSaltTrueReturn(ret)
        ret = ret[next(iter(ret))]
        self.assertEqual(ret['comment'], 'Patch successfully applied')
        self.assertTrue(ret['changes'])

        # Run again with test=True. Since the pre-check happens before we do
        # the __opts__['test'] check, we should exit with a True result just
        # the same as if we try to run this state on an already-patched file
        # *without* test=True.
        ret = self.run_state(
            'file.patch',
            name=self.numbers_file,
            source=self.numbers_patch,
            test=True,
        )
        self.assertSaltTrueReturn(ret)
        ret = ret[next(iter(ret))]
        self.assertEqual(ret['comment'], 'Patch was already applied')
        self.assertEqual(ret['changes'], {})

        # Empty the file to ensure that the patch doesn't apply cleanly
        with salt.utils.files.fopen(self.numbers_file, 'w'):
            pass

        # Run again with test=True. Similar to the above run, we are testing
        # that we return before we reach the __opts__['test'] check. In this
        # case we should return a False result because we should already know
        # by this point that the patch will not apply cleanly.
        ret = self.run_state(
            'file.patch',
            name=self.numbers_file,
            source=self.numbers_patch,
            test=True,
        )
        self.assertSaltFalseReturn(ret)
        ret = ret[next(iter(ret))]
        self.assertIn('Patch would not apply cleanly', ret['comment'])
        self.assertEqual(ret['changes'], {})
