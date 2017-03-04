# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Pedro Algarvio (pedro@algarvio.me)`


    ============================
    Unittest Compatibility Layer
    ============================

    Compatibility layer to use :mod:`unittest <python2:unittest>` under Python
    2.7 or `unittest2`_ under Python 2.6 without having to worry about which is
    in use.

    .. attention::

        Please refer to Python's :mod:`unittest <python2:unittest>`
        documentation as the ultimate source of information, this is just a
        compatibility layer.

    .. _`unittest2`: https://pypi.python.org/pypi/unittest2
'''
# pylint: disable=unused-import

# Import python libs
from __future__ import absolute_import
import sys
import logging
try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False

log = logging.getLogger(__name__)

# Set SHOW_PROC to True to show
# process details when running in verbose mode
# i.e. [CPU:15.1%|MEM:48.3%|Z:0]
SHOW_PROC = False

# support python < 2.7 via unittest2
if sys.version_info < (2, 7):
    try:
        # pylint: disable=import-error
        from unittest2 import (
            TestLoader as _TestLoader,
            TextTestRunner as __TextTestRunner,
            TestCase as __TestCase,
            expectedFailure,
            TestSuite as _TestSuite,
            skip,
            skipIf,
            TestResult as _TestResult,
            TextTestResult as __TextTestResult
        )
        from unittest2.case import _id
        # pylint: enable=import-error

        class NewStyleClassMixin(object):
            '''
            Simple new style class to make pylint shut up!

            And also to avoid errors like:

                'Cannot create a consistent method resolution order (MRO) for bases'
            '''

        class TestLoader(_TestLoader, NewStyleClassMixin):
            pass

        class _TextTestRunner(__TextTestRunner, NewStyleClassMixin):
            pass

        class _TestCase(__TestCase, NewStyleClassMixin):
            pass

        class TestSuite(_TestSuite, NewStyleClassMixin):
            pass

        class TestResult(_TestResult, NewStyleClassMixin):
            pass

        class _TextTestResult(__TextTestResult, NewStyleClassMixin):
            pass

    except ImportError:
        raise SystemExit('You need to install unittest2 to run the salt tests')
else:
    from unittest import (
        TestLoader,
        TextTestRunner as _TextTestRunner,
        TestCase as _TestCase,
        expectedFailure,
        TestSuite,
        skip,
        skipIf,
        TestResult,
        TextTestResult as _TextTestResult
    )
    from unittest.case import _id


class TestCase(_TestCase):

    # pylint: disable=expected-an-indented-block-comment
##   Commented out because it may be causing tests to hang
##   at the end of the run
#
#    _cwd = os.getcwd()
#    _chdir_counter = 0

#    @classmethod
#    def tearDownClass(cls):
#        '''
#        Overriden method for tearing down all classes in salttesting
#
#        This hard-resets the environment between test classes
#        '''
#        # Compare where we are now compared to where we were when we began this family of tests
#        if not cls._cwd == os.getcwd() and cls._chdir_counter > 0:
#            os.chdir(cls._cwd)
#            print('\nWARNING: A misbehaving test has modified the working directory!\nThe test suite has reset the working directory '
#                    'on tearDown() to {0}\n'.format(cls._cwd))
#            cls._chdir_counter += 1
    # pylint: enable=expected-an-indented-block-comment

    def run(self, result=None):
        self._prerun_instance_attributes = dir(self)
        outcome = super(TestCase, self).run(result=result)
        for attr in dir(self):
            if attr == '_prerun_instance_attributes':
                continue
            if attr not in self._prerun_instance_attributes:
                log.warning('Deleting extra class attribute after test run: %s.%s(%s). '
                            'Please consider using \'del self.%s\' on the test case '
                            '\'tearDown()\' method', self.__class__.__name__, attr,
                            getattr(self, attr), attr)
                delattr(self, attr)
        del self._prerun_instance_attributes
        return outcome

    def shortDescription(self):
        desc = _TestCase.shortDescription(self)
        if HAS_PSUTIL and SHOW_PROC:
            proc_info = ''
            found_zombies = 0
            try:
                for proc in psutil.process_iter():
                    if proc.status == psutil.STATUS_ZOMBIE:
                        found_zombies += 1
                proc_info = '[CPU:{0}%|MEM:{1}%|Z:{2}] {short_desc}'.format(psutil.cpu_percent(),
                                                                            psutil.virtual_memory().percent,
                                                                            found_zombies,
                                                                            short_desc=desc if desc else '')
            except Exception:
                pass
            return proc_info
        else:
            return _TestCase.shortDescription(self)

    def assertEquals(self, *args, **kwargs):
        raise DeprecationWarning(
            'The {0}() function is deprecated. Please start using {1}() '
            'instead.'.format('assertEquals', 'assertEqual')
        )
        # return _TestCase.assertEquals(self, *args, **kwargs)

    def failUnlessEqual(self, *args, **kwargs):
        raise DeprecationWarning(
            'The {0}() function is deprecated. Please start using {1}() '
            'instead.'.format('failUnlessEqual', 'assertEqual')
        )
        # return _TestCase.failUnlessEqual(self, *args, **kwargs)

    def failIfEqual(self, *args, **kwargs):
        raise DeprecationWarning(
            'The {0}() function is deprecated. Please start using {1}() '
            'instead.'.format('failIfEqual', 'assertNotEqual')
        )
        # return _TestCase.failIfEqual(self, *args, **kwargs)

    def failUnless(self, *args, **kwargs):
        raise DeprecationWarning(
            'The {0}() function is deprecated. Please start using {1}() '
            'instead.'.format('failUnless', 'assertTrue')
        )
        # return _TestCase.failUnless(self, *args, **kwargs)

    def assert_(self, *args, **kwargs):
        # The unittest2 library uses this deprecated method, we can't raise
        # the exception.
        raise DeprecationWarning(
            'The {0}() function is deprecated. Please start using {1}() '
            'instead.'.format('assert_', 'assertTrue')
        )
        # return _TestCase.assert_(self, *args, **kwargs)

    def failIf(self, *args, **kwargs):
        raise DeprecationWarning(
            'The {0}() function is deprecated. Please start using {1}() '
            'instead.'.format('failIf', 'assertFalse')
        )
        # return _TestCase.failIf(self, *args, **kwargs)

    def failUnlessRaises(self, *args, **kwargs):
        raise DeprecationWarning(
            'The {0}() function is deprecated. Please start using {1}() '
            'instead.'.format('failUnlessRaises', 'assertRaises')
        )
        # return _TestCase.failUnlessRaises(self, *args, **kwargs)

    def failUnlessAlmostEqual(self, *args, **kwargs):
        raise DeprecationWarning(
            'The {0}() function is deprecated. Please start using {1}() '
            'instead.'.format('failUnlessAlmostEqual', 'assertAlmostEqual')
        )
        # return _TestCase.failUnlessAlmostEqual(self, *args, **kwargs)

    def failIfAlmostEqual(self, *args, **kwargs):
        raise DeprecationWarning(
            'The {0}() function is deprecated. Please start using {1}() '
            'instead.'.format('failIfAlmostEqual', 'assertNotAlmostEqual')
        )
        # return _TestCase.failIfAlmostEqual(self, *args, **kwargs)


class TextTestResult(_TextTestResult):
    '''
    Custom TestResult class whith logs the start and the end of a test
    '''

    def startTest(self, test):
        log.debug('>>>>> START >>>>> {0}'.format(test.id()))
        return super(TextTestResult, self).startTest(test)

    def stopTest(self, test):
        log.debug('<<<<< END <<<<<<< {0}'.format(test.id()))
        return super(TextTestResult, self).stopTest(test)


class TextTestRunner(_TextTestRunner):
    '''
    Custom Text tests runner to log the start and the end of a test case
    '''
    resultclass = TextTestResult


__all__ = [
    'TestLoader',
    'TextTestRunner',
    'TestCase',
    'expectedFailure',
    'TestSuite',
    'skipIf',
    'TestResult'
]
