# -*- coding: utf-8 -*-

# Import Python Libs
import json
import time

# Import Salt Libs
from salt.netapi.rest_tornado import saltnado
from unit.netapi.rest_tornado.test_handlers import SaltnadoTestCase

# Import Salt Testing Libs
from salttesting import skipIf
from salttesting.helpers import ensure_in_syspath

ensure_in_syspath('../../../')

try:
    import tornado
    HAS_TORNADO = True
except ImportError:
    HAS_TORNADO = False

try:
    from zmq.eventloop.ioloop import ZMQIOLoop
    HAS_ZMQ_IOLOOP = True
except ImportError:
    HAS_ZMQ_IOLOOP = False


@skipIf(HAS_TORNADO is False, 'Tornado must be installed to run these tests')
@skipIf(HAS_ZMQ_IOLOOP is False, 'PyZMQ version must be >= 14.0.1 to run these tests.')
class TestSaltAPIHandler(SaltnadoTestCase):
    def get_app(self):
        application = tornado.web.Application([('/', saltnado.SaltAPIHandler)], debug=True)

        application.auth = self.auth
        application.opts = self.opts

        application.event_listener = saltnado.EventListener({}, self.opts)
        return application

    def test_root(self):
        '''
        Test the root path which returns the list of clients we support
        '''
        response = self.fetch('/')
        self.assertEqual(response.code, 200)
        response_obj = json.loads(response.body)
        self.assertEqual(response_obj['clients'],
                         ['runner',
                          'local_async',
                          'local',
                          'local_batch']
                         )
        self.assertEqual(response_obj['return'], 'Welcome')

    def test_post_no_auth(self):
        '''
        Test post with no auth token, should 401
        '''
        # get a token for this test
        low = [{'client': 'local',
                'tgt': '*',
                'fun': 'test.ping',
                }]
        response = self.fetch('/',
                              method='POST',
                              body=json.dumps(low),
                              headers={'Content-Type': self.content_type_map['json']},
                              follow_redirects=False
                              )
        self.assertEqual(response.code, 302)
        self.assertEqual(response.headers['Location'], '/login')

    # Local client tests
    def test_simple_local_post(self):
        '''
        Test a basic API of /
        '''
        low = [{'client': 'local',
                'tgt': '*',
                'fun': 'test.ping',
                }]
        response = self.fetch('/',
                              method='POST',
                              body=json.dumps(low),
                              headers={'Content-Type': self.content_type_map['json'],
                                       saltnado.AUTH_TOKEN_HEADER: self.token['token']},
                              )
        response_obj = json.loads(response.body)
        self.assertEqual(response_obj['return'], [{'minion': True, 'sub_minion': True}])

    def test_simple_local_post_no_tgt(self):
        '''
        POST job with invalid tgt
        '''
        low = [{'client': 'local',
                'tgt': 'minion_we_dont_have',
                'fun': 'test.ping',
                }]
        response = self.fetch('/',
                              method='POST',
                              body=json.dumps(low),
                              headers={'Content-Type': self.content_type_map['json'],
                                       saltnado.AUTH_TOKEN_HEADER: self.token['token']},
                              )
        response_obj = json.loads(response.body)
        self.assertEqual(response_obj['return'], ["No minions matched the target. No command was sent, no jid was assigned."])

    # local_batch tests
    def test_simple_local_batch_post(self):
        '''
        Basic post against local_batch
        '''
        low = [{'client': 'local_batch',
                'tgt': '*',
                'fun': 'test.ping',
                }]
        response = self.fetch('/',
                              method='POST',
                              body=json.dumps(low),
                              headers={'Content-Type': self.content_type_map['json'],
                                       saltnado.AUTH_TOKEN_HEADER: self.token['token']},
                              )
        response_obj = json.loads(response.body)
        self.assertEqual(response_obj['return'], [{'minion': True, 'sub_minion': True}])

    # local_batch tests
    def test_full_local_batch_post(self):
        '''
        Test full parallelism of local_batch
        '''
        low = [{'client': 'local_batch',
                'tgt': '*',
                'fun': 'test.ping',
                'batch': '100%',
                }]
        response = self.fetch('/',
                              method='POST',
                              body=json.dumps(low),
                              headers={'Content-Type': self.content_type_map['json'],
                                       saltnado.AUTH_TOKEN_HEADER: self.token['token']},
                              )
        response_obj = json.loads(response.body)
        self.assertEqual(response_obj['return'], [{'minion': True, 'sub_minion': True}])

    def test_simple_local_batch_post_no_tgt(self):
        '''
        Local_batch testing with no tgt
        '''
        low = [{'client': 'local_batch',
                'tgt': 'minion_we_dont_have',
                'fun': 'test.ping',
                }]
        response = self.fetch('/',
                              method='POST',
                              body=json.dumps(low),
                              headers={'Content-Type': self.content_type_map['json'],
                                       saltnado.AUTH_TOKEN_HEADER: self.token['token']},
                              )
        response_obj = json.loads(response.body)
        self.assertEqual(response_obj['return'], [{}])

    # local_async tests
    def test_simple_local_async_post(self):
        low = [{'client': 'local_async',
                'tgt': '*',
                'fun': 'test.ping',
                }]
        response = self.fetch('/',
                              method='POST',
                              body=json.dumps(low),
                              headers={'Content-Type': self.content_type_map['json'],
                                       saltnado.AUTH_TOKEN_HEADER: self.token['token']},
                              )
        response_obj = json.loads(response.body)
        # TODO: verify pub function? Maybe look at how we test the publisher
        self.assertEqual(len(response_obj['return']), 1)
        self.assertIn('jid', response_obj['return'][0])
        self.assertEqual(response_obj['return'][0]['minions'], ['minion', 'sub_minion'])

    def test_multi_local_async_post(self):
        low = [{'client': 'local_async',
                'tgt': '*',
                'fun': 'test.ping',
                },
                {'client': 'local_async',
                'tgt': '*',
                'fun': 'test.ping',
                }]
        response = self.fetch('/',
                              method='POST',
                              body=json.dumps(low),
                              headers={'Content-Type': self.content_type_map['json'],
                                       saltnado.AUTH_TOKEN_HEADER: self.token['token']},
                              )
        response_obj = json.loads(response.body)
        self.assertEqual(len(response_obj['return']), 2)
        self.assertIn('jid', response_obj['return'][0])
        self.assertIn('jid', response_obj['return'][1])
        self.assertEqual(response_obj['return'][0]['minions'], ['minion', 'sub_minion'])
        self.assertEqual(response_obj['return'][1]['minions'], ['minion', 'sub_minion'])

    def test_multi_local_async_post_multitoken(self):
        low = [{'client': 'local_async',
                'tgt': '*',
                'fun': 'test.ping',
                },
                {'client': 'local_async',
                'tgt': '*',
                'fun': 'test.ping',
                'token': self.token['token'],  # send a different (but still valid token)
                },
                {'client': 'local_async',
                'tgt': '*',
                'fun': 'test.ping',
                'token': 'BAD_TOKEN',  # send a bad token
                },
                ]
        response = self.fetch('/',
                              method='POST',
                              body=json.dumps(low),
                              headers={'Content-Type': self.content_type_map['json'],
                                       saltnado.AUTH_TOKEN_HEADER: self.token['token']},
                              )
        response_obj = json.loads(response.body)
        self.assertEqual(len(response_obj['return']), 3)  # make sure we got 3 responses
        self.assertIn('jid', response_obj['return'][0])  # the first 2 are regular returns
        self.assertIn('jid', response_obj['return'][1])
        self.assertIn('Failed to authenticate', response_obj['return'][2])  # bad auth
        self.assertEqual(response_obj['return'][0]['minions'], ['minion', 'sub_minion'])
        self.assertEqual(response_obj['return'][1]['minions'], ['minion', 'sub_minion'])

    def test_simple_local_async_post_no_tgt(self):
        low = [{'client': 'local_async',
                'tgt': 'minion_we_dont_have',
                'fun': 'test.ping',
                }]
        response = self.fetch('/',
                              method='POST',
                              body=json.dumps(low),
                              headers={'Content-Type': self.content_type_map['json'],
                                       saltnado.AUTH_TOKEN_HEADER: self.token['token']},
                              )
        response_obj = json.loads(response.body)
        self.assertEqual(response_obj['return'], [{}])

    # runner tests
    def test_simple_local_runner_post(self):
        low = [{'client': 'runner',
                'fun': 'manage.up',
                }]
        response = self.fetch('/',
                              method='POST',
                              body=json.dumps(low),
                              headers={'Content-Type': self.content_type_map['json'],
                                       saltnado.AUTH_TOKEN_HEADER: self.token['token']},
                              )
        response_obj = json.loads(response.body)
        self.assertEqual(response_obj['return'], [['minion', 'sub_minion']])


@skipIf(HAS_TORNADO is False, 'Tornado must be installed to run these tests')
@skipIf(HAS_ZMQ_IOLOOP is False, 'PyZMQ version must be >= 14.0.1 to run these tests.')
class TestMinionSaltAPIHandler(SaltnadoTestCase):
    def get_app(self):
        application = tornado.web.Application([(r"/minions/(.*)", saltnado.MinionSaltAPIHandler),
                                               (r"/minions", saltnado.MinionSaltAPIHandler),
                                               ], debug=True)

        application.auth = self.auth
        application.opts = self.opts

        application.event_listener = saltnado.EventListener({}, self.opts)
        return application

    def test_get_no_mid(self):
        response = self.fetch('/minions',
                              method='GET',
                              headers={saltnado.AUTH_TOKEN_HEADER: self.token['token']},
                              follow_redirects=False,
                              )
        response_obj = json.loads(response.body)
        self.assertEqual(len(response_obj['return']), 1)
        # one per minion
        self.assertEqual(len(response_obj['return'][0]), 2)
        # check a single grain
        for minion_id, grains in response_obj['return'][0].iteritems():
            self.assertEqual(minion_id, grains['id'])

    def test_get(self):
        response = self.fetch('/minions/minion',
                              method='GET',
                              headers={saltnado.AUTH_TOKEN_HEADER: self.token['token']},
                              follow_redirects=False,
                              )
        response_obj = json.loads(response.body)
        self.assertEqual(len(response_obj['return']), 1)
        self.assertEqual(len(response_obj['return'][0]), 1)
        # check a single grain
        self.assertEqual(response_obj['return'][0]['minion']['id'], 'minion')

    def test_post(self):
        low = [{'tgt': '*',
                'fun': 'test.ping',
                }]
        response = self.fetch('/minions',
                              method='POST',
                              body=json.dumps(low),
                              headers={'Content-Type': self.content_type_map['json'],
                                       saltnado.AUTH_TOKEN_HEADER: self.token['token']},
                              )
        response_obj = json.loads(response.body)
        # TODO: verify pub function? Maybe look at how we test the publisher
        self.assertEqual(len(response_obj['return']), 1)
        self.assertIn('jid', response_obj['return'][0])
        self.assertEqual(response_obj['return'][0]['minions'], ['minion', 'sub_minion'])

    def test_post_with_client(self):
        # get a token for this test
        low = [{'client': 'local_async',
                'tgt': '*',
                'fun': 'test.ping',
                }]
        response = self.fetch('/minions',
                              method='POST',
                              body=json.dumps(low),
                              headers={'Content-Type': self.content_type_map['json'],
                                       saltnado.AUTH_TOKEN_HEADER: self.token['token']},
                              )
        response_obj = json.loads(response.body)
        # TODO: verify pub function? Maybe look at how we test the publisher
        self.assertEqual(len(response_obj['return']), 1)
        self.assertIn('jid', response_obj['return'][0])
        self.assertEqual(response_obj['return'][0]['minions'], ['minion', 'sub_minion'])

    def test_post_with_incorrect_client(self):
        '''
        The /minions endpoint is async only, so if you try something else
        make sure you get an error
        '''
        # get a token for this test
        low = [{'client': 'local_batch',
                'tgt': '*',
                'fun': 'test.ping',
                }]
        response = self.fetch('/minions',
                              method='POST',
                              body=json.dumps(low),
                              headers={'Content-Type': self.content_type_map['json'],
                                       saltnado.AUTH_TOKEN_HEADER: self.token['token']},
                              )
        self.assertEqual(response.code, 400)


@skipIf(HAS_TORNADO is False, 'Tornado must be installed to run these tests')
@skipIf(HAS_ZMQ_IOLOOP is False, 'PyZMQ version must be >= 14.0.1 to run these tests.')
class TestJobsSaltAPIHandler(SaltnadoTestCase):
    def get_app(self):
        application = tornado.web.Application([(r"/jobs/(.*)", saltnado.JobsSaltAPIHandler),
                                               (r"/jobs", saltnado.JobsSaltAPIHandler),
                                               ], debug=True)

        application.auth = self.auth
        application.opts = self.opts

        application.event_listener = saltnado.EventListener({}, self.opts)
        return application

    def test_get(self):
        # test with no JID
        self.http_client.fetch(self.get_url('/jobs'),
                               self.stop,
                               method='GET',
                               headers={saltnado.AUTH_TOKEN_HEADER: self.token['token']},
                               follow_redirects=False,
                               request_timeout=10,  # wait up to 10s for this response-- jenkins seems to be slow
                               )
        response = self.wait(timeout=10)
        response_obj = json.loads(response.body)['return'][0]
        for jid, ret in response_obj.iteritems():
            self.assertIn('Function', ret)
            self.assertIn('Target', ret)
            self.assertIn('Target-type', ret)
            self.assertIn('User', ret)
            self.assertIn('StartTime', ret)
            self.assertIn('Arguments', ret)

        # test with a specific JID passed in
        jid = response_obj.iterkeys().next()
        self.http_client.fetch(self.get_url('/jobs/{0}'.format(jid)),
                               self.stop,
                               method='GET',
                               headers={saltnado.AUTH_TOKEN_HEADER: self.token['token']},
                               follow_redirects=False,
                               request_timeout=10,  # wait up to 10s for this response-- jenkins seems to be slow
                               )
        response = self.wait(timeout=10)
        response_obj = json.loads(response.body)['return'][0]
        self.assertIn('Function', response_obj)
        self.assertIn('Target', response_obj)
        self.assertIn('Target-type', response_obj)
        self.assertIn('User', response_obj)
        self.assertIn('StartTime', response_obj)
        self.assertIn('Arguments', response_obj)
        self.assertIn('Result', response_obj)


# TODO: run all the same tests from the root handler, but for now since they are
# the same code, we'll just sanity check
@skipIf(HAS_TORNADO is False, 'Tornado must be installed to run these tests')
@skipIf(HAS_ZMQ_IOLOOP is False, 'PyZMQ version must be >= 14.0.1 to run these tests.')
class TestRunSaltAPIHandler(SaltnadoTestCase):
    def get_app(self):
        application = tornado.web.Application([("/run", saltnado.RunSaltAPIHandler),
                                               ], debug=True)

        application.auth = self.auth
        application.opts = self.opts

        application.event_listener = saltnado.EventListener({}, self.opts)
        return application

    def test_get(self):
        low = [{'client': 'local',
                'tgt': '*',
                'fun': 'test.ping',
                }]
        response = self.fetch('/run',
                              method='POST',
                              body=json.dumps(low),
                              headers={'Content-Type': self.content_type_map['json'],
                                       saltnado.AUTH_TOKEN_HEADER: self.token['token']},
                              )
        response_obj = json.loads(response.body)
        self.assertEqual(response_obj['return'], [{'minion': True, 'sub_minion': True}])


@skipIf(HAS_TORNADO is False, 'Tornado must be installed to run these tests')
@skipIf(HAS_ZMQ_IOLOOP is False, 'PyZMQ version must be >= 14.0.1 to run these tests.')
class TestEventsSaltAPIHandler(SaltnadoTestCase):
    def get_app(self):
        application = tornado.web.Application([(r"/events", saltnado.EventsSaltAPIHandler),
                                               ], debug=True)

        application.auth = self.auth
        application.opts = self.opts

        application.event_listener = saltnado.EventListener({}, self.opts)
        # store a reference, for magic later!
        self.application = application
        self.events_to_fire = 0
        return application

    def test_get(self):
        self.events_to_fire = 5
        response = self.fetch('/events',
                              headers={saltnado.AUTH_TOKEN_HEADER: self.token['token']},
                              streaming_callback=self.on_event
                              )

    def _stop(self):
        self.stop()

    def on_event(self, event):
        if self.events_to_fire > 0:
            self.application.event_listener.event.fire_event({
                'foo': 'bar',
                'baz': 'qux',
            }, 'salt/netapi/test')
            self.events_to_fire -= 1
        # once we've fired all the events, lets call it a day
        else:
            # wait so that we can ensure that the next future is ready to go
            # to make sure we don't explode if the next one is ready
            ZMQIOLoop.current().add_timeout(time.time() + 0.5, self._stop)

        event = event.strip()
        # if we got a retry, just continue
        if event != 'retry: 400':
            tag, data = event.splitlines()
            self.assertTrue(tag.startswith('tag: '))
            self.assertTrue(data.startswith('data: '))


@skipIf(HAS_TORNADO is False, 'Tornado must be installed to run these tests')
@skipIf(HAS_ZMQ_IOLOOP is False, 'PyZMQ version must be >= 14.0.1 to run these tests.')
class TestWebhookSaltAPIHandler(SaltnadoTestCase):
    def get_app(self):
        application = tornado.web.Application([(r"/hook(/.*)?", saltnado.WebhookSaltAPIHandler),
                                               ], debug=True)

        application.auth = self.auth
        application.opts = self.opts

        self.application = application

        application.event_listener = saltnado.EventListener({}, self.opts)
        return application

    def test_post(self):
        def verify_event(event):
            '''
            Verify that the event fired on the master matches what we sent
            '''
            self.assertEqual(event['tag'], 'salt/netapi/hook')
            self.assertIn('headers', event['data'])
            self.assertEqual(event['data']['post'], {'foo': 'bar'})
        # get an event future
        event = self.application.event_listener.get_event(self,
                                                          tag='salt/netapi/hook',
                                                          callback=verify_event,
                                                          )
        # fire the event
        response = self.fetch('/hook',
                              method='POST',
                              body='foo=bar',
                              headers={saltnado.AUTH_TOKEN_HEADER: self.token['token']},
                              )
        response_obj = json.loads(response.body)
        self.assertTrue(response_obj['success'])
