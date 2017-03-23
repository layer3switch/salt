# -*- coding: utf-8 -*-
'''
The `cache` roster provides a flexible interface to the Salt Masters' minion cache
to access regular minions over ``salt-ssh``.

.. versionadded:: Nitrogen

    - grains, pillar, mine data matching
    - environment variables
    - IPv6 support
    - roster_order per config key
    - default order changed to industry-wide best practices
    - CIDR range selection


Targeting
---------

This roster supports all matching and targeting of the Salt Master.
The matching will be done using only the Salt Master's cache.


The Roster Order
----------------

The roster's composition can be configured using ``roster_order``.
In the ``roster_order`` you can define *any* roster key and fill it with a parameter
overriding the one in ``roster_defaults``:

.. code-block:: yaml

roster_order:
    host: id          # use the minion id as hostname


You can define lists of parameters as well, the first result from the list will become the value.


Selecting a host
================

.. code-block:: yaml

# default
roster_order:
    host:
      - ipv6-private  # IPv6 addresses in private ranges
      - ipv6-global   # IPv6 addresses in global ranges
      - ipv4-private  # IPv4 addresses in private ranges
      - ipv4-public   # IPv4 addresses in public ranges
      - ipv4-local    # loopback addresses


This is the default ``roster_order``.
It prefers IPv6 over IPv4 addresses and private addresses over public ones.
The relevant data will be fetched from the cache in-order, and the first match will fill the ``host`` key.

Other address selection parameters are also possible:

.. code-block:: yaml

roster_order:
  host:
    - global|public|private|local    # Both IPv6 and IPv4 addresses in that range
    - 2000::/3                       # CIDR networks, both IPv4 and IPv6 are supported


Using cached data
=================

Several cached libraries can be selected using the ``library: `` prefix, followed by the library key.
This can be referenced using the same ``:`` syntax as e.g. ``pillar.get()``.
Lists of references are also supported during the lookup, as are Salt SDB URLs.

This should be especially useful for the other roster keys:

.. code-block:: yaml

roster_order:
  host:
    - grain: fqdn_ip4                # Lookup this grain
    - mine: network.ip_addrs         # Mine data lookup works the same

  password: sdb://vault/ssh_pass     # Salt SDB URLs are also supported

  user:
    - pillar: ssh:auth:user          # Lookup this pillar key
    - env: USER                      # Lookup this env var

  priv:
    - pillar:                        # Lists are also supported
        - salt:ssh:private_key
        - ssh:auth:private_key

'''
from __future__ import absolute_import

# Python
import logging
import os
import re

# Salt libs
import salt.utils.minions
import salt.cache
from salt._compat import ipaddress
import salt.ext.six as six

log = logging.getLogger(__name__)


def targets(tgt, tgt_type='glob', **kwargs):  # pylint: disable=W0613
    '''
    Return the targets from the Salt Masters' minion cache.
    All targets and matchers are supported.

    The resulting roster can be configured using ``roster_order`` and ``roster_default``.
    '''
    minions = salt.utils.minions.CkMinions(__opts__)
    minions = minions.check_minions(tgt, tgt_type)

    ret = {}
    if not minions:
        return ret
    # log.debug(minions)

    cache = salt.cache.Cache(__opts__)

    roster_order = __opts__.get('roster_order', {
        'host': ('ipv6-private', 'ipv6-global', 'ipv4-private', 'ipv4-public')
    })
    if isinstance(roster_order, (tuple, list)):
        salt.utils.warn_until('Oxygen',
                              'Using legacy syntax for roster_order')
        roster_order = {
            'host': roster_order
        }
    for config_key, order in roster_order.items():
        for idx, key in enumerate(order):
            if key in ('public', 'private', 'local'):
                salt.utils.warn_until('Oxygen',
                                      'roster_order {0} will include IPv6 soon. '
                                      'Set order to ipv4-{0} if needed.'.format(key))
                order[idx] = 'ipv4-' + key

    # log.debug(roster_order)

    ret = {}
    for minion_id in minions:
        try:
            minion = _load_minion(minion_id, cache)
        except LookupError:
            continue

        minion_res = __opts__.get('roster_defaults', {}).copy()
        for param, order in roster_order.items():
            if not isinstance(order, (list, tuple)):
                order = [order]
            for key in order:
                kres = _minion_lookup(minion_id, key, minion)
                if kres:
                    minion_res[param] = kres
                    break

        if 'host' in minion_res:
            ret[minion_id] = minion_res
        else:
            log.warn('Could not determine host information for minion {0}'.format(minion_id))

    log.debug('Roster lookup result: {0}'.format(ret))

    return ret


def _load_minion(minion_id, cache):
    data_minion, grains, pillar = salt.utils.minions.get_minion_data(minion_id, __opts__)

    if minion_id != data_minion:
        log.error('Asked for minion {0}, got {1}'.format(minion_id, data_minion))
        raise LookupError

    if not grains:
        log.warn('No grain data for minion id {0}'.format(minion_id))
        grains = {}

    if not pillar:
        log.warn('No pillar data for minion id {0}'.format(minion_id))
        pillar = {}

    addrs = {
        4: sorted([ipaddress.IPv4Address(addr) for addr in grains.get('ipv4', [])]),
        6: sorted([ipaddress.IPv6Address(addr) for addr in grains.get('ipv6', [])])
    }

    mine = cache.fetch('minions/{0}'.format(minion_id), 'mine')

    return grains, pillar, addrs, mine


def _data_lookup(ref, lookup):
    if isinstance(lookup, six.string_types):
        lookup = [lookup]

    res = []
    for data_key in lookup:
        data = salt.utils.traverse_dict_and_list(ref, data_key, None)
        # log.debug('Fetched {0} in {1}: {2}'.format(data_key, ref, data))
        if data:
            res.append(data)

    return res


def _minion_lookup(minion_id, key, minion):
    grains, pillar, addrs, mine = minion

    if key == 'id':
        # Just paste in the minion ID
        return minion_id
    elif key.startswith('sdb://'):
        # It's a Salt SDB url
        return salt['sdb.get'](key)
    elif isinstance(key, dict):
        # Lookup the key in the dict
        for data_id, lookup in key.items():
            ref = {
                'pillar': pillar,
                'grain': grains,
                'mine': mine,
                'env': os.environ,
            }[data_id]

            for k in _data_lookup(ref, lookup):
                if k:
                    return k

            return None
    elif re.match(r'^[0-9a-fA-F:./]+$', key):
        # It smells like a CIDR block
        try:
            net = ipaddress.ip_network(key, strict=True)
        except ValueError:
            log.error('{0} is an invalid CIDR network'.format(net))
            return None

        for addr in addrs[net.version]:
            if addr in net:
                return str(addr)
    else:
        # Take the addresses from the grains and filter them
        filters = {
            'global': lambda addr: addr.is_global if addr.version == 6 else not addr.is_private,
            'public': lambda addr: not addr.is_private,
            'private': lambda addr: addr.is_private and not addr.is_loopback and not addr.is_link_local,
            'local': lambda addr: addr.is_loopback,
        }

        ip_vers = [4, 6]
        if key.startswith('ipv'):
            ip_vers = [int(key[3])]
            key = key[5:]

        for ip_ver in ip_vers:
            try:
                for addr in addrs[ip_ver]:
                    if filters[key](addr):
                        return str(addr)
            except KeyError:
                raise KeyError('Invalid filter {0} specified in roster_order'.format(key))
