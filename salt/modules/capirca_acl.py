# -*- coding: utf-8 -*-
'''
Capirca ACL
============

Generate ACL (firewall) configuration for network devices.

.. versionadded:: Nitrogen

:codeauthor: Mircea Ulinic <mircea@cloudflare.com> & Robert Ankeny <robankeny@google.com>
:maturity:   new
:depends:    capirca
:platform:   unix

Dependencies
------------

The firewall configuration is generated by Capirca_.

.. _Capirca: https://github.com/google/capirca

Capirca is not yet available on PyPI threrefore it has to be installed
directly form Git: ``pip install -e git+git@github.com:google/capirca.git#egg=aclgen``.
'''
from __future__ import absolute_import

import re
import inspect
import logging
import datetime

log = logging.getLogger(__file__)

# Import third party libs
try:
    import aclgen
    HAS_CAPIRCA = True
except ImportError:
    HAS_CAPIRCA = False

# Import Salt modules
import salt.utils
from salt.ext import six

# ------------------------------------------------------------------------------
# module properties
# ------------------------------------------------------------------------------

__virtualname__ = 'capirca'
__proxyenabled__ = ['*']
# allow any proxy type

# ------------------------------------------------------------------------------
# property functions
# ------------------------------------------------------------------------------


def __virtual__():
    '''
    This module requires at least Capirca to work.
    '''
    if HAS_CAPIRCA:
        return __virtualname__
    else:
        return (False, 'The capirca module (capirca_acl) cannot be loaded.')

# ------------------------------------------------------------------------------
# module globals
# ------------------------------------------------------------------------------

# define the default values for all possible term fields
# we could also extract them from the `policy` module, inspecting the `Policy`
# class, but that might be overkill & it would make the code less obvious.
# we can revisit this later if necessary.
_TERM_FIELDS = {
    'action': [],
    'address': [],
    'address_exclude': [],
    'comment': [],
    'counter': None,
    'expiration': None,
    'destination_address': [],
    'destination_address_exclude': [],
    'destination_port': [],
    'destination_prefix': [],
    'forwarding_class': [],
    'forwarding_class_except': [],
    'logging': [],
    'log_name': None,
    'loss_priority': None,
    'option': [],
    'owner': None,
    'policer': None,
    'port': [],
    'precedence': [],
    'principals': [],
    'protocol': [],
    'protocol_except': [],
    'qos': None,
    'pan_application': [],
    'routing_instance': None,
    'source_address': [],
    'source_address_exclude': [],
    'source_port': [],
    'source_prefix': [],
    'verbatim': [],
    'packet_length': None,
    'fragment_offset': None,
    'hop_limit': None,
    'icmp_type': [],
    'ether_type': [],
    'traffic_class_count': None,
    'traffic_type': [],
    'translated': False,
    'dscp_set': None,
    'dscp_match': [],
    'dscp_except': [],
    'next_ip': None,
    'flexible_match_range': [],
    'source_prefix_except': [],
    'destination_prefix_except': [],
    'vpn': None,
    'source_tag': [],
    'destination_tag': [],
    'source_interface': None,
    'destination_interface': None,
    'platform': [],
    'platform_exclude': [],
    'timeout': None,
    'flattened': False,
    'flattened_addr': None,
    'flattened_saddr': None,
    'flattened_daddr': None
}

# IP-type fields
# when it comes to IP fields, Capirca does not ingest raw text
# but they need to be converted to `nacaddr.IP`
# this pre-processing is done in `_clean_term_opts`
_IP_FILEDS = [
    'source_address',
    'source_address_exclude',
    'destination_address',
    'address',
    'address_exclude',
    'flattened_addr',
    'flattened_saddr',
    'flattened_daddr',
    'next_ip'
]

_SERVICES = {}

# ------------------------------------------------------------------------------
# helper functions -- will not be exported
# ------------------------------------------------------------------------------


if HAS_CAPIRCA:
    class _Policy(aclgen.policy.Policy):
        '''
        Extending the Capirca Policy class to allow inserting custom filters.
        '''
        def __init__(self):
            self.filters = []
            self.filename = ''

    class _Term(aclgen.policy.Term):
        '''
        Extending the Capirca Term class to allow setting field valued on the fly.
        '''
        def __init__(self):
            for field, default in six.iteritems(_TERM_FIELDS):
                setattr(self, field, default)


def _import_platform_generator(platform):
    '''
    Given a specific platform (under the Capirca conventions),
    return the generator class.
    The generator class is identified looking under the <platform> module
    for a class inheriting the `ACLGenerator` class.
    '''
    log.debug('Using platform: {plat}'.format(plat=platform))
    for mod_name, mod_obj in inspect.getmembers(aclgen):
        if mod_name == platform and inspect.ismodule(mod_obj):
            for plat_obj_name, plat_obj in inspect.getmembers(mod_obj):  # pylint: disable=unused-variable
                if inspect.isclass(plat_obj) and issubclass(plat_obj, aclgen.aclgenerator.ACLGenerator):
                    log.debug('Identified Capirca class {cls} for {plat}'.format(
                        cls=plat_obj,
                        plat=platform))
                    return plat_obj
    log.error('Unable to identify any Capirca plaform class for {plat}'.format(plat=platform))


def _get_services_mapping():
    '''
    Build a map of services based on the IANA assignment list:
    http://www.iana.org/assignments/port-numbers

    It will load the /etc/services file and will build the mapping on the fly,
    similar to the Capirca's SERVICES file:
    https://github.com/google/capirca/blob/master/def/SERVICES.svc

    As this module is be available on Unix systems only,
    we'll read the services from /etc/services.
    In the worst case, the user will not be able to specify the
    services shortcut and they will need to specify the protocol / port combination
    using the source_port / destination_port & protocol fields.
    '''
    if _SERVICES:
        return _SERVICES
    global _SERVICES
    services_txt = ''
    try:
        with salt.utils.fopen('/etc/services', 'r') as srv_f:
            services_txt = srv_f.read()
    except IOError as ioe:
        log.error('Unable to read from /etc/services:')
        log.error(ioe)
        return _SERVICES  # no mapping possible, sorry
        # will return the default mapping
    service_rgx = re.compile(r'^([a-zA-Z0-9-]+)\s+(\d+)\/(tcp|udp)(.*)$')
    for line in services_txt.splitlines():
        service_rgx_s = service_rgx.search(line)
        if service_rgx_s and len(service_rgx_s.groups()) == 4:
            srv_name, port, protocol, _ = service_rgx_s.groups()
            if srv_name not in _SERVICES:
                _SERVICES[srv_name] = {
                    'port': [],
                    'protocol': []
                }
            try:
                _SERVICES[srv_name]['port'].append(int(port))
            except ValueError as verr:
                log.error(verr)
                log.error('Did not read that properly:')
                log.error(line)
                log.error('Please report the above error: {port} does not seem a valid port value!'.format(port=port))
            _SERVICES[srv_name]['protocol'].append(protocol)
    return _SERVICES


def _translate_port(port):
    '''
    Look into services and return the port value using the
    service name as lookup value.
    '''
    services = _get_services_mapping()
    if port in services and services[port]['port']:
        return services[port]['port'][0]
    return port


def _make_it_list(dict_, field_name, value):
    '''
    Return the object list.
    '''
    prev_value = []
    # firsly we'll collect the prev value
    if field_name in dict_:
        prev_value = dict_[field_name]
    if value is None:
        return prev_value
    elif isinstance(value, (tuple, list)):
        # other type of iterables
        if field_name in ('source_port', 'destination_port'):
            # port fields are more special
            # they can either be a list of integers, either a list of tuples
            # list of integers = a list of ports
            # list of tuples = a list of ranges,
            # e.g.: [(1000, 2000), (3000, 4000)] means the 1000-2000 and 3000-4000 ranges
            portval = []
            for port in value:
                if not isinstance(port, (tuple, list)):
                    # to make sure everything is consistent,
                    # we'll transform indivitual ports into tuples
                    # thus an individual port e.g. 1000 will be transormed into the port range 1000-1000
                    # which is the equivalent
                    # but assures consistency for the Capirca parser
                    portval.append((port, port))
                else:
                    portval.append(port)
            translated_portval = []
            # and the ports sent as string, e.g. ntp instead of 123
            # needs to be translated
            # again, using the same /etc/services
            for port_start, port_end in portval:
                if not isinstance(port_start, int):
                    port_start = _translate_port(port_start)
                if not isinstance(port_end, int):
                    port_end = _translate_port(port_end)
                translated_portval.append(
                    (port_start, port_end)
                )
            return list(set(prev_value + translated_portval))
        return list(set(prev_value + list(value)))
    if field_name in ('source_port', 'destination_port'):
        if not isinstance(value, int):
            value = _translate_port(value)
        return list(set(prev_value + [(value, value)]))  # a list of tuples
    # anything else will be enclosed in a list-type
    return list(set(prev_value + [value]))


def _clean_term_opts(term_opts):
    '''
    Cleanup the term opts:

    - strip Null and empty valuee, defaulting their value to their base definition from _TERM_FIELDS
    - convert to `nacaddr.IP` fields from `_IP_FILEDS`
    - create lists for those fields requiring it
    '''
    clean_opts = {}
    _services = _get_services_mapping()
    for field, value in six.iteritems(term_opts):
        # firstly we'll process special fields like source_service or destination_services
        # which will inject values directly in the source or destination port and protocol
        if field == 'source_service' and value:
            for service in value:
                if service and service in _services:
                    # if valid source_service
                    # take the port and protocol values from the global and inject in the term config
                    clean_opts['source_port'] = _make_it_list(clean_opts,
                                                              'source_port',
                                                              _services[service]['port'])
                    clean_opts['protocol'] = _make_it_list(clean_opts,
                                                           'protocol',
                                                           _services[service]['protocol'])
        elif field == 'destination_service' and value:
            for service in value:
                if service and service in _services:
                    # if valid destination_service
                    # take the port and protocol values from the global and inject in the term config
                    clean_opts['destination_port'] = _make_it_list(clean_opts,
                                                                   'destination_port',
                                                                   _services[service]['port'])
                    clean_opts['protocol'] = _make_it_list(clean_opts,
                                                           'protocol',
                                                           _services[service]['protocol'])
        # not a special field, but it has to be a valid one
        elif field in _TERM_FIELDS and value and value != _TERM_FIELDS[field]:
            # if not a special field type
            if isinstance(_TERM_FIELDS[field], list):
                value = _make_it_list(clean_opts, field, value)
            if field in _IP_FILEDS:
                # IP-type fields need to be transformed
                ip_values = []
                for addr in value:
                    ip_values.append(aclgen.policy.nacaddr.IP(addr))
                value = ip_values[:]
            clean_opts[field] = value
    return clean_opts


def _get_pillar_cfg(pillar_key,
                    pillarenv=None,
                    saltenv=None):
    '''
    Retrieve the pillar data from the right environment.
    '''
    pillar_cfg = __salt__['pillar.get'](pillar_key,
                                        pillarenv=pillarenv,
                                        saltenv=saltenv)
    if not isinstance(pillar_cfg, dict):
        return {}
    return pillar_cfg


def _merge_dict(source, dest):
    '''
    Merge dictionaries.
    '''
    if not source:
        source = dest
    elif source.keys() != dest.keys():
        source_keys = set(source.keys())
        dest_keys = set(dest.keys())
        merge_keys = dest_keys - source_keys
        for key in merge_keys:
            source[key] = dest[key]
    return source


def _get_term_object(filter_name,
                     term_name,
                     pillar_key='acl',
                     pillarenv=None,
                     saltenv=None,
                     merge_pillar=True,
                     **term_fields):
    '''
    Return an instance of the ``_Term`` class given the term options.
    '''
    log.debug('Generating config for term {tname} under filter {fname}'.format(
        tname=term_name,
        fname=filter_name
    ))
    term = _Term()
    term.name = term_name
    term_opts = {}
    if merge_pillar:
        term_pillar_key = ':'.join((pillar_key, filter_name, term_name))
        term_opts = _get_pillar_cfg(term_pillar_key,
                                    saltenv=saltenv,
                                    pillarenv=pillarenv)
        log.debug('Merging with pillar data:')
        log.debug(term_opts)
        term_opts = _clean_term_opts(term_opts)
        log.debug('Cleaning up pillar data:')
        log.debug(term_opts)
    log.debug('Received processing opts:')
    log.debug(term_fields)
    log.debug('Cleaning up processing opts:')
    term_fields = _clean_term_opts(term_fields)
    log.debug(term_fields)
    log.debug('Final term opts:')
    term_opts.update(term_fields)
    log.debug(term_fields)
    for field, value in six.iteritems(term_opts):
        # setting the field attributes to the term instance of _Term
        setattr(term, field, value)
    log.debug('Term config:')
    log.debug(str(term))
    return term


def _get_policy_object(platform,
                       filters=None,
                       pillar_key='acl',
                       pillarenv=None,
                       saltenv=None,
                       merge_pillar=True):
    '''
    Return an instance of the ``_Policy`` class given the filters config.
    '''
    policy = _Policy()
    policy_filters = []
    if not filters:
        filters = {}
    for filter_name, filter_config in six.iteritems(filters):
        header = aclgen.policy.Header()  # same header everywhere
        target_opts = [
            platform,
            filter_name
        ]
        filter_options = filter_config.pop('options', None)
        if filter_options:
            filter_options = _make_it_list(filter_options, filter_name, filter_options)
            # make sure the filter options are sent as list
            target_opts.extend(filter_options)
        target = aclgen.policy.Target(target_opts)
        header.AddObject(target)
        filter_terms = []
        for term_name, term_fields in six.iteritems(filter_config):
            term = _get_term_object(filter_name,
                                    term_name,
                                    pillar_key=pillar_key,
                                    pillarenv=pillarenv,
                                    saltenv=saltenv,
                                    merge_pillar=merge_pillar,
                                    **term_fields)
            filter_terms.append(term)
        policy_filters.append(
            (header, filter_terms)
        )
    policy.filters = policy_filters
    log.debug('Policy config:')
    log.debug(str(policy))
    platform_generator = _import_platform_generator(platform)
    policy_config = platform_generator(policy, 2)
    log.debug('Generating policy config for {platform}:'.format(
        platform=platform))
    log.debug(str(policy_config))
    return policy_config


def _revision_tag(text,
                  revision_id=None,
                  revision_no=None,
                  revision_date=True,
                  revision_date_format='%Y/%m/%d'):
    '''
    Refactor revision tag comments.
    Capirca generates the filter text having the following tag keys:

    - $Id:$
    - $Revision:$
    - $Date:$

    This function goes through all the config lines and replaces
    those tags with the content requested by the user.
    If a certain value is not provided, the corresponding tag will be stripped.
    '''
    timestamp = datetime.datetime.now().strftime(revision_date_format)
    new_text = []
    for line in text.splitlines():
        if '$Id:$' in line:
            if not revision_id:  # if no explicit revision ID required
                continue  # jump to next line, ignore this one
            line = line.replace('$Id:$', '$Id: {rev_id} $'.format(rev_id=revision_id))
        if '$Revision:$' in line:
            if not revision_no:  # if no explicit revision number required
                continue  # jump to next line, ignore this one
            line = line.replace('$Revision:$', '$Revision: {rev_no} $'.format(rev_no=revision_no))
        if '$Date:$' in line:
            if not revision_date:
                continue  # jump
            line = line.replace('$Date:$', '$Date: {ts} $'.format(ts=timestamp))
        new_text.append(line)
    return '\n'.join(new_text)

# ------------------------------------------------------------------------------
# callable functions
# ------------------------------------------------------------------------------


def get_term_config(platform,
                    filter_name,
                    term_name,
                    filter_options=None,
                    pillar_key='acl',
                    pillarenv=None,
                    saltenv=None,
                    merge_pillar=True,
                    revision_id=None,
                    revision_no=None,
                    revision_date=True,
                    revision_date_format='%Y/%m/%d',
                    source_service=None,
                    destination_service=None,
                    **term_fields):
    '''
    Return the configuration of a single policy term.

    platform
        The name of the Capirca platform.

    filter_name
        The name of the policy filter.

    term_name
        The name of the term.

    filter_options
        Additional filter options. These options are platform-specific.
        E.g.: ``inet6``, ``bridge``, ``object-group``,
        See the complete list of options_.

        .. _options: https://github.com/google/capirca/wiki/Policy-format#header-section

    pillar_key: ``acl``
        The key in the pillar containing the default attributes values. Default: ``acl``.
        If the pillar contains the following structure:

        .. code-block:: yaml

            firewall:
                my-filter:
                    my-term:
                        source_port: 1234
                        source_address:
                            - 1.2.3.4/32
                            - 5.6.7.8/32

        The ``pillar_key`` field would be specified as ``firewall``.

    pillarenv
        Query the master to generate fresh pillar data on the fly,
        specifically from the requested pillar environment.

    saltenv
        Included only for compatibility with
        :conf_minion:`pillarenv_from_saltenv`, and is otherwise ignored.

    merge_pillar: ``True``
        Merge the CLI variables with the pillar. Default: ``True``.

    revision_id
        Add a comment in the term config having the description for the changes applied.

    revision_no
        The revision count.

    revision_date: ``True``
        Boolean flag: display the date when the term configuration was generated. Default: ``True``.

    revision_date_format: ``%Y/%m/%d``
        The date format to be used when generating the perforce data. Default: ``%Y/%m/%d`` (<year>/<month>/<day>).

    source_service
        A special service to choose from. This is a helper so the user is able to
        select a source just using the name, instead of specifying a source_port and protocol.

        As this module is available on Unix platforms only,
        it reads the IANA_ port assignment from ``/etc/services``.

        If the user requires additional shortcuts to be referenced, they can add entries under ``/etc/services``,
        which can be managed using the :mod:`file state <salt.states.file>`.

        .. _IANA: http://www.iana.org/assignments/port-numbers

    destination_service
        A special service to choose from. This is a helper so the user is able to
        select a source just using the name, instead of specifying a destination_port and protocol.
        Allows the same options as ``source_service``.

    **term_fields
        Term attributes.
        To see what fields are supported, please consult the list of supported keywords_.
        Some platforms have few other optional_ keywords.

        .. _keywords: https://github.com/google/capirca/wiki/Policy-format#keywords
        .. _optional: https://github.com/google/capirca/wiki/Policy-format#optionally-supported-keywords

    .. note::
        The following fields are accepted:

        - action
        - address
        - address_exclude
        - comment
        - counter
        - expiration
        - destination_address
        - destination_address_exclude
        - destination_port
        - destination_prefix
        - forwarding_class
        - forwarding_class_except
        - logging
        - log_name
        - loss_priority
        - option
        - policer
        - port
        - precedence
        - principals
        - protocol
        - protocol_except
        - qos
        - pan_application
        - routing_instance
        - source_address
        - source_address_exclude
        - source_port
        - source_prefix
        - verbatim
        - packet_length
        - fragment_offset
        - hop_limit
        - icmp_type
        - ether_type
        - traffic_class_count
        - traffic_type
        - translated
        - dscp_set
        - dscp_match
        - dscp_except
        - next_ip
        - flexible_match_range
        - source_prefix_except
        - destination_prefix_except
        - vpn
        - source_tag
        - destination_tag
        - source_interface
        - destination_interface
        - flattened
        - flattened_addr
        - flattened_saddr
        - flattened_daddr

    .. note::
        The following fields can be also a single value and a list of values:

        - action
        - address
        - address_exclude
        - comment
        - destination_address
        - destination_address_exclude
        - destination_port
        - destination_prefix
        - forwarding_class
        - forwarding_class_except
        - logging
        - option
        - port
        - precedence
        - principals
        - protocol
        - protocol_except
        - pan_application
        - source_address
        - source_address_exclude
        - source_port
        - source_prefix
        - verbatim
        - icmp_type
        - ether_type
        - traffic_type
        - dscp_match
        - dscp_except
        - flexible_match_range
        - source_prefix_except
        - destination_prefix_except
        - source_tag
        - destination_tag
        - source_service
        - destination_service

        Example: ``destination_address`` can be either defined as:

        .. code-block:: yaml

            destination_address: 172.17.17.1/24

        or as a list of destination IP addresses:

        .. code-block:: yaml

            destination_address:
                - 172.17.17.1/24
                - 172.17.19.1/24

        or a list of services to be matched:

        .. code-block:: yaml

            source_service:
                - ntp
                - snmp
                - ldap
                - bgpd

    .. note::
        The port fields ``source_port`` and ``destination_port`` can be used as above to select either
        a single value, either a list of values, but also they can select port ranges. Example:

        .. code-block:: yaml

            source_port:
                - [1000, 2000]
                - [3000, 4000]

        With the configuration above, the user is able to select the 1000-2000 and 3000-4000 source port ranges.

    CLI Example:

    .. code-block:: bash

        salt '*' capirca.get_term_config arista filter-name term-name source_address=1.2.3.4 destination_address=5.6.7.8 action=accept

    Output Example:

    .. code-block:: text

        ! $Id:$
        ! $Date:$
        ! $Revision:$
        no ip access-list filter-name
        ip access-list filter-name
         remark $Id:$
         remark term-name
         permit ip host 1.2.3.4 host 5.6.7.8
        exit
    '''
    terms = {
        term_name: {
        }
    }
    terms[term_name].update(term_fields)
    terms[term_name].update({
        'source_service': _make_it_list({}, 'source_service', source_service),
        'destination_service': _make_it_list({}, 'destination_service', destination_service),
    })
    if not filter_options:
        filter_options = []
    return get_filter_config(platform,
                             filter_name,
                             filter_options=filter_options,
                             terms=terms,
                             pillar_key=pillar_key,
                             pillarenv=pillarenv,
                             saltenv=saltenv,
                             merge_pillar=merge_pillar,
                             only_lower_merge=True,
                             revision_id=revision_id,
                             revision_no=revision_no,
                             revision_date=revision_date,
                             revision_date_format=revision_date_format)


def get_filter_config(platform,
                      filter_name,
                      filter_options=None,
                      terms=None,
                      pillar_key='acl',
                      pillarenv=None,
                      saltenv=None,
                      merge_pillar=True,
                      only_lower_merge=False,
                      revision_id=None,
                      revision_no=None,
                      revision_date=True,
                      revision_date_format='%Y/%m/%d'):
    '''
    Return the configuration of a policy filter.

    platform
        The name of the Capirca platform.

    filter_name
        The name of the policy filter.

    filter_options
        Additional filter options. These options are platform-specific.
        See the complete list of options_.

        .. _options: https://github.com/google/capirca/wiki/Policy-format#header-section

    terms
        Dictionary of terms for this policy filter.
        If not specified or empty, will try to load the configuration from the pillar,
        unless ``merge_pillar`` is set as ``False``.

    pillar_key: ``acl``
        The key in the pillar containing the default attributes values. Default: ``acl``.

    pillarenv
        Query the master to generate fresh pillar data on the fly,
        specifically from the requested pillar environment.

    saltenv
        Included only for compatibility with
        :conf_minion:`pillarenv_from_saltenv`, and is otherwise ignored.

    merge_pillar: ``True``
        Merge the CLI variables with the pillar. Default: ``True``

    only_lower_merge: ``False``
        Specify if it should merge only the terms fields. Otherwise it will try
        to merge also filters fields. Default: ``False``.

    revision_id
        Add a comment in the filter config having the description for the changes applied.

    revision_no
        The revision count.

    revision_date: ``True``
        Boolean flag: display the date when the filter configuration was generated. Default: ``True``.

    revision_date_format: ``%Y/%m/%d``
        The date format to be used when generating the perforce data. Default: ``%Y/%m/%d`` (<year>/<month>/<day>).

    CLI Example:

    .. code-block:: bash

        salt '*' capirca.get_filter_config ciscoxr my-filter pillar_key=netacl

    Output Example:

    .. code-block:: text

        ! $Id:$
        ! $Date:$
        ! $Revision:$
        no ipv4 access-list my-filter
        ipv4 access-list my-filter
         remark $Id:$
         remark my-term
         deny ipv4 any eq 1234 any
         deny ipv4 any eq 1235 any
         remark my-other-term
         permit tcp any range 5678 5680 any
        exit

    The filter configuration has been loaded from the pillar, having the following structure:

    .. code-block:: yaml

        netacl:
          my-filter:
            my-term:
              source_port: [1234, 1235]
              action: reject
            my-other-term:
              source_port:
                - [5678, 5680]
              protocol: tcp
              action: accept
    '''
    if not filter_options:
        filter_options = []
    if not terms:
        terms = {}
    if merge_pillar and not only_lower_merge:
        filter_pillar_key = ':'.join((pillar_key, filter_name))
        filter_pillar_cfg = _get_pillar_cfg(filter_pillar_key)
        filter_options = filter_options or filter_pillar_cfg.pop('options', None)
        terms = _merge_dict(terms, filter_pillar_cfg)
        # merge the passed variable with the pillar data
        # any filter term not defined here, will be appended from the pillar
        # new terms won't be removed
    filters = {
        filter_name: {
            'options': _make_it_list(filter_options, filter_name, filter_options)
        }
    }
    filters[filter_name].update(terms)
    return get_policy_config(platform,
                             filters=filters,
                             pillar_key=pillar_key,
                             pillarenv=pillarenv,
                             saltenv=saltenv,
                             merge_pillar=merge_pillar,
                             only_lower_merge=True,
                             revision_id=revision_id,
                             revision_no=revision_no,
                             revision_date=revision_date,
                             revision_date_format=revision_date_format)


def get_policy_config(platform,
                      filters=None,
                      pillar_key='acl',
                      pillarenv=None,
                      saltenv=None,
                      merge_pillar=True,
                      only_lower_merge=False,
                      revision_id=None,
                      revision_no=None,
                      revision_date=True,
                      revision_date_format='%Y/%m/%d'):
    '''
    Return the configuration of the whole policy.

    platform
        The name of the Capirca platform.

    filters
        Dictionary of filters for this policy.
        If not specified or empty, will try to load the configuration from the pillar,
        unless ``merge_pillar`` is set as ``False``.

    pillar_key: ``acl``
        The key in the pillar containing the default attributes values. Default: ``acl``.

    pillarenv
        Query the master to generate fresh pillar data on the fly,
        specifically from the requested pillar environment.

    saltenv
        Included only for compatibility with
        :conf_minion:`pillarenv_from_saltenv`, and is otherwise ignored.

    merge_pillar: ``True``
        Merge the CLI variables with the pillar. Default: ``True``.

    only_lower_merge: ``False``
        Specify if it should merge only the filters and terms fields. Otherwise it will try
        to merge everything at the policy level. Default: ``False``.

    revision_id
        Add a comment in the policy config having the description for the changes applied.

    revision_no
        The revision count.

    revision_date: ``True``
        Boolean flag: display the date when the policy configuration was generated. Default: ``True``.

    revision_date_format: ``%Y/%m/%d``
        The date format to be used when generating the perforce data. Default: ``%Y/%m/%d`` (<year>/<month>/<day>).

    CLI Example:

    .. code-block:: bash

        salt '*' capirca.get_policy_config juniper pillar_key=netacl

    Output Example:

    .. code-block:: text

        firewall {
            family inet {
                replace:
                /*
                ** $Id:$
                ** $Date:$
                ** $Revision:$
                **
                */
                filter my-other-filter {
                    interface-specific;
                    term dummy-term {
                        from {
                            protocol [ tcp udp ];
                        }
                        then {
                            reject;
                        }
                    }
                }
            }
        }
        firewall {
            family inet {
                replace:
                /*
                ** $Id:$
                ** $Date:$
                ** $Revision:$
                **
                */
                filter my-filter {
                    interface-specific;
                    term my-term {
                        from {
                            source-port [ 1234 1235 ];
                        }
                        then {
                            reject;
                        }
                    }
                    term my-other-term {
                        from {
                            protocol tcp;
                            source-port 5678-5680;
                        }
                        then accept;
                    }
                }
            }
        }

    The policy configuration has been loaded from the pillar, having the following structure:

    .. code-block:: yaml

        netacl:
          my-filter:
            my-term:
              source_port: [1234, 1235]
              action: reject
            my-other-term:
              source_port:
                - [5678, 5680]
              protocol: tcp
              action: accept
          my-other-filter:
            dummy-term:
              protocol:
                - tcp
                - udp
              action: reject
    '''
    if not filters:
        filters = {}
    if merge_pillar and not only_lower_merge:
        # the pillar key for the policy config is the `pillar_key` itself
        policy_pillar_cfg = _get_pillar_cfg(pillar_key)
        # now, let's merge everything witht the pillar data
        # again, this will not remove any extra filters/terms
        # but it will merge with the pillar data
        # if this behaviour is not wanted, the user can set `merge_pillar` as `False`
        filters = _merge_dict(filters, policy_pillar_cfg)
    policy_object = _get_policy_object(platform,
                                       filters=filters,
                                       pillar_key=pillar_key,
                                       pillarenv=pillarenv,
                                       saltenv=saltenv,
                                       merge_pillar=merge_pillar)
    policy_text = str(policy_object)
    return _revision_tag(policy_text,
                         revision_id=revision_id,
                         revision_no=revision_no,
                         revision_date=revision_date,
                         revision_date_format=revision_date_format)
