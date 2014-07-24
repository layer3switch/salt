# -*- coding: utf-8 -*-
'''
Compendium of generic DNS utilities
'''

# Import salt libs
import salt.utils
import socket

# Import python libs
import logging

log = logging.getLogger(__name__)


def __virtual__():
    '''
    Generic, should work on any platform (including Windows). Functionality
    which requires dependencies outside of Python do not belong in this module.
    '''
    return True


def parse_hosts(hostsfile='/etc/hosts', hosts=None):
    '''
    Parse /etc/hosts file.

    CLI Example:

    .. code-block:: bash

        salt '*' dnsutil.parse_hosts
    '''
    if not hosts:
        try:
            with salt.utils.fopen(hostsfile, 'r') as fp_:
                hosts = fp_.read()
        except Exception:
            return 'Error: hosts data was not found'

    hostsdict = {}
    for line in hosts.splitlines():
        if not line:
            continue
        if line.startswith('#'):
            continue
        comps = line.split()
        ip = comps[0]
        aliases = comps[1:]
        hostsdict.setdefault(ip, []).extend(aliases)

    return hostsdict


def hosts_append(hostsfile='/etc/hosts', ip_addr=None, entries=None):
    '''
    Append a single line to the /etc/hosts file.

    CLI Example:

    .. code-block:: bash

        salt '*' dnsutil.hosts_append /etc/hosts 127.0.0.1 ad1.yuk.co,ad2.yuk.co
    '''
    host_list = entries.split(',')
    hosts = parse_hosts(hostsfile=hostsfile)
    if ip_addr in hosts:
        for host in host_list:
            if host in hosts[ip_addr]:
                host_list.remove(host)

    if not host_list:
        return 'No additional hosts were added to {0}'.format(hostsfile)

    append_line = '\n{0} {1}'.format(ip_addr, ' '.join(host_list))
    with salt.utils.fopen(hostsfile, 'a') as fp_:
        fp_.write(append_line)

    return 'The following line was added to {0}:{1}'.format(hostsfile,
                                                            append_line)


def hosts_remove(hostsfile='/etc/hosts', entries=None):
    '''
    Remove a host from the /etc/hosts file. If doing so will leave a line
    containing only an IP address, then the line will be deleted. This function
    will leave comments and blank lines intact.

    CLI Examples:

    .. code-block:: bash

        salt '*' dnsutil.hosts_remove /etc/hosts ad1.yuk.co
        salt '*' dnsutil.hosts_remove /etc/hosts ad2.yuk.co,ad1.yuk.co
    '''
    with salt.utils.fopen(hostsfile, 'r') as fp_:
        hosts = fp_.read()

    host_list = entries.split(',')
    out_file = salt.utils.fopen(hostsfile, 'w')
    for line in hosts.splitlines():
        if not line or line.strip().startswith('#'):
            out_file.write('{0}\n'.format(line))
            continue
        comps = line.split()
        for host in host_list:
            if host in comps[1:]:
                comps.remove(host)
        if len(comps) > 1:
            out_file.write(' '.join(comps))
            out_file.write('\n')

    out_file.close()


def parse_zone(zonefile=None, zone=None):
    '''
    Parses a zone file. Can be passed raw zone data on the API level.

    CLI Example:

    .. code-block:: bash

        salt ns1 dnsutil.parse_zone /var/lib/named/example.com.zone
    '''
    if zonefile:
        try:
            with salt.utils.fopen(zonefile, 'r') as fp_:
                zone = fp_.read()
        except Exception:
            pass

    if not zone:
        return 'Error: Zone data was not found'

    zonedict = {}
    mode = 'single'
    for line in zone.splitlines():
        comps = line.split(';')
        line = comps[0].strip()
        if not line:
            continue
        comps = line.split()
        if line.startswith('$'):
            zonedict[comps[0].replace('$', '')] = comps[1]
            continue
        if '(' in line and ')' not in line:
            mode = 'multi'
            multi = ''
        if mode == 'multi':
            multi += ' {0}'.format(line)
            if ')' in line:
                mode = 'single'
                line = multi.replace('(', '').replace(')', '')
            else:
                continue
        if 'ORIGIN' in zonedict.keys():
            comps = line.replace('@', zonedict['ORIGIN']).split()
        else:
            comps = line.split()
        if 'SOA' in line:
            if comps[1] != 'IN':
                comps.pop(1)
            zonedict['ORIGIN'] = comps[0]
            zonedict['NETWORK'] = comps[1]
            zonedict['SOURCE'] = comps[3]
            zonedict['CONTACT'] = comps[4].replace('.', '@', 1)
            zonedict['SERIAL'] = comps[5]
            zonedict['REFRESH'] = _to_seconds(comps[6])
            zonedict['RETRY'] = _to_seconds(comps[7])
            zonedict['EXPIRE'] = _to_seconds(comps[8])
            zonedict['MINTTL'] = _to_seconds(comps[9])
            continue
        if comps[0] == 'IN':
            comps.insert(0, zonedict['ORIGIN'])
        if not comps[0].endswith('.'):
            comps[0] = '{0}.{1}'.format(comps[0], zonedict['ORIGIN'])
        if comps[2] == 'NS':
            zonedict.setdefault('NS', []).append(comps[3])
        elif comps[2] == 'MX':
            if 'MX' not in zonedict.keys():
                zonedict.setdefault('MX', []).append({'priority': comps[3],
                                                      'host': comps[4]})
        else:
            zonedict.setdefault(comps[2], {})[comps[0]] = comps[3]
    return zonedict


def _to_seconds(time):
    '''
    Converts a time value to seconds.

    As per RFC1035 (page 45), max time is 1 week, so anything longer (or
    unreadable) will be set to one week (604800 seconds).
    '''
    time = time.upper()
    if 'H' in time:
        time = int(time.replace('H', '')) * 3600
    elif 'D' in time:
        time = int(time.replace('D', '')) * 86400
    elif 'W' in time:
        time = 604800
    else:
        try:
            time = int(time)
        except Exception:
            time = 604800
    if time > 604800:
        time = 604800
    return time


def _has_dig():
    '''
    The dig-specific functions have been moved into their own module, but
    because they are also DNS utilities, a compatibility layer exists. This
    function helps add that layer.
    '''
    return salt.utils.which('dig') is not None


def check_ip(ip_addr):
    '''
    Check that string ip_addr is a valid IP

    CLI Example:

    .. code-block:: bash

        salt ns1 dig.check_ip 127.0.0.1
    '''
    if _has_dig():
        return __salt__['dig.check_ip'](ip_addr)

    return 'This function requires dig, which is not currently available'


def A(host, nameserver=None):
    '''
    Return the A record for 'host'.

    Always returns a list.

    CLI Example:

    .. code-block:: bash

        salt ns1 dig.A www.google.com
    '''
    if _has_dig():
        return __salt__['dig.A'](host, nameserver)
    elif nameserver is None:
        # fall back to the socket interface, if we don't care who resolves
        try:
            (hostname, aliases, addresses) = socket.gethostbyname_ex(host)
            return addresses
        except socket.error:
            return 'Unabled to resolve {0}'.format(host)

    return 'This function requires dig, which is not currently available'


def NS(domain, resolve=True, nameserver=None):
    '''
    Return a list of IPs of the nameservers for ``domain``

    If 'resolve' is False, don't resolve names.

    CLI Example:

    .. code-block:: bash

        salt ns1 dig.NS google.com

    '''
    if _has_dig():
        return __salt__['dig.NS'](domain, resolve, nameserver)

    return 'This function requires dig, which is not currently available'


def SPF(domain, record='SPF', nameserver=None):
    '''
    Return the allowed IPv4 ranges in the SPF record for ``domain``.

    If record is ``SPF`` and the SPF record is empty, the TXT record will be
    searched automatically. If you know the domain uses TXT and not SPF,
    specifying that will save a lookup.

    CLI Example:

    .. code-block:: bash

        salt ns1 dig.SPF google.com
    '''
    if _has_dig():
        return __salt__['dig.SPF'](domain, record, nameserver)

    return 'This function requires dig, which is not currently available'


def MX(domain, resolve=False, nameserver=None):
    '''
    Return a list of lists for the MX of ``domain``.

    If the 'resolve' argument is True, resolve IPs for the servers.

    It's limited to one IP, because although in practice it's very rarely a
    round robin, it is an acceptable configuration and pulling just one IP lets
    the data be similar to the non-resolved version. If you think an MX has
    multiple IPs, don't use the resolver here, resolve them in a separate step.

    CLI Example:

    .. code-block:: bash

        salt ns1 dig.MX google.com
    '''
    if _has_dig():
        return __salt__['dig.MX'](domain, resolve, nameserver)

    return 'This function requires dig, which is not currently available'
