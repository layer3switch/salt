# -*- coding: utf-8 -*-
'''
Generate marathon proxy minion grains.

.. versionadded:: 2015.8.2

'''
from __future__ import absolute_import, print_function, unicode_literals

import salt.utils.http
import salt.utils.platform
__proxyenabled__ = ['marathon']
__virtualname__ = 'marathon'


def __virtual__():
<<<<<<< HEAD
    if not salt.utils.platform.is_proxy() or 'proxy' not in __opts__:
        return False
    else:
        return __virtualname__
=======
    if salt.utils.platform.is_proxy() and 'proxy' in __opts__ and __opts__['proxy'].get('proxytype') == 'marathon':
        return __virtualname__
    return False
>>>>>>> upstream


def kernel():
    return {'kernel': 'marathon'}


def os():
    return {'os': 'marathon'}


def os_family():
    return {'os_family': 'marathon'}


def os_data():
    return {'os_data': 'marathon'}


def marathon():
    response = salt.utils.http.query(
        "{0}/v2/info".format(__opts__['proxy'].get(
            'base_url',
            "http://locahost:8080",
        )),
        decode_type='json',
        decode=True,
    )
    if not response or 'dict' not in response:
        return {'marathon': None}
    return {'marathon': response['dict']}
