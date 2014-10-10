# -*- coding: utf-8 -*-
'''
Tests of utilities that support multiple masters in Salt Raet

'''
# pylint: skip-file
# pylint: disable=C0103
import sys
if sys.version_info < (2, 7):
    import unittest2 as unittest
else:
    import unittest

import os
import stat
import time
import tempfile
import shutil

from ioflo.base.odicting import odict
from ioflo.base.aiding import Timer, StoreTimer
from ioflo.base import storing
from ioflo.base.consoling import getConsole
console = getConsole()

from raet import raeting

from salt.daemons import parseHostname,  extractMasters


def setUpModule():
    console.reinit(verbosity=console.Wordage.concise)

def tearDownModule():
    pass

class BasicTestCase(unittest.TestCase):
    """"""

    def setUp(self):
        self.store = storing.Store(stamp=0.0)
        self.timer = StoreTimer(store=self.store, duration=1.0)
        self.port = 4506
        self.opts = dict(master_port=self.port)

    def tearDown(self):
        pass



    def testParseHostname(self):
        '''
        Test parsing hostname provided according to syntax for opts['master']
        '''
        console.terse("{0}\n".format(self.testParseHostname.__doc__))

        self.assertEquals(parseHostname('localhost', self.port),
                                       ('localhost', 4506))
        self.assertEquals(parseHostname('127.0.0.1', self.port),
                                       ('127.0.0.1', 4506))
        self.assertEquals(parseHostname('10.0.2.100', self.port),
                                        ('10.0.2.100', 4506))
        self.assertEquals(parseHostname('me.example.com', self.port),
                                        ('me.example.com', 4506))
        self.assertEquals(parseHostname(
               '1.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.ip6.arpa',
                self.port),
                ('1.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.ip6.arpa',
                 4506))
        self.assertEquals(parseHostname('fe80::1%lo0', self.port),
                                                ('fe80::1%lo0', 4506))

        self.assertEquals(parseHostname('  localhost   ', self.port),
                                               ('localhost', 4506))
        self.assertEquals(parseHostname('  127.0.0.1   ', self.port),
                                       ('127.0.0.1', 4506))
        self.assertEquals(parseHostname('   10.0.2.100   ', self.port),
                                        ('10.0.2.100', 4506))
        self.assertEquals(parseHostname('  me.example.com  ', self.port),
                                        ('me.example.com', 4506))
        self.assertEquals(parseHostname(
               '  1.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.ip6.arpa   ',
                self.port),
                ('1.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.ip6.arpa',
                 4506))
        self.assertEquals(parseHostname('  fe80::1%lo0  ', self.port),
                                                ('fe80::1%lo0', 4506))


        self.assertEquals(parseHostname('localhost 4510', self.port),
                                               ('localhost', 4510))
        self.assertEquals(parseHostname('127.0.0.1 4510', self.port),
                                       ('127.0.0.1', 4510))
        self.assertEquals(parseHostname('10.0.2.100 4510', self.port),
                                        ('10.0.2.100', 4510))
        self.assertEquals(parseHostname('me.example.com 4510', self.port),
                                        ('me.example.com', 4510))
        self.assertEquals(parseHostname(
               '1.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.ip6.arpa 4510',
                self.port),
                ('1.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.ip6.arpa',
                 4510))
        self.assertEquals(parseHostname('fe80::1%lo0 4510', self.port),
                                                ('fe80::1%lo0', 4510))


        self.assertEquals(parseHostname('  localhost     4510 ', self.port),
                                               ('localhost', 4510))
        self.assertEquals(parseHostname('   127.0.0.1    4510   ', self.port),
                                       ('127.0.0.1', 4510))
        self.assertEquals(parseHostname('   10.0.2.100   4510   ', self.port),
                                        ('10.0.2.100', 4510))
        self.assertEquals(parseHostname('   me.example.com    4510   ', self.port),
                                        ('me.example.com', 4510))
        self.assertEquals(parseHostname(
               '   1.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.ip6.arpa   4510   ',
                self.port),
                ('1.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.ip6.arpa',
                 4510))
        self.assertEquals(parseHostname('   fe80::1%lo0   4510   ', self.port),
                                                ('fe80::1%lo0', 4510))


        self.assertEquals(parseHostname('localhost abcde', self.port), None)
        self.assertEquals(parseHostname('127.0.0.1 a4510', self.port), None)
        self.assertEquals(parseHostname(list([1, 2, 3]), self.port), None)
        self.assertEquals(parseHostname(list(), self.port), None)
        self.assertEquals(parseHostname(dict(a=1), self.port), None)
        self.assertEquals(parseHostname(dict(), self.port), None)
        self.assertEquals(parseHostname(4510, self.port), None)
        self.assertEquals(parseHostname(('localhost', 4510), self.port), None)

        self.assertEquals(parseHostname('localhost:4510', self.port),
                                               ('localhost', 4510))
        self.assertEquals(parseHostname('127.0.0.1:4510', self.port),
                                       ('127.0.0.1', 4510))
        self.assertEquals(parseHostname('10.0.2.100:4510', self.port),
                                        ('10.0.2.100', 4510))
        self.assertEquals(parseHostname('me.example.com:4510', self.port),
                                        ('me.example.com', 4510))
        self.assertEquals(parseHostname(
               '1.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.ip6.arpa:4510',
                self.port),
                ('1.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.ip6.arpa',
                 4510))
        self.assertEquals(parseHostname('fe80::1%lo0:4510', self.port),
                                                      ('fe80::1%lo0:4510', 4506))
        self.assertEquals(parseHostname('localhost::4510', self.port),
                                                       ('localhost::4510', 4506))


    def testExtractMasters(self):
        '''
        Test extracting from master provided according to syntax for opts['master']
        '''
        console.terse("{0}\n".format(self.testExtractMasters.__doc__))

        master = 'localhost'
        self.opts.update(master=master)
        self.assertEquals(extractMasters(self.opts),
                          [
                              dict(external=('localhost', 4506),
                                   internal=None),
                          ])

        master = '127.0.0.1'
        self.opts.update(master=master)
        self.assertEquals(extractMasters(self.opts),
                          [
                              dict(external=('127.0.0.1', 4506),
                                   internal=None),
                          ])

        master = 'localhost 4510'
        self.opts.update(master=master)
        self.assertEquals(extractMasters(self.opts),
                          [
                              dict(external=('localhost', 4510),
                                   internal=None),
                          ])

        master = '127.0.0.1 4510'
        self.opts.update(master=master)
        self.assertEquals(extractMasters(self.opts),
                          [
                              dict(external=('127.0.0.1', 4510),
                                   internal=None),
                          ])


        master = '10.0.2.23'
        self.opts.update(master=master)
        self.assertEquals(extractMasters(self.opts),
                          [
                              dict(external=('10.0.2.23', 4506),
                                   internal=None),
                          ])

        master = 'me.example.com'
        self.opts.update(master=master)
        self.assertEquals(extractMasters(self.opts),
                                  [
                                      dict(external=('me.example.com', 4506),
                                           internal=None),
                                  ])

        master = '10.0.2.23 4510'
        self.opts.update(master=master)
        self.assertEquals(extractMasters(self.opts),
                                  [
                                      dict(external=('10.0.2.23', 4510),
                                           internal=None),
                                  ])

        master = 'me.example.com 4510'
        self.opts.update(master=master)
        self.assertEquals(extractMasters(self.opts),
                                  [
                                      dict(external=('me.example.com', 4510),
                                           internal=None),
                                  ])

        master = dict(external='10.0.2.23 4510')
        self.opts.update(master=master)
        self.assertEquals(extractMasters(self.opts),
                                  [
                                      dict(external=('10.0.2.23', 4510),
                                           internal=None),
                                  ])

        master = dict(external='10.0.2.23 4510', internal='')
        self.opts.update(master=master)
        self.assertEquals(extractMasters(self.opts),
                                  [
                                      dict(external=('10.0.2.23', 4510),
                                           internal=None),
                                  ])

        master = dict(internal='10.0.2.23 4510')
        self.opts.update(master=master)
        self.assertEquals(extractMasters(self.opts),[])






def runOne(test):
    '''
    Unittest Runner
    '''
    test = BasicTestCase(test)
    suite = unittest.TestSuite([test])
    unittest.TextTestRunner(verbosity=2).run(suite)

def runSome():
    '''
    Unittest runner
    '''
    tests =  []
    names = [
                'testParseHostname',
                'testExtractMasters',
            ]

    tests.extend(map(BasicTestCase, names))

    suite = unittest.TestSuite(tests)
    unittest.TextTestRunner(verbosity=2).run(suite)

def runAll():
    '''
    Unittest runner
    '''
    suite = unittest.TestSuite()
    suite.addTest(unittest.TestLoader().loadTestsFromTestCase(BasicTestCase))

    unittest.TextTestRunner(verbosity=2).run(suite)

if __name__ == '__main__' and __package__ is None:

    #console.reinit(verbosity=console.Wordage.concise)

    #runAll() #run all unittests

    runSome()#only run some

    #runOne('testParseHostname')
