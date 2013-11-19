# -*- coding: utf-8 -*-
'''
Configuration of network interfaces on Windows hosts
====================================================

.. versionadded:: Hydrogen

This module provides the ``network`` state(s) on Windows hosts. DNS servers, IP
addresses and default gateways can currently be managed.

Below is an example of the configuration for an interface that uses DHCP for
both DNS servers and IP addresses:

.. code-block:: yaml

    Local Area Connection #2:
      network.managed:
        - dns_proto: dhcp
        - ip_proto: dhcp

.. note::

    Both the ``dns_proto`` and ``ip_proto`` arguments are required.

Static DNS and IP addresses can be configured like so:

.. code-block:: yaml

    Local Area Connection #2:
      network.managed:
        - dns_proto: static
        - dns_servers:
          - 8.8.8.8
          - 8.8.4.4
        - ip_proto: static
        - ip_addrs:
          - 10.2.3.4/24

.. note::

    IP addresses are specified using the format
    ``<ip-address>/<subnet-length>``. Salt provides a convenience function
    called :mod:`ip.get_subnet_length <salt.modules.win_ip.get_subnet_length>`
    to calculate the subnet length from a netmask.

Optionally, if you are setting a static IP address, you can also specify the
default gateway using the ``gateway`` parameter:

.. code-block:: yaml

    Local Area Connection #2:
      network.managed:
        - dns_proto: static
        - dns_servers:
          - 8.8.8.8
          - 8.8.4.4
        - ip_proto: static
        - ip_addrs:
          - 10.2.3.4/24
        - gateway: 10.2.3.1
'''

# Import python libs
import logging

# Import salt libs
import salt.utils
import salt.utils.validate.net

# Set up logging
log = logging.getLogger(__name__)

__VALID_PROTO = ('static', 'dhcp')

# Define the module's virtual name
__virtualname__ = 'network'


def __virtual__():
    '''
    Confine this module to Windows systems with the required execution module
    available.
    '''
    if salt.utils.is_windows() and 'ip.get_interface' in __salt__:
        return __virtualname__
    return False


def _validate(dns_proto, dns_servers, ip_proto, ip_addrs, gateway):
    '''
    Ensure that the configuration passed is formatted correctly and contains
    valid IP addresses, etc.
    '''
    errors = []
    # Validate DNS configuration
    if dns_proto == 'dhcp':
        if dns_servers is not None:
            errors.append(
                'The dns_servers param cannot be set if unless dns_proto is '
                'set to \'static\'.'
            )
    else:
        if not dns_servers:
            errors.append(
                'The dns_servers param is required to set static DNS servers.'
            )
        elif not isinstance(dns_servers, list):
            errors.append(
                'The dns_servers param must be formatted as a list.'
            )
        else:
            bad_ips = [x for x in dns_servers
                       if not salt.utils.validate.net.ipv4_addr(x)]
            if bad_ips:
                errors.append('Invalid DNS server IPs: {0}.'
                              .format(', '.join(bad_ips)))

    # Validate IP configuration
    if ip_proto == 'dhcp':
        if ip_addrs is not None:
            errors.append(
                'The ip_addrs param cannot be set if unless ip_proto is set '
                'to \'static\'.'
            )
        if gateway is not None:
            errors.append(
                'A gateway IP cannot be set if unless ip_proto is set to '
                '\'static\'.'
            )
    else:
        if not ip_addrs:
            errors.append(
                'The ip_addrs param is required to set static IPs.'
            )
        elif not isinstance(ip_addrs, list):
            errors.append(
                'The ip_addrs param must be formatted as a list.'
            )
        else:
            bad_ips = [x for x in ip_addrs
                       if not salt.utils.validate.net.ipv4_addr(x)]
            if bad_ips:
                errors.append('The following static IPs are invalid: '
                              '{0}.'.format(', '.join(bad_ips)))

            # Validate default gateway
            if gateway is not None:
                if not salt.utils.validate.net.ipv4_addr(gateway):
                    errors.append('Gateway IP {0} is invalid.'.format(gateway))

    return errors


def _addrdict_to_ip_addrs(addrs):
    '''
    Extracts a list of IP/CIDR expressions from a list of addrdicts, as
    retrieved from ip.get_interface
    '''
    return [
        '{0}/{1}'.format(x['IP Address'], x['Subnet'].rsplit('/', 1)[-1])
        for x in addrs
    ]


def _changes(cur, dns_proto, dns_servers, ip_proto, ip_addrs, gateway):
    '''
    Compares the current interface against the desired configuration and
    returns a dictionary describing the changes that need to be made.
    '''
    changes = {}
    cur_dns_proto = (
        'static' if 'Statically Configured DNS Servers' in cur
        else 'dhcp'
    )
    if cur_dns_proto == 'static':
        cur_dns_servers = cur['Statically Configured DNS Servers']
    elif 'DNS servers configured through DHCP' in cur:
        cur_dns_servers = cur['DNS servers configured through DHCP']
    cur_ip_proto = 'static' if cur['DHCP enabled'] == 'No' else 'dhcp'
    cur_ip_addrs = _addrdict_to_ip_addrs(cur.get('ip_addrs', []))
    cur_gateway = cur.get('Default Gateway')

    if dns_proto != cur_dns_proto:
        changes['dns_proto'] = dns_proto
    if set(dns_servers or ['None']) != set(cur_dns_servers):
        changes['dns_servers'] = dns_servers
    if ip_proto != cur_ip_proto:
        changes['ip_proto'] = ip_proto
    if set(ip_addrs or []) != set(cur_ip_addrs):
        if ip_proto == 'static':
            changes['ip_addrs'] = ip_addrs
    if gateway != cur_gateway:
        if ip_proto == 'static':
            changes['gateway'] = gateway
    return changes


def managed(name,
            dns_proto=None,
            dns_servers=None,
            ip_proto=None,
            ip_addrs=None,
            gateway=None,
            enabled=True,
            **kwargs):
    '''
    Ensure that the named interface is configured properly.

    name
        The name of the interface to manage

    dns_proto : None
        Set to ``static`` and use the ``dns_servers`` parameter to provide a
        list of DNS nameservers. set to ``dhcp`` to use DHCP to get the DNS
        servers.

    dns_servers : None
        A list of static DNS servers.

    ip_proto : None
        Set to ``static`` and use the ``ip_addrs`` and (optionally) ``gateway``
        parameters to provide a list of static IP addresses and the default
        gateway. Set to ``dhcp`` to use DHCP.

    ip_addrs : None
        A list of static IP addresses.

    gateway : None
        A list of static IP addresses.

    enabled : True
        Set to ``False`` to ensure that this interface is disabled.

    '''
    ret = {
        'name': name,
        'changes': {},
        'result': True,
        'comment': 'Interface {0!r} is up to date.'.format(name)
    }

    dns_proto = str(dns_proto).lower()
    ip_proto = str(ip_proto).lower()

    errors = []
    if dns_proto not in __VALID_PROTO:
        ret['result'] = False
        errors.append('dns_proto must be one of the following: {0}.'
                      .format(', '.join(__VALID_PROTO)))

    if ip_proto not in __VALID_PROTO:
        errors.append('ip_proto must be one of the following: {0}.'
                      .format(', '.join(__VALID_PROTO)))

    if errors:
        ret['result'] = False
        ret['comment'] = ' '.join(errors)
        return ret

    if not enabled:
        if __salt__['ip.is_enabled'](name):
            if __opts__['test']:
                ret['result'] = None
                ret['comment'] = ('Interface {0!r} will be disabled'
                                  .format(name))
            else:
                ret['result'] = __salt__['ip.disable'](name)
                if not ret['result']:
                    ret['comment'] = ('Failed to disable interface {0!r}'
                                      .format(name))
        else:
            ret['comment'] += ' (already disabled)'
        return ret
    else:
        currently_enabled = __salt__['ip.is_disabled'](name)
        if not currently_enabled:
            if __opts__['test']:
                ret['result'] = None
                ret['comment'] = ('Interface {0!r} will be enabled'
                                  .format(name))
            else:
                result = __salt__['ip.enable'](name)
                if not result:
                    ret['result'] = False
                    ret['comment'] = ('Failed to enable interface {0!r} to '
                                      'make changes'.format(name))
                    return ret

        errors = _validate(dns_proto, dns_servers, ip_proto, ip_addrs, gateway)
        if errors:
            ret['result'] = False
            ret['comment'] = ('The following SLS configuration errors were '
                              'detected: {0}'.format(' '.join(errors)))
            return ret

        old = __salt__['ip.get_interface'](name)
        if not old:
            ret['result'] = False
            ret['comment'] = ('Unable to get current configuration for '
                              'interface {0!r}'.format(name))
            return ret

        changes = _changes(old,
                           dns_proto,
                           dns_servers,
                           ip_proto,
                           ip_addrs,
                           gateway)
        if not changes:
            return ret

        if __opts__['test']:
            comments = []
            if 'dns_proto' in changes:
                comments.append('DNS protocol will be changed to: {0}.'
                                .format(changes['dns_proto']))
            if dns_proto == 'static' and 'dns_servers' in changes:
                comments.append(
                    'DNS servers will be set to the following: {0}.'
                    .format(', '.join(changes['dns_servers']))
                )
            if 'ip_proto' in changes:
                comments.append('IP protocol will be changed to: {0}.'
                                .format(changes['ip_proto']))
            if ip_proto == 'static':
                if 'ip_addrs' in changes:
                    comments.append(
                        'IP addresses will be set to the following: {0}.'
                        .format(', '.join(changes['ip_addrs']))
                    )
                if 'gateway' in changes:
                    if changes['gateway'] is None:
                        comments.append('Default gateway will be removed.')
                    else:
                        comments.append(
                            'Default gateway will be set to {0}.'
                            .format(changes['gateway'])
                        )

            ret['result'] = None
            ret['comment'] = ('The following changes will be made to '
                              'interface {0!r}: {1}'
                              .format(name, ' '.join(comments)))
            return ret

        if changes.get('dns_proto') == 'dhcp':
            __salt__['ip.set_dhcp_dns'](name)

        elif changes.get('dns_servers'):
            if changes.get('dns_servers'):
                __salt__['ip.set_static_dns'](name, *changes['dns_servers'])

        if changes.get('ip_proto') == 'dhcp':
            __salt__['ip.set_dhcp_ip'](name)
        elif changes.get('ip_addrs') or changes.get('gateway') or changes.get('ip_proto') == 'static':
            if changes.get('gateway') and not changes.get('ip_addrs'):
                changes['ip_addrs'] = ip_addrs
            if changes.get('ip_proto') == 'static' and not changes.get('ip_addrs'):
                changes['ip_addrs'] = ip_addrs
            for idx in xrange(len(changes['ip_addrs'])):
                if idx == 0:
                    __salt__['ip.set_static_ip'](
                        name,
                        changes['ip_addrs'][idx],
                        gateway=gateway,
                        append=False
                    )
                else:
                    __salt__['ip.set_static_ip'](
                        name,
                        changes['ip_addrs'][idx],
                        gateway=None,
                        append=True
                    )

        new = __salt__['ip.get_interface'](name)
        ret['changes'] = salt.utils.compare_dicts(old, new)
        if _changes(new, dns_proto, dns_servers, ip_proto, ip_addrs, gateway):
            ret['result'] = False
            ret['comment'] = ('Failed to set desired configuration settings '
                              'for interface {0!r}'.format(name))
        else:
            ret['comment'] = ('Successfully updated configuration for '
                              'interface {0!r}'.format(name))
        return ret
