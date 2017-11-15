# -*- coding: utf-8 -*-
#
# Author: Bo Maryniuk <bo@suse.de>
#
# Copyright 2017 SUSE LLC
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

'''
Salt Service Discovery Protocol.
JSON-based service discovery protocol, used by minions to find running Master.
'''

import datetime
import time
import logging
import socket
from collections import OrderedDict

from salt.utils import json
json = json.import_json()
if not hasattr(json, 'dumps'):
    json = None

try:
    import asyncio
    asyncio.ported = False
except ImportError:
    try:
        # Python 2 doesn't have asyncio
        import trollius as asyncio
        asyncio.ported = True
    except ImportError:
        asyncio = None


class TimeOutException(Exception):
    pass


class TimeStampException(Exception):
    pass


class SSDPBase(object):
    '''
    Salt Service Discovery Protocol.
    '''
    log = logging.getLogger(__name__)

    # Fields
    SIGNATURE = 'signature'
    ANSWER = 'answer'
    PORT = 'port'
    LISTEN_IP = 'listen_ip'
    TIMEOUT = 'timeout'

    # Default values
    DEFAULTS = {
        SIGNATURE: '__salt_master_service',
        PORT: 30777,
        LISTEN_IP: '0.0.0.0',
        TIMEOUT: 3,
        ANSWER: {},
    }

    @staticmethod
    def _is_available():
        '''
        Return True if the USSDP dependencies are satisfied.
        :return:
        '''
        return bool(asyncio and json)

    @staticmethod
    def get_self_ip():
        '''
        Find out localhost outside IP.

        :return:
        '''
        sck = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            sck.connect(('1.255.255.255', 1))  # Does not needs to be reachable
            ip_addr = sck.getsockname()[0]
        except Exception:
            ip_addr = socket.gethostbyname(socket.gethostname())
        finally:
            sck.close()
        return ip_addr


class SSDPFactory(SSDPBase):
    '''
    Socket protocol factory.
    '''

    def __init__(self, **config):
        '''
        Initialize

        :param config:
        '''
        for attr in (self.SIGNATURE, self.ANSWER):
            setattr(self, attr, config.get(attr, self.DEFAULTS[attr]))
        self.disable_hidden = False
        self.transport = None
        self.my_ip = socket.gethostbyname(socket.gethostname())

    def __call__(self, *args, **kwargs):
        '''
        Return instance on Factory call.
        :param args:
        :param kwargs:
        :return:
        '''
        return self

    def connection_made(self, transport):
        '''
        On connection.

        :param transport:
        :return:
        '''
        self.transport = transport

    def datagram_received(self, data, addr):
        '''
        On datagram receive.

        :param data:
        :param addr:
        :return:
        '''
        message = data.decode()
        if message.startswith(self.signature):
            try:
                timestamp = float(message[len(self.signature):])
            except TypeError:
                self.log.debug('Received invalid timestamp in package from %s' % ("%s:%s" % addr))
                if self.disable_hidden:
                    self.transport.sendto('{0}#ERROR#{1}'.format(self.signature, 'Invalid timestamp'), addr)
                return

            if datetime.datetime.fromtimestamp(timestamp) < (datetime.datetime.now() - datetime.timedelta(seconds=20)):
                if self.disable_hidden:
                    self.transport.sendto('{0}#ERROR#{1}'.format(self.signature, 'Timestamp is too old'), addr)
                self.log.debug('Received outdated package from %s' % ("%s:%s" % addr))
                return

            self.log.debug('Received %r from %s' % (message, "%s:%s" % addr))
            self.transport.sendto('{0}#OK#{1}'.format(self.signature,
                                                      json.dumps(self.answer)), addr)
        else:
            if self.disable_hidden:
                self.transport.sendto('{0}#ERROR#{1}'.format(self.signature,
                                                             'Invalid packet signature').encode(), addr)
            self.log.debug('Received bad magic or password from %s:%s' % addr)


class SSDPDiscoveryServer(SSDPBase):
    '''
    Discovery service publisher.

    '''
    is_available = SSDPBase._is_available

    def __init__(self, **config):
        '''
        Initialize.

        :param config:
        '''
        self._config = config.copy()
        if self.ANSWER not in self._config:
            self._config[self.ANSWER] = {}
        self._config[self.ANSWER].update({'master': self.get_self_ip()})

    @staticmethod
    def create_datagram_endpoint(loop, protocol_factory, local_addr=None, remote_addr=None, family=0, proto=0, flags=0):
        '''
        Create datagram connection.

        Based on code from Python 3.5 version, this method is used
        only in Python 2.7+ versions, since Trollius library did not
        ported UDP packets broadcast.
        '''
        if not (local_addr or remote_addr):
            if not family:
                raise ValueError('unexpected address family')
            addr_pairs_info = (((family, proto), (None, None)),)
        else:
            addr_infos = OrderedDict()
            for idx, addr in ((0, local_addr), (1, remote_addr)):
                if addr is not None:
                    assert isinstance(addr, tuple) and len(addr) == 2, '2-tuple is expected'
                    infos = yield asyncio.coroutines.From(loop.getaddrinfo(
                        *addr, family=family, type=socket.SOCK_DGRAM, proto=proto, flags=flags))
                    if not infos:
                        raise socket.error('getaddrinfo() returned empty list')
                    for fam, _, pro, _, address in infos:
                        key = (fam, pro)
                        if key not in addr_infos:
                            addr_infos[key] = [None, None]
                        addr_infos[key][idx] = address
            addr_pairs_info = [
                (key, addr_pair) for key, addr_pair in addr_infos.items()
                if not ((local_addr and addr_pair[0] is None) or
                        (remote_addr and addr_pair[1] is None))]
            if not addr_pairs_info:
                raise ValueError('can not get address information')
        exceptions = []
        for ((family, proto),
             (local_address, remote_address)) in addr_pairs_info:
            sock = r_addr = None
            try:
                sock = socket.socket(family=family, type=socket.SOCK_DGRAM, proto=proto)
                for opt in [socket.SO_REUSEADDR, socket.SO_BROADCAST]:
                    sock.setsockopt(socket.SOL_SOCKET, opt, 1)
                sock.setblocking(False)
                if local_addr:
                    sock.bind(local_address)
                if remote_addr:
                    yield asyncio.coroutines.From(loop.sock_connect(sock, remote_address))
                    r_addr = remote_address
            except socket.error as exc:
                if sock is not None:
                    sock.close()
                exceptions.append(exc)
            except Exception:
                if sock is not None:
                    sock.close()
                raise
            else:
                break
        else:
            raise exceptions[0]

        protocol = protocol_factory()
        waiter = asyncio.futures.Future(loop=loop)
        transport = loop._make_datagram_transport(sock, protocol, r_addr, waiter)
        try:
            yield asyncio.coroutines.From(waiter)
        except Exception:
            transport.close()
            raise
        raise asyncio.coroutines.Return(transport, protocol)

    def run(self):
        '''
        Run server.
        :return:
        '''
        listen_ip = self._config.get(self.LISTEN_IP, self.DEFAULTS[self.LISTEN_IP])
        port = self._config.get(self.PORT, self.DEFAULTS[self.PORT])
        self.log.info('Starting service discovery listener on udp://{0}:{1}'.format(listen_ip, port))
        loop = asyncio.get_event_loop()
        protocol = SSDPFactory(answer=self._config[self.ANSWER])
        if asyncio.ported:
            transport, protocol = loop.run_until_complete(
                SSDPDiscoveryServer.create_datagram_endpoint(loop, protocol, local_addr=(listen_ip, port)))
        else:
            transport, protocol = loop.run_until_complete(
                loop.create_datagram_endpoint(protocol, local_addr=(listen_ip, port), allow_broadcast=True))
        try:
            loop.run_forever()
        finally:
            self.log.info('Stopping service discovery listener.')
            transport.close()
            loop.close()


class SSDPDiscoveryClient(SSDPBase):
    '''
    Class to discover Salt Master via UDP broadcast.
    '''
    is_available = SSDPBase._is_available

    def __init__(self, **config):
        '''
        Initialize
        '''
        self._config = config
        self._socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._socket.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        self._socket.settimeout(self._config.get(self.TIMEOUT, self.DEFAUTS[self.TIMEOUT]))

        for attr in [self.SIGNATURE, self.TIMEOUT, self.PORT]:
            setattr(self, attr, self._config.get(attr, self.DEFAUTS[attr]))

    def _query(self):
        '''
        Query the broadcast for defined services.
        :return:
        '''
        query = "%s%s" % (self.signature, time.time())
        self._socket.sendto(query.encode(), ('<broadcast>', self.port))

        return query

    def discover(self):
        '''
        Gather the information of currently declared servers.

        :return:
        '''
        self.log.info("Looking for a server discovery")
        try:
            self._query()
            data, addr = self._socket.recvfrom(1024)  # wait for a packet
        except socket.timeout:
            msg = 'No master has been discovered.'
            self.log.info(msg)
            raise TimeOutException(msg)
        msg = data.decode()
        if msg.startswith(self.signature):
            msg = msg.split(self.signature)[-1]
            self.log.debug("Service announcement at '{0}'. Response: '{1}'".format("%s:%s" % addr, msg))
            if '#ERROR#' in msg:
                err = msg.split('#ERROR#')[-1]
                self.log.debug('Error response from the service publisher: {0}'.format(err))
                if "timestamp" in err:
                    raise TimeStampException(err)
            else:
                return json.loads(msg.split('#OK#')[-1]), "%s:%s" % addr
