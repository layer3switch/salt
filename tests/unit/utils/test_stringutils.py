# -*- coding: utf-8 -*-

from __future__ import absolute_import, print_function, unicode_literals

# Import Salt libs
from tests.support.mock import patch
from tests.support.unit import TestCase, LOREM_IPSUM
import salt.utils.stringutils

# Import 3rd-party libs
from salt.ext import six
from salt.ext.six.moves import builtins, range  # pylint: disable=redefined-builtin

UNICODE = '中国語 (繁体)'
STR = BYTES = UNICODE.encode('utf-8')


class StringutilsTestCase(TestCase):
    def test_contains_whitespace(self):
        does_contain_whitespace = 'A brown fox jumped over the red hen.'
        does_not_contain_whitespace = 'Abrownfoxjumpedovertheredhen.'

        self.assertTrue(salt.utils.stringutils.contains_whitespace(does_contain_whitespace))
        self.assertFalse(salt.utils.stringutils.contains_whitespace(does_not_contain_whitespace))

    def test_to_num(self):
        self.assertEqual(7, salt.utils.stringutils.to_num('7'))
        self.assertIsInstance(salt.utils.stringutils.to_num('7'), int)
        self.assertEqual(7, salt.utils.stringutils.to_num('7.0'))
        self.assertIsInstance(salt.utils.stringutils.to_num('7.0'), float)
        self.assertEqual(salt.utils.stringutils.to_num('Seven'), 'Seven')
        self.assertIsInstance(salt.utils.stringutils.to_num('Seven'), six.text_type)

    def test_is_binary(self):
        self.assertFalse(salt.utils.stringutils.is_binary(LOREM_IPSUM))

        zero_str = '{0}{1}'.format(LOREM_IPSUM, '\0')
        self.assertTrue(salt.utils.stringutils.is_binary(zero_str))

        # To to ensure safe exit if str passed doesn't evaluate to True
        self.assertFalse(salt.utils.stringutils.is_binary(''))

        nontext = 3 * (''.join([chr(x) for x in range(1, 32) if x not in (8, 9, 10, 12, 13)]))
        almost_bin_str = '{0}{1}'.format(LOREM_IPSUM[:100], nontext[:42])
        self.assertFalse(salt.utils.stringutils.is_binary(almost_bin_str))

        bin_str = almost_bin_str + '\x01'
        self.assertTrue(salt.utils.stringutils.is_binary(bin_str))

    def test_to_str(self):
        for x in (123, (1, 2, 3), [1, 2, 3], {1: 23}, None):
            self.assertRaises(TypeError, salt.utils.stringutils.to_str, x)
        if six.PY3:
            self.assertEqual(salt.utils.stringutils.to_str('plugh'), 'plugh')
            self.assertEqual(salt.utils.stringutils.to_str('áéíóúý', 'utf-8'), 'áéíóúý')
            self.assertEqual(salt.utils.stringutils.to_str(BYTES, 'utf-8'), UNICODE)
            self.assertEqual(salt.utils.stringutils.to_str(bytearray(BYTES), 'utf-8'), UNICODE)
            # Test situation when a minion returns incorrect utf-8 string because of... million reasons
            ut2 = b'\x9c'
            self.assertRaises(UnicodeDecodeError, salt.utils.stringutils.to_str, ut2, 'utf-8')
            self.assertEqual(salt.utils.stringutils.to_str(ut2, 'utf-8', 'replace'), u'\ufffd')
            self.assertRaises(UnicodeDecodeError, salt.utils.stringutils.to_str, bytearray(ut2), 'utf-8')
            self.assertEqual(salt.utils.stringutils.to_str(bytearray(ut2), 'utf-8', 'replace'), u'\ufffd')
        else:
            self.assertEqual(salt.utils.stringutils.to_str('plugh'), str('plugh'))  # future lint: disable=blacklisted-function
            self.assertEqual(salt.utils.stringutils.to_str('áéíóúý', 'utf-8'), 'áéíóúý'.encode('utf-8'))
            self.assertEqual(salt.utils.stringutils.to_str(UNICODE, 'utf-8'), STR)
            self.assertEqual(salt.utils.stringutils.to_str(bytearray(STR), 'utf-8'), STR)

            # Test utf-8 fallback with Windows default codepage
            with patch.object(builtins, '__salt_system_encoding__', 'CP1252'):
                self.assertEqual(salt.utils.stringutils.to_str('Ψ'), 'Ψ'.encode('utf-8'))

    def test_to_bytes(self):
        for x in (123, (1, 2, 3), [1, 2, 3], {1: 23}, None):
            self.assertRaises(TypeError, salt.utils.stringutils.to_bytes, x)
        if six.PY3:
            self.assertEqual(salt.utils.stringutils.to_bytes('xyzzy'), b'xyzzy')
            self.assertEqual(salt.utils.stringutils.to_bytes(BYTES), BYTES)
            self.assertEqual(salt.utils.stringutils.to_bytes(bytearray(BYTES)), BYTES)
            self.assertEqual(salt.utils.stringutils.to_bytes(UNICODE, 'utf-8'), BYTES)

            # Test utf-8 fallback with ascii default encoding
            with patch.object(builtins, '__salt_system_encoding__', 'ascii'):
                self.assertEqual(salt.utils.stringutils.to_bytes('Ψ'), b'\xce\xa8')
        else:
            self.assertEqual(salt.utils.stringutils.to_bytes('xyzzy'), 'xyzzy')
            self.assertEqual(salt.utils.stringutils.to_bytes(BYTES), BYTES)
            self.assertEqual(salt.utils.stringutils.to_bytes(bytearray(BYTES)), BYTES)
            self.assertEqual(salt.utils.stringutils.to_bytes(UNICODE, 'utf-8'), BYTES)

    def test_to_unicode(self):
        if six.PY3:
            self.assertEqual(salt.utils.stringutils.to_unicode('plugh'), 'plugh')
            self.assertEqual(salt.utils.stringutils.to_unicode('áéíóúý'), 'áéíóúý')
            self.assertEqual(salt.utils.stringutils.to_unicode(BYTES, 'utf-8'), UNICODE)
            self.assertEqual(salt.utils.stringutils.to_unicode(bytearray(BYTES), 'utf-8'), UNICODE)
        else:
            self.assertEqual(salt.utils.stringutils.to_unicode(str('xyzzy'), 'utf-8'), 'xyzzy')  # future lint: disable=blacklisted-function
            self.assertEqual(salt.utils.stringutils.to_unicode(BYTES, 'utf-8'), UNICODE)

            # Test utf-8 fallback with ascii default encoding
            with patch.object(builtins, '__salt_system_encoding__', 'ascii'):
                self.assertEqual(salt.utils.stringutils.to_unicode(u'Ψ'.encode('utf-8')), u'Ψ')

    def test_build_whitespace_split_regex(self):
        expected_regex = '(?m)^(?:[\\s]+)?Lorem(?:[\\s]+)?ipsum(?:[\\s]+)?dolor(?:[\\s]+)?sit(?:[\\s]+)?amet\\,' \
                         '(?:[\\s]+)?$'
        ret = salt.utils.stringutils.build_whitespace_split_regex(' '.join(LOREM_IPSUM.split()[:5]))
        self.assertEqual(ret, expected_regex)
