# -*- coding: utf-8 -*-
'''
Support for IFTTT

.. versionadded:: Beryllium

Requires an ``api_key`` in ``/etc/salt/minion``:

.. code-block: yaml

    ifttt:
      secret_key: '280d4699-a817-4719-ba6f-ca56e573e44f'
'''

# Import python libs
from __future__ import absolute_import, print_function
import json
import logging

# Import 3rd-party libs
# pylint: disable=import-error,no-name-in-module,redefined-builtin
from salt.ext.six.moves.urllib.parse import urlencode as _urlencode
import salt.ext.six.moves.http_client
# pylint: enable=import-error,no-name-in-module

# Import salt libs
import salt.utils.http

log = logging.getLogger(__name__)


def __virtual__():
    '''
    Only load the module if apache is installed
    '''
    if not __salt__['config.get']('ifttt.secret_key') and \
       not __salt__['config.get']('ifttt:secret_key'):
            log.error('IFTTT Secret Key Unavailable, not loading.')
            return False
    return True


def _query(event=None,
           method='GET',
           args=None,
           header_dict=None,
           data=None):
    '''
    Make a web call to IFTTT

    .. versionadded:: Beryllium
    '''
    secret_key = __salt__['config.get']('ifttt.secret_key') or \
        __salt__['config.get']('ifttt:secret_key')
    path = 'https://maker.ifttt.com/trigger/{0}/with/key/{1}'.format(event, secret_key)

    if header_dict is None:
        header_dict = {'Content-type': 'application/json'}

    if method != 'POST':
        header_dict['Accept'] = 'application/json'

    result = salt.utils.http.query(
        path,
        method,
        params={},
        data=data,
        header_dict=header_dict,
        decode=True,
        decode_type='auto',
        text=True,
        status=True,
        cookies=True,
        persist_session=True,
        opts=__opts__,
        backend='requests'
    )
    return result


def trigger_event(event=None, **kwargs):
    '''
    Trigger a configured event in IFTTT.

    :param event:   The name of the event to trigger.

    :return:        A dictionary with status, text, and error if result was failure.

    CLI Example:

    .. code-block:: yaml

    '''

    res = {'result': False, 'message': 'Something went wrong'}

    data = {}
    for kwarg in kwargs:
        if kwarg.startswith('__'):
            continue
        data[kwarg.lower()] = kwargs[kwarg]
    foo = json.dumps(data)
    log.debug('foo {0}'.format(foo))
    result = _query(event=event,
                    method='POST',
                    data=foo
                    )
    if 'status' in result:
        if result['status'] == 200:
            res['result'] = True
            res['message'] = result['text']
        else:
            if 'error' in result:
                res['message'] = result['error']
    return res
