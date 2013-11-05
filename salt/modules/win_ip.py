# -*- coding: utf-8 -*-
'''
The networking module for Windows based systems
'''

# Import python libs
import logging
import socket
import time

# Import salt libs
import salt.utils
import salt.utils.network
import salt.utils.validate.net
from salt.exceptions import (
    CommandExecutionError,
    SaltInvocationError
)

# Set up logging
log = logging.getLogger(__name__)

# Define the module's virtual name
__virtualname__ = 'ip'


def __virtual__():
    '''
    Confine this module to Windows systems
    '''
    if salt.utils.is_windows():
        return __virtualname__
    return False


def _interface_configs():
    '''
    Return all interface configs
    '''
    cmd = 'netsh interface ip show config'
    lines = __salt__['cmd.run'](cmd).splitlines()
    iface = ''
    ip = 0
    dns_flag = None
    wins_flag = None
    ret = {}
    for line in lines:
        if dns_flag:
            try:
                socket.inet_aton(line.strip())
                ret[iface][dns_flag].append(line.strip())
                dns_flag = None
                continue
            except socket.error as exc:
                dns_flag = None
        if wins_flag:
            try:
                socket.inet_aton(line.strip())
                ret[iface][wins_flag].append(line.strip())
                wins_flag = None
                continue
            except socket.error as exc:
                wins_flag = None
        if not line:
            iface = ''
            continue
        if 'Configuration for interface' in line:
            _, iface = line.rstrip('"').split('"', 1)  # get iface name
            ret[iface] = {}
            ip = 0
            continue
        try:
            key, val = line.split(':', 1)
        except ValueError as exc:
            log.debug('Could not split line. Error was {0}.'.format(exc))
            continue
        if 'DNS Servers' in line:
            dns_flag = key.strip()
            ret[iface][key.strip()] = [val.strip()]
            continue
        if 'WINS Servers' in line:
            wins_flag = key.strip()
            ret[iface][key.strip()] = [val.strip()]
            continue
        if 'IP Address' in key:
            if 'ip_addrs' not in ret[iface]:
                ret[iface]['ip_addrs'] = []
            ret[iface]['ip_addrs'].append(dict([(key.strip(), val.strip())]))
            continue
        if 'Subnet Prefix' in key:
            subnet, _, netmask = val.strip().split(' ', 2)
            ret[iface]['ip_addrs'][ip]['Subnet'] = subnet.strip()
            ret[iface]['ip_addrs'][ip]['Netmask'] = netmask.lstrip().rstrip(')')
            ip = ip + 1
            continue
        else:
            ret[iface][key.strip()] = val.strip()
    return ret


def raw_interface_configs():
    '''
    Return raw configs for all interfaces

    CLI Example:

    .. code-block:: bash

        salt -G 'os_family:Windows' ip.raw_interface_configs
    '''
    cmd = 'netsh interface ip show config'
    return __salt__['cmd.run'](cmd)


def get_all_interfaces():
    '''
    Return configs for all interfaces

    CLI Example:

    .. code-block:: bash

        salt -G 'os_family:Windows' ip.get_all_interfaces
    '''
    return _interface_configs()


def get_interface(iface):
    '''
    Return the configuration of a network interface

    CLI Example:

    .. code-block:: bash

        salt -G 'os_family:Windows' ip.get_interface 'Local Area Connection'
    '''
    return _interface_configs().get(iface, {})


def is_enabled(iface):
    '''
    Returns ``True`` if interface is enabled, otherwise ``False``

    CLI Example:

    .. code-block:: bash

        salt -G 'os_family:Windows' ip.is_enabled 'Local Area Connection #2'
    '''
    cmd = 'netsh interface show interface name="{0}"'.format(iface)
    iface_found = False
    for line in __salt__['cmd.run'](cmd).splitlines():
        if 'Connect state:' in line:
            iface_found = True
            return line.split()[-1] == 'Connected'
    if not iface_found:
        raise CommandExecutionError('Interface {0!r} not found')
    return False


def is_disabled(iface):
    '''
    Returns ``True`` if interface is disabled, otherwise ``False``

    CLI Example:

    .. code-block:: bash

        salt -G 'os_family:Windows' ip.is_disabled 'Local Area Connection #2'
    '''
    return not is_enabled(iface)


def enable(iface):
    '''
    Enable an interface

    CLI Example:

    .. code-block:: bash

        salt -G 'os_family:Windows' ip.enable 'Local Area Connection #2'
    '''
    if is_enabled(iface):
        return True
    __salt__['cmd.run'](
        'netsh interface set interface "{0}" admin=ENABLED'.format(iface)
    )
    return is_enabled(iface)


def disable(iface):
    '''
    Disable an interface

    CLI Example:

    .. code-block:: bash

        salt -G 'os_family:Windows' ip.disable 'Local Area Connection #2'
    '''
    if is_disabled(iface):
        return True
    __salt__['cmd.run'](
        'netsh interface set interface "{0}" admin=DISABLED'.format(iface)
    )
    return is_disabled(iface)


def get_subnet_length(mask):
    '''
    Convenience function to convert the netmask to the CIDR subnet length

    CLI Example:

    .. code-block:: bash

        salt -G 'os_family:Windows' ip.get_subnet_length 255.255.255.0
    '''
    if not salt.utils.validate.net.netmask(mask):
        raise SaltInvocationError('{0!r} is not a valid netmask'.format(mask))
    return salt.utils.network.get_net_size(mask)


def set_static_ip(iface, addr, gateway=None, append=False):
    '''
    Set static IP configuration on a Windows NIC

    iface
        The name of the interface to manage

    addr
        IP address with subnet length (ex. ``10.1.2.3/24``). The
        :mod:`ip.get_subnet_length <salt.modules.win_ip.get_subnet_length>`
        function can be used to calculate the subnet length from a netmask.

    gateway : None
        If specified, the default gateway will be set to this value.

    append : False
        If ``True``, this IP address will be added to the interface. Default is
        ``False``, which overrides any existing configuration for the interface
        and sets ``addr`` as the only address on the interface.

    CLI Example:

    .. code-block:: bash

        salt -G 'os_family:Windows' ip.set_static_ip 'Local Area Connection' 10.1.2.3/24 gateway=10.1.2.1
        salt -G 'os_family:Windows' ip.set_static_ip 'Local Area Connection' 10.1.2.4/24 append=True
    '''
    def _find_addr(iface, addr, timeout=1):
        ip, cidr = addr.rsplit('/', 1)
        netmask = salt.utils.network.cidr_to_ipv4_netmask(cidr)
        for idx in xrange(timeout):
            for addrinfo in get_interface(iface).get('ip_addrs', []):
                if addrinfo['IP Address'] == ip \
                        and addrinfo['Netmask'] == netmask:
                    return addrinfo
            time.sleep(1)
        return {}

    if not salt.utils.validate.net.ipv4_addr(addr):
        raise SaltInvocationError('Invalid address {0!r}'.format(addr))

    if gateway and not salt.utils.validate.net.ipv4_addr(addr):
        raise SaltInvocationError(
            'Invalid default gateway {0!r}'.format(gateway)
        )

    if '/' not in addr:
        addr += '/32'

    if append and _find_addr(iface, addr):
        raise CommandExecutionError(
            'Address {0!r} already exists on interface '
            '{1!r}'.format(addr, iface)
        )

    # Do not use raw string formatting (ex. {1!r}) for interface name, as the
    # windows command shell does not like single quotes.
    cmd = (
        'netsh interface ip {0} address name="{1}" {2} '
        'address={3}{4}'.format(
            'add' if append else 'set',
            iface,
            '' if append else 'source=static',
            addr,
            ' gateway={0}'.format(gateway) if gateway else '',
        )
    )
    result = __salt__['cmd.run_all'](cmd)
    if result['retcode'] != 0:
        raise CommandExecutionError(
            'Unable to set IP address: {0}'.format(result['stderr'])
        )

    new_addr = _find_addr(iface, addr, timeout=10)
    if not new_addr:
        return {}

    ret = {'Address Info': new_addr}
    if gateway:
        ret['Default Gateway'] = gateway
    return ret


def set_dhcp_ip(iface):
    '''
    Set Windows NIC to get IP from DHCP

    CLI Example:

    .. code-block:: bash

        salt -G 'os_family:Windows' ip.set_dhcp_ip 'Local Area Connection'
    '''
    cmd = 'netsh interface ip set address "{0}" dhcp'.format(iface)
    __salt__['cmd.run'](cmd)
    return {'Interface': iface, 'DHCP enabled': 'Yes'}


def set_static_dns(iface, *addrs):
    '''
    Set static DNS configuration on a Windows NIC

    CLI Example:

    .. code-block:: bash

        salt -G 'os_family:Windows' ip.set_static_dns 'Local Area Connection' '192.168.1.1'
        salt -G 'os_family:Windows' ip.set_static_dns 'Local Area Connection' '192.168.1.252' '192.168.1.253'
    '''
    addr_index = 1
    for addr in addrs:
        if addr_index == 1:
            cmd = 'netsh int ip set dns "{0}" static {1} primary'.format(
                    iface,
                    addrs[0],
                    )
            __salt__['cmd.run'](cmd)
            addr_index = addr_index + 1
        else:
            cmd = 'netsh interface ip add dns name="{0}" addr="{1}" index={2}'
            __salt__['cmd.run'](cmd.format(iface, addr, addr_index))
            addr_index = addr_index + 1
    return {'Interface': iface, 'DNS Server': addrs}


def set_dhcp_dns(iface):
    '''
    Set DNS source to DHCP on Windows

    CLI Example:

    .. code-block:: bash

        salt -G 'os_family:Windows' ip.set_dhcp_dns 'Local Area Connection'
    '''
    cmd = 'netsh interface ip set dns "{0}" dhcp'.format(iface)
    __salt__['cmd.run'](cmd)
    return {'Interface': iface, 'DNS Server': 'DHCP'}


def set_dhcp_all(iface):
    '''
    Set both IP Address and DNS to DHCP

    CLI Example:

    ..code-block:: bash

        salt -G 'os_family:Windows' ip.set_dhcp_all 'Local Area Connection'
    '''
    set_dhcp_ip(iface)
    set_dhcp_dns(iface)
    return {'Interface': iface, 'DNS Server': 'DHCP', 'DHCP enabled': 'Yes'}


def get_default_gateway():
    '''
    Set DNS source to DHCP on Windows

    CLI Example:

    .. code-block:: bash

        salt -G 'os_family:Windows' ip.get_default_gateway
    '''
    try:
        return next(iter(
            x.split()[-1] for x in __salt__['cmd.run'](
                'netsh interface ip show config'
            ).splitlines()
            if 'Default Gateway:' in x
        ))
    except StopIteration:
        raise CommandExecutionError('Unable to find default gateway')
