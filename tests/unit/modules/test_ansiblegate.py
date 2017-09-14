# -*- coding: utf-8 -*-
#
# Author: Bo Maryniuk <bo@suse.de>
#
# Copyright 2017 SUSE LLC
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

# Import Salt Testing Libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.unit import TestCase, skipIf
from tests.support.mock import (
    Mock,
    MagicMock,
    call,
    patch,
    NO_MOCK,
    NO_MOCK_REASON
)

import salt.modules.ansiblegate as ansible


@skipIf(NO_MOCK, NO_MOCK_REASON)
class AnsiblegateTestCase(TestCase, LoaderModuleMockMixin):
    def setUp(self):
        self.resolver = ansible.AnsibleModuleResolver({})
        self.resolver._modules_map = {
            'one.two.three': '/one/two/three.py',
            'four.five.six': '/four/five/six.py',
            'three.six.one': '/three/six/one.py',
        }

    def tearDown(self):
        self.resolver = None

    def setup_loader_modules(self):
        return {ansible: {}}

    def test_ansible_module_help(self):
        '''
        Test help extraction from the module
        :return:
        '''
        class Module(object):
            '''
            An ansible module mock.
            '''
            __name__ = 'foo'
            DOCUMENTATION = """
---
one:
   text here
---
two:
   text here
description:
   describe the second part
        """

        ansible._resolver = self.resolver
        ansible._resolver.load_module = MagicMock(return_value=Module())
        ret = ansible.help('dummy')
        assert sorted(ret.get('Available sections on module "{0}"'.format(
            Module().__name__))) == ['one', 'two']
        assert ret.get('Description') == 'describe the second part'

    def test_module_resolver_modlist(self):
        '''
        Test Ansible resolver modules list.
        :return:
        '''
        assert self.resolver.get_modules_list() == ['four.five.six', 'one.two.three', 'three.six.one']
        for ptr in ['five', 'fi', 've']:
            assert self.resolver.get_modules_list(ptr) == ['four.five.six']
        for ptr in ['si', 'ix', 'six']:
            assert self.resolver.get_modules_list(ptr) == ['four.five.six', 'three.six.one']
        assert self.resolver.get_modules_list('one') == ['one.two.three', 'three.six.one']
        assert self.resolver.get_modules_list('one.two') == ['one.two.three']
        assert self.resolver.get_modules_list('four') == ['four.five.six']
