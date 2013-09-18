'''
Test the salt mine system
'''
# Import Salt Testing libs
from salttesting.helpers import ensure_in_syspath
ensure_in_syspath('../../')

# Import salt libs
import integration


class MineTest(integration.ModuleCase):
    '''
    Test the mine system
    '''
    def test_get(self):
        '''
        test mine.get and mine.update
        '''
        self.assertTrue(self.run_function('mine.update', minion_tgt='minion'))
        self.assertTrue(
                self.run_function(
                    'mine.update',
                    minion_tgt='sub_minion'
                    )
                )
        self.assertTrue(
                self.run_function(
                    'mine.get',
                    ['minion', 'test.ping']
                    )
                )

    def test_send(self):
        '''
        test mine.send
        '''
        self.assertFalse(
                self.run_function(
                    'mine.send',
                    ['foo.__spam_and_cheese']
                    )
                )
        self.assertTrue(
                self.run_function(
                    'mine.send',
                    ['grains.items'],
                    minion_tgt='minion',
                    )
                )
        self.assertTrue(
                self.run_function(
                    'mine.send',
                    ['grains.items'],
                    minion_tgt='sub_minion',
                    )
                )
        ret = self.run_function(
                    'mine.get',
                    ['sub_minion', 'grains.items']
                    )
        self.assertEqual(ret['sub_minion']['id'], 'sub_minion')
        ret = self.run_function(
                    'mine.get',
                    ['minion', 'grains.items'],
                    minion_tgt='sub_minion'
                    )
        self.assertEqual(ret['minion']['id'], 'minion')

    def test_mine_flush(self):
        '''
        Test mine.flush
        '''
        for minion_id in ('minion', 'sub_minion'):
            self.assertTrue(
                self.run_function(
                    'mine.send',
                    ['grains.items'],
                    minion_tgt=minion_id
                )
            )
            ret = self.run_function(
                'mine.get',
                [minion_id, 'grains.items'],
                minion_tgt=minion_id
            )
            self.assertEqual(ret[minion_id]['id'], minion_id)
        self.assertTrue(
            self.run_function(
                'mine.flush',
                minion_tgt='minion'
            )
        )
        ret_flushed = self.run_function(
            'mine.get',
            ['*', 'grains.items']
        )
        self.assertEqual(ret_flushed.get('minion', None), None)
        self.assertEqual(ret_flushed['sub_minion']['id'], 'sub_minion')

if __name__ == '__main__':
    from integration import run_tests
    run_tests(MineTest)
