# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Nicole Thomas <nicole@saltstack.com>`
'''

# Import Python libs
from __future__ import absolute_import
import os
import sys
import tempfile

# Import Salt Testing libs
import integration
from salttesting import TestCase, skipIf
from salttesting.helpers import ensure_in_syspath
from salttesting.mock import NO_MOCK, NO_MOCK_REASON, patch, MagicMock

ensure_in_syspath('../')

# Import Salt libs
import salt.state
import salt.config
import salt.exceptions
from salt.utils.odict import OrderedDict, DefaultOrderedDict


@skipIf(NO_MOCK, NO_MOCK_REASON)
class StateCompilerTestCase(TestCase):
    '''
    TestCase for the state compiler.
    '''

    def test_format_log_non_ascii_character(self):
        '''
        Tests running a non-ascii character through the state.format_log
        function. See Issue #33605.
        '''
        # There is no return to test against as the format_log
        # function doesn't return anything. However, we do want
        # to make sure that the function doesn't stacktrace when
        # called.
        ret = {'changes': {u'Français': {'old': 'something old',
                                         'new': 'something new'}},
               'result': True}
        salt.state.format_log(ret)

    @skipIf(sys.version_info < (2, 7), 'Context manager in assertEquals only available in > Py2.7')
    @patch('salt.state.State._gather_pillar')
    def test_render_error_on_invalid_requisite(self, state_patch):
        '''
        Test that the state compiler correctly deliver a rendering
        exception when a requisite cannot be resolved
        '''
        high_data = {'git': OrderedDict([('pkg', [OrderedDict([('require', [OrderedDict([('file', OrderedDict([('test1', 'test')]))])])]), 'installed', {'order': 10000}]), ('__sls__', u'issue_35226'), ('__env__', 'base')])}
        minion_opts = salt.config.minion_config(os.path.join(integration.TMP_CONF_DIR, 'minion'))
        minion_opts['pillar'] = {'git': OrderedDict([('test1', 'test')])}
        state_obj = salt.state.State(minion_opts)
        with self.assertRaises(salt.exceptions.SaltRenderError):
            state_obj.call_high(high_data)


class HighStateTestCase(TestCase):
    def setUp(self):
        self.root_dir = tempfile.mkdtemp(dir=integration.TMP)
        self.state_tree_dir = os.path.join(self.root_dir, 'state_tree')
        self.cache_dir = os.path.join(self.root_dir, 'cachedir')
        if not os.path.isdir(self.root_dir):
            os.makedirs(self.root_dir)

        if not os.path.isdir(self.state_tree_dir):
            os.makedirs(self.state_tree_dir)

        if not os.path.isdir(self.cache_dir):
            os.makedirs(self.cache_dir)
        self.config = salt.config.minion_config(None)
        self.config['root_dir'] = self.root_dir
        self.config['state_events'] = False
        self.config['id'] = 'match'
        self.config['file_client'] = 'local'
        self.config['file_roots'] = dict(base=[self.state_tree_dir])
        self.config['cachedir'] = self.cache_dir
        self.config['test'] = False
        self.highstate = salt.state.HighState(self.config)
        self.highstate.push_active()

    def tearDown(self):
        self.highstate.pop_active()

    def test_top_matches_with_list(self):
        top = {'env': {'match': ['state1', 'state2'], 'nomatch': ['state3']}}
        matches = self.highstate.top_matches(top)
        self.assertEqual(matches, {'env': ['state1', 'state2']})

    def test_top_matches_with_string(self):
        top = {'env': {'match': 'state1', 'nomatch': 'state2'}}
        matches = self.highstate.top_matches(top)
        self.assertEqual(matches, {'env': ['state1']})

    def test_matches_whitelist(self):
        matches = {'env': ['state1', 'state2', 'state3']}
        matches = self.highstate.matches_whitelist(matches, ['state2'])
        self.assertEqual(matches, {'env': ['state2']})

    def test_matches_whitelist_with_string(self):
        matches = {'env': ['state1', 'state2', 'state3']}
        matches = self.highstate.matches_whitelist(matches,
                                                   'state2,state3')
        self.assertEqual(matches, {'env': ['state2', 'state3']})


class TopFileMergeTestCase(TestCase):
    '''
    Test various merge strategies for multiple tops files collected from
    multiple environments. Various options correspond to merge strategies
    which can be set by the user with the top_file_merging_strategy config
    option.

    Refs #12483
    '''
    def setUp(self):
        '''
        Create multiple top files for use in each test
        '''
        self.env1 = {'base': {'*': ['e1_a', 'e1_b', 'e1_c']}}
        self.env2 = {'base': {'*': ['e2_a', 'e2_b', 'e2_c']}}
        self.env3 = {'base': {'*': ['e3_a', 'e3_b', 'e3_c']}}
        self.config = self._make_default_config()
        self.highstate = salt.state.HighState(self.config)

    def _make_default_config(self):
        config = salt.config.minion_config(None)
        root_dir = tempfile.mkdtemp(dir=integration.TMP)
        state_tree_dir = os.path.join(root_dir, 'state_tree')
        cache_dir = os.path.join(root_dir, 'cachedir')
        config['root_dir'] = root_dir
        config['state_events'] = False
        config['id'] = 'match'
        config['file_client'] = 'local'
        config['file_roots'] = dict(base=[state_tree_dir])
        config['cachedir'] = cache_dir
        config['test'] = False
        return config

    def _get_tops(self):
        '''
        A test helper to emulate salt.state.HighState.get_tops() but just to
        construct an appropriate data structure for top files from multiple
        environments
        '''
        tops = DefaultOrderedDict(list)

        tops['a'].append(self.env1)
        tops['b'].append(self.env2)
        tops['c'].append(self.env3)
        return tops

    def test_basic_merge(self):
        '''
        This is the default approach for Salt. Merge the top files with the
        earlier appends taking precendence. Since Salt does the appends
        lexecographically, this is effectively a test against the default
        lexecographical behaviour.
        '''
        merged_tops = self.highstate.merge_tops(self._get_tops())

        expected_merge = DefaultOrderedDict(OrderedDict)
        expected_merge['base']['*'] = ['e1_c', 'e1_b', 'e1_a']
        self.assertEqual(merged_tops, expected_merge)

    def test_merge_strategy_same(self):
        '''
        Test to see if the top file that corresponds
        to the requested env is the one that is used
        by the state system
        '''
        config = self._make_default_config()
        config['top_file_merging_strategy'] = 'same'
        config['environment'] = 'b'
        highstate = salt.state.HighState(config)
        ret = highstate.get_tops()
        self.assertEqual(ret, OrderedDict([('b', [{}])]))

    def test_ordered_merge(self):
        '''
        Test to see if the merger respects environment
        ordering
        '''
        config = self._make_default_config()
        config['top_file_merging_strategy'] = 'merge'
        config['env_order'] = ['b', 'a', 'c']
        with patch('salt.fileclient.FSClient.envs', MagicMock(return_value=['a', 'b', 'c'])):
            highstate = salt.state.HighState(config)
            ret = highstate.get_tops()
        self.assertEqual(ret, OrderedDict([('a', [{}]), ('c', [{}]), ('b', [{}])]))


if __name__ == '__main__':
    from integration import run_tests
    run_tests(StateCompilerTestCase, needs_daemon=False)
