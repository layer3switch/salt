# -*- coding: utf-8 -*-

# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals

# Import Salt Testing Libs
from tests.support.case import SSHCase


class SSHJinjaFiltersTest(SSHCase):
    '''
    testing the state system with salt-ssh
    '''

    def test_data_compare_dicts(self):
        '''
        test jinja filter data.compare_dicts
        '''
        _expected = {u'ret': {u'a': {u'new': u'c', u'old': u'b'}}}

        ret = self.run_function('state.sls',
                                ['jinja_filters.data_compare_dicts'])
        self.assertIn('module_|-test_|-test.echo_|-run', ret)
        self.assertEqual(ret['module_|-test_|-test.echo_|-run']['changes'],
                         _expected)

    def test_data_compare_lists(self):
        '''
        test jinja filter data.compare_list
        '''
        _expected = {u'ret': {u'old': u'b'}}
        ret = self.run_function('state.sls',
                                ['jinja_filters.data_compare_lists'])
        self.assertIn('module_|-test_|-test.echo_|-run', ret)
        self.assertEqual(ret['module_|-test_|-test.echo_|-run']['changes'],
                         _expected)

    def test_data_decode_dict(self):
        '''
        test jinja filter data.decode_dict
        '''
        _expected = {u'ret': {u'a': u'b', u'c': u'd'}}
        ret = self.run_function('state.sls',
                                ['jinja_filters.data_decode_dict'])
        self.assertIn('module_|-test_|-test.echo_|-run', ret)
        self.assertEqual(ret['module_|-test_|-test.echo_|-run']['changes'],
                         _expected)

    def test_data_decode_list(self):
        '''
        test jinja filter data.decode_list
        '''
        _expected = {u'ret': [u'a', u'b', u'c', u'd']}
        ret = self.run_function('state.sls',
                                ['jinja_filters.data_decode_list'])
        self.assertIn('module_|-test_|-test.echo_|-run', ret)
        self.assertEqual(ret['module_|-test_|-test.echo_|-run']['changes'],
                         _expected)

    def test_data_encode_dict(self):
        '''
        test jinja filter data.encode_dict
        '''
        _expected = {u'ret': {u'a': u'b', u'c': u'd'}}
        ret = self.run_function('state.sls',
                                ['jinja_filters.data_encode_dict'])
        self.assertIn('module_|-test_|-test.echo_|-run', ret)
        self.assertEqual(ret['module_|-test_|-test.echo_|-run']['changes'],
                         _expected)

    def test_data_encode_list(self):
        '''
        test jinja filter data.encode_list
        '''
        _expected = {u'ret': [u'a', u'b', u'c', u'd']}
        ret = self.run_function('state.sls',
                                ['jinja_filters.data_encode_list'])
        self.assertIn('module_|-test_|-test.echo_|-run', ret)
        self.assertEqual(ret['module_|-test_|-test.echo_|-run']['changes'],
                         _expected)

    def test_data_exactly_n(self):
        '''
        test jinja filter data.exactly_n
        '''
        _expected = {u'ret': True}
        ret = self.run_function('state.sls',
                                ['jinja_filters.data_exactly_n'])
        self.assertIn('module_|-test_|-test.echo_|-run', ret)
        self.assertEqual(ret['module_|-test_|-test.echo_|-run']['changes'],
                         _expected)

    def test_data_exactly_one(self):
        '''
        test jinja filter data.exactly_one
        '''
        _expected = {u'ret': True}
        ret = self.run_function('state.sls',
                                ['jinja_filters.data_exactly_one'])
        self.assertIn('module_|-test_|-test.echo_|-run', ret)
        self.assertEqual(ret['module_|-test_|-test.echo_|-run']['changes'],
                         _expected)

    def test_data_is_iter(self):
        '''
        test jinja filter data.is_iter
        '''
        _expected = {u'ret': True}
        ret = self.run_function('state.sls',
                                ['jinja_filters.data_is_iter'])
        self.assertIn('module_|-test_|-test.echo_|-run', ret)
        self.assertEqual(ret['module_|-test_|-test.echo_|-run']['changes'],
                         _expected)

    def test_data_is_list(self):
        '''
        test jinja filter data.is_list
        '''
        _expected = {u'ret': True}
        ret = self.run_function('state.sls',
                                ['jinja_filters.data_is_list'])
        self.assertIn('module_|-test_|-test.echo_|-run', ret)
        self.assertEqual(ret['module_|-test_|-test.echo_|-run']['changes'],
                         _expected)

    def test_data_mysql_to_dict(self):
        '''
        test jinja filter data.mysql_to_dict
        '''
        _expected = {u'ret': {u'show processlist': {u'Info': u'show processlist', u'db': u'NULL', u'Host': u'localhost', u'State': u'init', u'Command': u'Query', u'User': u'root', u'Time': 0, u'Id': 7}}}
        ret = self.run_function('state.sls',
                                ['jinja_filters.data_mysql_to_dict'])
        self.assertIn('module_|-test_|-test.echo_|-run', ret)
        self.assertEqual(ret['module_|-test_|-test.echo_|-run']['changes'],
                         _expected)

    def test_data_sorted_ignorecase(self):
        '''
        test jinja filter data.softed_ignorecase
        '''
        _expected = {u'ret': [u'Abcd', u'efgh', u'Ijk', u'lmno', u'Pqrs']}
        ret = self.run_function('state.sls',
                                ['jinja_filters.data_sorted_ignorecase'])
        self.assertIn('module_|-test_|-test.echo_|-run', ret)
        self.assertEqual(ret['module_|-test_|-test.echo_|-run']['changes'],
                         _expected)

    def test_data_substring_in_list(self):
        '''
        test jinja filter data.substring_in_list
        '''
        _expected = {u'ret': True}
        ret = self.run_function('state.sls',
                                ['jinja_filters.data_substring_in_list'])
        self.assertIn('module_|-test_|-test.echo_|-run', ret)
        self.assertEqual(ret['module_|-test_|-test.echo_|-run']['changes'],
                         _expected)

    def test_dateutils_strftime(self):
        '''
        test jinja filter datautils.strftime
        '''
        _expected = {u'ret': ''}
        ret = self.run_function('state.sls',
                                ['jinja_filters.dateutils_strftime'])
        self.assertIn('module_|-test_|-test.echo_|-run', ret)
        self.assertEqual(ret['module_|-test_|-test.echo_|-run']['changes'],
                         _expected)

    def test_files_is_binary(self):
        '''
        test jinja filter files.is_binary
        '''
        _expected = {u'ret': True}
        ret = self.run_function('state.sls',
                                ['jinja_filters.files_is_binary'])
        self.assertIn('module_|-test_|-test.echo_|-run', ret)
        self.assertEqual(ret['module_|-test_|-test.echo_|-run']['changes'],
                         _expected)

    def test_files_is_empty(self):
        '''
        test jinja filter files.is_empty
        '''
        _expected = {u'ret': True}
        ret = self.run_function('state.sls',
                                ['jinja_filters.files_is_empty'])
        self.assertIn('module_|-test_|-test.echo_|-run', ret)
        self.assertEqual(ret['module_|-test_|-test.echo_|-run']['changes'],
                         _expected)

    def test_files_is_text(self):
        '''
        test jinja filter files.is_text
        '''
        _expected = {u'ret': True}
        ret = self.run_function('state.sls',
                                ['jinja_filters.files_is_text'])
        self.assertIn('module_|-test_|-test.echo_|-run', ret)
        self.assertEqual(ret['module_|-test_|-test.echo_|-run']['changes'],
                         _expected)

    def test_files_list_files(self):
        '''
        test jinja filter files.list_files
        '''
        ret = self.run_function('state.sls',
                                ['jinja_filters.files_list_files'])
        self.assertIn('module_|-test_|-test.echo_|-run', ret)
        self.assertIn('/bin/ls',
                      ret['module_|-test_|-test.echo_|-run']['changes']['ret'])

    def test_hashutils_base4_64decode(self):
        '''
        test jinja filter hashutils.base64_64decode
        '''
        _expected = {u'ret': 'Salt Rocks!'}
        ret = self.run_function('state.sls',
                                ['jinja_filters.hashutils_base4_64decode'])
        self.assertIn('module_|-test_|-test.echo_|-run', ret)
        self.assertEqual(ret['module_|-test_|-test.echo_|-run']['changes'],
                         _expected)

    def test_hashutils_base4_64encode(self):
        '''
        test jinja filter hashutils.base64_64encode
        '''
        _expected = {u'ret': 'U2FsdCBSb2NrcyE='}
        ret = self.run_function('state.sls',
                                ['jinja_filters.hashutils_base4_64encode'])
        self.assertIn('module_|-test_|-test.echo_|-run', ret)
        self.assertEqual(ret['module_|-test_|-test.echo_|-run']['changes'],
                         _expected)

    def test_hashutils_file_hashsum(self):
        '''
        test jinja filter hashutils.file_hashsum
        '''
        _expected = {u'ret': '1faec9786e4fd621f32c060a0b0cf2562fdd0cc1f338d1f2fcbdf79380c0ffb1'}
        ret = self.run_function('state.sls',
                                ['jinja_filters.hashutils_file_hashsum'])
        self.assertIn('module_|-test_|-test.echo_|-run', ret)
        self.assertEqual(ret['module_|-test_|-test.echo_|-run']['changes'],
                         _expected)

    def test_hashutils_hmac(self):
        '''
        test jinja filter hashutils.hmac
        '''
        _expected = {u'ret': True}
        ret = self.run_function('state.sls',
                                ['jinja_filters.hashutils_hmac'])
        self.assertIn('module_|-test_|-test.echo_|-run', ret)
        self.assertEqual(ret['module_|-test_|-test.echo_|-run']['changes'],
                         _expected)

    def test_hashutils_md5_digest(self):
        '''
        test jinja filter hashutils.md5_digest
        '''
        _expected = {u'ret': '85d6e71db655ee8e42c8b18475f0925f'}
        ret = self.run_function('state.sls',
                                ['jinja_filters.hashutils_md5_digest'])
        self.assertIn('module_|-test_|-test.echo_|-run', ret)
        self.assertEqual(ret['module_|-test_|-test.echo_|-run']['changes'],
                         _expected)

    def test_hashutils_random_hash(self):
        '''
        test jinja filter hashutils.random_hash
        '''
        ret = self.run_function('state.sls',
                                ['jinja_filters.hashutils_random_hash'])
        self.assertIn('module_|-test_|-test.echo_|-run', ret)
        self.assertIn('ret',
                      ret['module_|-test_|-test.echo_|-run']['changes'])

    def test_hashutils_sha256_digest(self):
        '''
        test jinja filter hashutils.sha256_digest
        '''
        _expected = {u'ret': 'cce7fe00fd9cc6122fd3b2ed22feae215bcfe7ac4a7879d336c1993426a763fe'}
        ret = self.run_function('state.sls',
                                ['jinja_filters.hashutils_sha256_digest'])
        self.assertIn('module_|-test_|-test.echo_|-run', ret)
        self.assertEqual(ret['module_|-test_|-test.echo_|-run']['changes'],
                         _expected)

    def test_hashutils_sha512_digest(self):
        '''
        test jinja filter hashutils.sha512_digest
        '''
        _expected = {u'ret': '44d829491d8caa7039ad08a5b7fa9dd0f930138c614411c5326dd4755fdc9877ec6148219fccbe404139e7bb850e77237429d64f560c204f3697ab489fd8bfa5'}
        ret = self.run_function('state.sls',
                                ['jinja_filters.hashutils_sha512_digest'])
        self.assertIn('module_|-test_|-test.echo_|-run', ret)
        self.assertEqual(ret['module_|-test_|-test.echo_|-run']['changes'],
                         _expected)

    def test_http_query(self):
        '''
        test jinja filter http.query
        '''
        _expected = {u'ret': {}}
        ret = self.run_function('state.sls',
                                ['jinja_filters.http_query'])
        self.assertIn('module_|-test_|-test.echo_|-run', ret)
        self.assertEqual(ret['module_|-test_|-test.echo_|-run']['changes'],
                         _expected)

    def test_jinja_avg(self):
        '''
        test jinja filter jinja.avg
        '''
        _expected = {u'ret': 2.0}
        ret = self.run_function('state.sls',
                                ['jinja_filters.jinja_avg'])
        self.assertIn('module_|-test_|-test.echo_|-run', ret)
        self.assertEqual(ret['module_|-test_|-test.echo_|-run']['changes'],
                         _expected)

    def test_jinja_difference(self):
        '''
        test jinja filter jinja.difference
        '''
        _expected = {u'ret': [1, 3]}
        ret = self.run_function('state.sls',
                                ['jinja_filters.jinja_difference'])
        self.assertIn('module_|-test_|-test.echo_|-run', ret)
        self.assertEqual(ret['module_|-test_|-test.echo_|-run']['changes'],
                         _expected)

    def test_jinja_intersect(self):
        '''
        test jinja filter jinja.intersect
        '''
        _expected = {u'ret': [2, 4]}
        ret = self.run_function('state.sls',
                                ['jinja_filters.jinja_intersect'])
        self.assertIn('module_|-test_|-test.echo_|-run', ret)
        self.assertEqual(ret['module_|-test_|-test.echo_|-run']['changes'],
                         _expected)

    def test_jinja_max(self):
        '''
        test jinja filter jinja.max
        '''
        _expected = {u'ret': 4}
        ret = self.run_function('state.sls',
                                ['jinja_filters.jinja_max'])
        self.assertIn('module_|-test_|-test.echo_|-run', ret)
        self.assertEqual(ret['module_|-test_|-test.echo_|-run']['changes'],
                         _expected)

    def test_jinja_min(self):
        '''
        test jinja filter jinja.min
        '''
        _expected = {u'ret': 1}
        ret = self.run_function('state.sls',
                                ['jinja_filters.jinja_min'])
        self.assertIn('module_|-test_|-test.echo_|-run', ret)
        self.assertEqual(ret['module_|-test_|-test.echo_|-run']['changes'],
                         _expected)

    def test_jinja_quote(self):
        '''
        test jinja filter jinja.quote
        '''
        _expected = {u'ret': 'Salt Rocks!'}
        ret = self.run_function('state.sls',
                                ['jinja_filters.jinja_quote'])
        self.assertIn('module_|-test_|-test.echo_|-run', ret)
        self.assertEqual(ret['module_|-test_|-test.echo_|-run']['changes'],
                         _expected)

    def test_jinja_regex_escape(self):
        '''
        test jinja filter jinja.regex_escape
        '''
        _expected = {u'ret': 'Salt\\ Rocks'}
        ret = self.run_function('state.sls',
                                ['jinja_filters.jinja_regex_escape'])
        self.assertIn('module_|-test_|-test.echo_|-run', ret)
        self.assertEqual(ret['module_|-test_|-test.echo_|-run']['changes'],
                         _expected)

    def test_jinja_regex_match(self):
        '''
        test jinja filter jinja.regex_match
        '''
        _expected = {u'ret': "('a', 'd')"}
        ret = self.run_function('state.sls',
                                ['jinja_filters.jinja_regex_match'])
        self.assertIn('module_|-test_|-test.echo_|-run', ret)
        self.assertEqual(ret['module_|-test_|-test.echo_|-run']['changes'],
                         _expected)

    def test_jinja_regex_replace(self):
        '''
        test jinja filter jinja.regex_replace
        '''
        _expected = {u'ret': 'lets__replace__spaces'}
        ret = self.run_function('state.sls',
                                ['jinja_filters.jinja_regex_replace'])
        self.assertIn('module_|-test_|-test.echo_|-run', ret)
        self.assertEqual(ret['module_|-test_|-test.echo_|-run']['changes'],
                         _expected)

    def test_jinja_regex_search(self):
        '''
        test jinja filter jinja.regex_search
        '''
        _expected = {u'ret': "('a', 'd')"}
        ret = self.run_function('state.sls',
                                ['jinja_filters.jinja_regex_search'])
        self.assertIn('module_|-test_|-test.echo_|-run', ret)
        self.assertEqual(ret['module_|-test_|-test.echo_|-run']['changes'],
                         _expected)

    def test_jinja_sequence(self):
        '''
        test jinja filter jinja.sequence
        '''
        _expected = {u'ret': [u'Salt Rocks!']}
        ret = self.run_function('state.sls',
                                ['jinja_filters.jinja_sequence'])
        self.assertIn('module_|-test_|-test.echo_|-run', ret)
        self.assertEqual(ret['module_|-test_|-test.echo_|-run']['changes'],
                         _expected)

    def test_jinja_skip(self):
        '''
        test jinja filter jinja.skip
        '''
        _expected = {u'ret': None}
        ret = self.run_function('state.sls',
                                ['jinja_filters.jinja_skip'])
        self.assertIn('module_|-test_|-test.echo_|-run', ret)
        self.assertEqual(ret['module_|-test_|-test.echo_|-run']['changes'],
                         _expected)

    def test_jinja_symmetric_difference(self):
        '''
        test jinja filter jinja.symmetric_difference
        '''
        _expected = {u'ret': [1, 3, 6]}
        ret = self.run_function('state.sls',
                                ['jinja_filters.jinja_symmetric_difference'])
        self.assertIn('module_|-test_|-test.echo_|-run', ret)
        self.assertEqual(ret['module_|-test_|-test.echo_|-run']['changes'],
                         _expected)

    def test_jinja_to_bool(self):
        '''
        test jinja filter jinja.to_bool
        '''
        _expected = {u'ret': True}
        ret = self.run_function('state.sls',
                                ['jinja_filters.jinja_to_bool'])
        self.assertIn('module_|-test_|-test.echo_|-run', ret)
        self.assertEqual(ret['module_|-test_|-test.echo_|-run']['changes'],
                         _expected)

    def test_jinja_union(self):
        '''
        test jinja filter jinja.union
        '''
        _expected = {u'ret': [1, 2, 3, 4, 6]}
        ret = self.run_function('state.sls',
                                ['jinja_filters.jinja_union'])
        self.assertIn('module_|-test_|-test.echo_|-run', ret)
        self.assertEqual(ret['module_|-test_|-test.echo_|-run']['changes'],
                         _expected)

    def test_jinja_unique(self):
        '''
        test jinja filter jinja.unique
        '''
        _expected = {u'ret': [u'a', u'b', u'c']}
        ret = self.run_function('state.sls',
                                ['jinja_filters.jinja_unique'])
        self.assertIn('module_|-test_|-test.echo_|-run', ret)
        self.assertEqual(ret['module_|-test_|-test.echo_|-run']['changes'],
                         _expected)

    def test_jinja_uuid(self):
        '''
        test jinja filter jinja.uuid
        '''
        _expected = {u'ret': '799192d9-7f32-5227-a45f-dfeb4a34e06f'}
        ret = self.run_function('state.sls',
                                ['jinja_filters.jinja_uuid'])
        self.assertIn('module_|-test_|-test.echo_|-run', ret)
        self.assertEqual(ret['module_|-test_|-test.echo_|-run']['changes'],
                         _expected)

    def test_network_gen_mac(self):
        '''
        test jinja filter network.gen_mac
        '''
        _expected = 'AC:DE:48:'
        ret = self.run_function('state.sls',
                                ['jinja_filters.network_gen_mac'])
        self.assertIn('module_|-test_|-test.echo_|-run', ret)
        self.assertTrue(ret['module_|-test_|-test.echo_|-run']['changes']['ret'].startswith(_expected))

    def test_network_ipaddr(self):
        '''
        test jinja filter network.ipaddr
        '''
        _expected = {u'ret': "[u'127.0.0.1', u'::1']"}
        ret = self.run_function('state.sls',
                                ['jinja_filters.network_ipaddr'])
        self.assertIn('module_|-test_|-test.echo_|-run', ret)
        self.assertEqual(ret['module_|-test_|-test.echo_|-run']['changes'],
                         _expected)

    def test_network_ip_host(self):
        '''
        test jinja filter network.ip_host
        '''
        _expected = {u'ret': '192.168.0.12/24'}
        ret = self.run_function('state.sls',
                                ['jinja_filters.network_ip_host'])
        self.assertIn('module_|-test_|-test.echo_|-run', ret)
        self.assertEqual(ret['module_|-test_|-test.echo_|-run']['changes'],
                         _expected)

    def test_network_ipv4(self):
        '''
        test jinja filter network.ipv4
        '''
        _expected = {u'ret': ['127.0.0.1']}
        ret = self.run_function('state.sls',
                                ['jinja_filters.network_ipv4'])
        self.assertIn('module_|-test_|-test.echo_|-run', ret)
        self.assertEqual(ret['module_|-test_|-test.echo_|-run']['changes'],
                         _expected)

    def test_network_ipv6(self):
        '''
        test jinja filter network.ipv6
        '''
        _expected = {u'ret': u"[u'::1']"}
        ret = self.run_function('state.sls',
                                ['jinja_filters.network_ipv6'])
        self.assertIn('module_|-test_|-test.echo_|-run', ret)
        self.assertEqual(ret['module_|-test_|-test.echo_|-run']['changes'],
                         _expected)

    def test_network_is_ip(self):
        '''
        test jinja filter network.is_ip
        '''
        _expected = {u'ret': True}
        ret = self.run_function('state.sls',
                                ['jinja_filters.network_is_ip'])
        self.assertIn('module_|-test_|-test.echo_|-run', ret)
        self.assertEqual(ret['module_|-test_|-test.echo_|-run']['changes'],
                         _expected)

    def test_network_is_ipv4(self):
        '''
        test jinja filter network.is_ipv4
        '''
        _expected = {u'ret': True}
        ret = self.run_function('state.sls',
                                ['jinja_filters.network_is_ipv4'])
        self.assertIn('module_|-test_|-test.echo_|-run', ret)
        self.assertEqual(ret['module_|-test_|-test.echo_|-run']['changes'],
                         _expected)

    def test_network_is_ipv6(self):
        '''
        test jinja filter network.is_ipv6
        '''
        _expected = {u'ret': True}
        ret = self.run_function('state.sls',
                                ['jinja_filters.network_is_ipv6'])
        self.assertIn('module_|-test_|-test.echo_|-run', ret)
        self.assertEqual(ret['module_|-test_|-test.echo_|-run']['changes'],
                         _expected)

    def test_network_network_hosts(self):
        '''
        test jinja filter network.network_hosts
        '''
        _expected = {u'ret': [u'192.168.1.1', u'192.168.1.2']}
        ret = self.run_function('state.sls',
                                ['jinja_filters.network_network_hosts'])
        self.assertIn('module_|-test_|-test.echo_|-run', ret)
        self.assertEqual(ret['module_|-test_|-test.echo_|-run']['changes'],
                         _expected)

    def test_network_network_size(self):
        '''
        test jinja filter network.network_size
        '''
        _expected = {u'ret': 16}
        ret = self.run_function('state.sls',
                                ['jinja_filters.network_network_size'])
        self.assertIn('module_|-test_|-test.echo_|-run', ret)
        self.assertEqual(ret['module_|-test_|-test.echo_|-run']['changes'],
                         _expected)

    def test_path_join(self):
        '''
        test jinja filter path.join
        '''
        _expected = {u'ret': '/a/b/c/d'}
        ret = self.run_function('state.sls',
                                ['jinja_filters.path_join'])
        self.assertIn('module_|-test_|-test.echo_|-run', ret)
        self.assertEqual(ret['module_|-test_|-test.echo_|-run']['changes'],
                         _expected)

    def test_path_which(self):
        '''
        test jinja filter path.which
        '''
        _expected = {u'ret': '/usr/bin/which'}
        ret = self.run_function('state.sls',
                                ['jinja_filters.path_which'])
        self.assertIn('module_|-test_|-test.echo_|-run', ret)
        self.assertEqual(ret['module_|-test_|-test.echo_|-run']['changes'],
                         _expected)

    def test_stringutils_contains_whitespace(self):
        '''
        test jinja filter stringutils.contains_whitespace
        '''
        _expected = {u'ret': True}
        ret = self.run_function('state.sls',
                                ['jinja_filters.stringutils_contains_whitespace'])
        self.assertIn('module_|-test_|-test.echo_|-run', ret)
        self.assertEqual(ret['module_|-test_|-test.echo_|-run']['changes'],
                         _expected)

    def test_stringutils_is_hex(self):
        '''
        test jinja filter stringutils.is_hex
        '''
        _expected = {u'ret': True}
        ret = self.run_function('state.sls',
                                ['jinja_filters.stringutils_is_hex'])
        self.assertIn('module_|-test_|-test.echo_|-run', ret)
        self.assertEqual(ret['module_|-test_|-test.echo_|-run']['changes'],
                         _expected)

    def test_stringutils_random_str(self):
        '''
        test jinja filter stringutils.random_str
        '''
        ret = self.run_function('state.sls',
                                ['jinja_filters.stringutils_random_str'])
        self.assertIn('module_|-test_|-test.echo_|-run', ret)
        self.assertIn('ret', ret['module_|-test_|-test.echo_|-run']['changes'])

    def test_stringutils_to_bytes(self):
        '''
        test jinja filter stringutils.to_bytes
        '''
        _expected = {u'ret': 'Salt Rocks!'}
        ret = self.run_function('state.sls',
                                ['jinja_filters.stringutils_to_bytes'])
        self.assertIn('module_|-test_|-test.echo_|-run', ret)
        self.assertEqual(ret['module_|-test_|-test.echo_|-run']['changes'],
                         _expected)

    def test_stringutils_to_num(self):
        '''
        test jinja filter stringutils.to_num
        '''
        _expected = {u'ret': 42}
        ret = self.run_function('state.sls',
                                ['jinja_filters.stringutils_to_num'])
        self.assertIn('module_|-test_|-test.echo_|-run', ret)
        self.assertEqual(ret['module_|-test_|-test.echo_|-run']['changes'],
                         _expected)

    def test_stringutils_whitelist_blacklist(self):
        '''
        test jinja filter stringutils.whitelist_blacklist
        '''
        _expected = {u'ret': True}
        ret = self.run_function('state.sls',
                                ['jinja_filters.stringutils_whitelist_blacklist'])
        self.assertIn('module_|-test_|-test.echo_|-run', ret)
        self.assertEqual(ret['module_|-test_|-test.echo_|-run']['changes'],
                         _expected)

    def test_user_get_uid(self):
        '''
        test jinja filter user.get_uid
        '''
        _expected = {u'ret': 0}
        ret = self.run_function('state.sls',
                                ['jinja_filters.user_get_uid'])
        self.assertIn('module_|-test_|-test.echo_|-run', ret)
        self.assertEqual(ret['module_|-test_|-test.echo_|-run']['changes'],
                         _expected)

    def test_yamlencoding_yaml_dquote(self):
        '''
        test jinja filter yamlencoding.yaml_dquote
        '''
        _expected = {u'ret': 'A double-quoted string in YAML'}
        ret = self.run_function('state.sls',
                                ['jinja_filters.yamlencoding_yaml_dquote'])
        self.assertIn('module_|-test_|-test.echo_|-run', ret)
        self.assertEqual(ret['module_|-test_|-test.echo_|-run']['changes'],
                         _expected)

    def test_yamlencoding_yaml_encode(self):
        '''
        test jinja filter yamlencoding.yaml_encode
        '''
        _expected = {u'ret': 'An encoded string in YAML'}
        ret = self.run_function('state.sls',
                                ['jinja_filters.yamlencoding_yaml_encode'])
        self.assertIn('module_|-test_|-test.echo_|-run', ret)
        self.assertEqual(ret['module_|-test_|-test.echo_|-run']['changes'],
                         _expected)

    def test_yamlencoding_yaml_squote(self):
        '''
        test jinja filter yamlencoding.yaml_squote
        '''
        _expected = {u'ret': 'A single-quoted string in YAML'}
        ret = self.run_function('state.sls',
                                ['jinja_filters.yamlencoding_yaml_squote'])
        self.assertIn('module_|-test_|-test.echo_|-run', ret)
        self.assertEqual(ret['module_|-test_|-test.echo_|-run']['changes'],
                         _expected)
