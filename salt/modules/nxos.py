from __future__ import absolute_import
import contextlib
import re

import salt.utils
from salt.utils.vt_helper import SSHConnection

import logging
log = logging.getLogger(__name__)

__proxyenabled__ = ['nxos']
__virtualname__ = 'nxos'


def __virtual__():
    if salt.utils.is_proxy():
        return __virtualname__
    return (False, 'The nxos execution module failed to load: '
            'only available on proxy minions.')


def _parser(block):
    return re.compile('^{block}\n(?:^[ \n].*$\n?)+'.format(block=block), re.MULTILINE)


def _parse_software(data):
    ret = {'software': {}}
    software = _parser('Software').search(data).group(0)
    matcher = re.compile('^  ([^:]+): *([^\n]+)', re.MULTILINE)
    for line in matcher.finditer(software):
        key, val = line.groups()
        ret['software'][key] = val
    return ret['software']


def _parse_hardware(data):
    ret = {'hardware': {}}
    hardware = _parser('Hardware').search(data).group(0)
    matcher = re.compile('^  ([^:\n]+): *([^\n]+)', re.MULTILINE)
    for line in matcher.finditer(hardware):
        key, val = line.groups()
        ret['hardware'][key] = val
    return ret['hardware']


def _parse_plugins(data):
    ret = {'plugins': []}
    plugins = _parser('plugin').search(data).group(0)
    matcher = re.compile('^  (?:([^,]+), )+([^\n]+)', re.MULTILINE)
    for line in matcher.finditer(plugins):
        ret['plugins'].extend(line.groups())
    return ret['plugins']


@contextlib.contextmanager
def make_connection(opts=None):
    if not opts:
	if '__opts__' not in globals():
	    raise
	opts = __opts__
    connection = SSHConnection(
	host=opts['proxy']['host'],
	username=opts['proxy']['username'],
	password=opts['proxy']['password'],
	key_accept=opts['proxy']['key_accept'],
	ssh_args=opts['proxy']['ssh_args'],
	prompt='{0}.*#'.format(opts['proxy']['hostname'])
    )
    yield connection
    connection.close_connection()


def system_info(opts=None):
    with make_connection(opts=opts) as connection:
	out, err = connection.sendline('terminal length 0')
	out, err = connection.sendline('show ver')
    _, out = out.split('\n', 1)
    data, _, _ = out.rpartition('\n')
    info = {
        'software': _parse_software(data),
        'hardware': _parse_hardware(data),
        'plugins': _parse_plugins(data),
    }
    return info


def cmd(command, *args, **kwargs):
    proxy_prefix = __opts__['proxy']['proxytype']
    proxy_cmd = '.'.join([proxy_prefix, command])
    if proxy_cmd not in __proxy__:
        return False
    for k in kwargs.keys():
        if k.startswith('__pub_'):
            kwargs.pop(k)
    return __proxy__[proxy_cmd](*args, **kwargs)
