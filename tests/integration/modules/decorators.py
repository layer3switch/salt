# -*- coding: utf-8 -*-

# Import Python libs
from __future__ import absolute_import

# Import Salt Testing libs
from salttesting.helpers import ensure_in_syspath
ensure_in_syspath('../../')

# Import salt libs
import integration


class DecoratorTest(integration.ModuleCase):
    def test_module(self):
        self.assertTrue(
                self.run_function(
                    'runtests_decorators.working_function'
                    )
                )

    def test_depends(self):
        ret = self.run_function('runtests_decorators.depends')
        self.assertTrue(isinstance(ret, dict))
        self.assertTrue(ret['ret'])
        self.assertTrue(isinstance(ret['time'], float))

    def test_missing_depends(self):
        self.assertIn(
                'is not available',
                self.run_function('runtests_decorators.missing_depends'
                    )
                )

    def test_bool_depends(self):
        # test True
        self.assertTrue(
                self.run_function(
                    'runtests_decorators.booldependsTrue'
                    )
                )

        # test False
        self.assertIn(
                'is not available',
                self.run_function('runtests_decorators.booldependsFalse'
                    )
                )

    def test_depends_will_not_fallback(self):
        ret = self.run_function('runtests_decorators.depends_will_not_fallback')
        self.assertTrue(isinstance(ret, dict))
        self.assertTrue(ret['ret'])
        self.assertTrue(isinstance(ret['time'], float))

    def test_missing_depends_will_fallback(self):
        self.assertListEqual(
                [False, 'fallback'],
                self.run_function(
                    'runtests_decorators.missing_depends_will_fallback'
                    )
                )


if __name__ == '__main__':
    from integration import run_tests
    run_tests(DecoratorTest)
