# -*- coding: utf-8 -*-
'''
Module for managing IIS SMTP server configuration on Windows servers.
The Windows features 'SMTP-Server' and 'Web-WMI' must be installed.

:depends:
        - wmi
'''

#   IIS metabase configuration settings:
#     https://goo.gl/XCt1uO
#   IIS logging options:
#     https://goo.gl/RL8ki9
#     https://goo.gl/iwnDow
#   MicrosoftIISv2 namespace in Windows 2008r2 and later:
#     http://goo.gl/O4m48T
#   Connection and relay IPs in PowerShell:
#     https://goo.gl/aBMZ9K
#     http://goo.gl/MrybFq

# Import python libs
from __future__ import absolute_import
import logging
import re
# Import salt libs
from salt.exceptions import SaltInvocationError
import salt.utils

try:
    import wmi
    import salt.utils.winapi
    _HAS_MODULE_DEPENDENCIES = True
except ImportError:
    _HAS_MODULE_DEPENDENCIES = False

_DEFAULT_SERVER = 'SmtpSvc/1'
_WMI_NAMESPACE = 'MicrosoftIISv2'
_LOG = logging.getLogger(__name__)

# Define the module's virtual name
__virtualname__ = 'win_smtp_server'


def __virtual__():
    '''
    Only works on Windows systems.
    '''
    if salt.utils.is_windows() and _HAS_MODULE_DEPENDENCIES:
        return __virtualname__
    return False


def _get_wmi_setting(wmi_class_name, setting, server):
    '''
    Get the value of the setting for the provided class.
    '''
    with salt.utils.winapi.Com():
        try:
            connection = wmi.WMI(namespace=_WMI_NAMESPACE)
            wmi_class = getattr(connection, wmi_class_name)

            settings = wmi_class([setting], Name=server)[0]
            ret = getattr(settings, setting)
        except wmi.x_wmi as error:
            _LOG.error('Encountered WMI error: %s', error.com_error)
        except (AttributeError, IndexError) as error:
            _LOG.error('Error getting %s: %s', wmi_class_name, error)
    return ret


def _set_wmi_setting(wmi_class_name, setting, value, server):
    '''
    Set the value of the setting for the provided class.
    '''
    with salt.utils.winapi.Com():
        try:
            connection = wmi.WMI(namespace=_WMI_NAMESPACE)
            wmi_class = getattr(connection, wmi_class_name)

            settings = wmi_class(Name=server)[0]
        except wmi.x_wmi as error:
            _LOG.error('Encountered WMI error: %s', error.com_error)
        except (AttributeError, IndexError) as error:
            _LOG.error('Error getting %s: %s', wmi_class_name, error)

        try:
            setattr(settings, setting, value)
            return True
        except wmi.x_wmi as error:
            _LOG.error('Encountered WMI error: %s', error.com_error)
        except AttributeError as error:
            _LOG.error('Error setting %s: %s', setting, error)
    return False


def _normalize_connection_ips(*args):
    '''
    Fix connection address formatting. Consolidate extra spaces and convert to a standard string.
    '''
    ret = list()
    reg_separator = r',\s*'

    for arg in args:
        if not re.search(reg_separator, arg):
            message = ("Connection IP '{0}' is not in a valid format. Address should"
                       " be formatted like: 'ip_address, subnet'").format(arg)
            raise SaltInvocationError(message)

        ip_address, subnet = re.split(reg_separator, arg)
        ret.append('{0}, {1}'.format(ip_address, subnet))
    return ret


def _normalize_server_settings(**kwargs):
    '''
    Convert setting values that has been improperly converted to a dict back to a string.
    '''
    ret = dict()
    kwargs = salt.utils.clean_kwargs(**kwargs)

    for key in kwargs:
        if isinstance(kwargs[key], dict):
            _LOG.debug('Fixing value: %s', kwargs[key])
            ret[key] = "{{{0}}}".format(next(kwargs[key].iterkeys()))
        else:
            _LOG.debug('No fix necessary for value: %s', kwargs[key])
            ret[key] = kwargs[key]
    return ret


def get_log_format_types():
    '''
    Get all available log format names and ids.

    :return: A dictionary of the log format names and ids.

    CLI Example:

    .. code-block:: bash

        salt '*' win_smtp_server.get_log_format_types
    '''
    ret = dict()
    prefix = 'logging/'

    with salt.utils.winapi.Com():
        try:
            connection = wmi.WMI(namespace=_WMI_NAMESPACE)
            settings = connection.IISLogModuleSetting()

            # Remove the prefix from the name.
            for setting in settings:
                name = str(setting.Name).replace(prefix, '', 1)
                ret[name] = str(setting.LogModuleId)
        except wmi.x_wmi as error:
            _LOG.error('Encountered WMI error: %s', error.com_error)
        except (AttributeError, IndexError) as error:
            _LOG.error('Error getting IISLogModuleSetting: %s', error)

    if not ret:
        _LOG.error('Unable to get log format types.')
    return ret


def get_servers():
    '''
    Get the SMTP virtual server names.

    :return: A list of the SMTP virtual servers.

    CLI Example:

    .. code-block:: bash

        salt '*' win_smtp_server.get_servers
    '''
    ret = list()

    with salt.utils.winapi.Com():
        try:
            connection = wmi.WMI(namespace=_WMI_NAMESPACE)
            settings = connection.IIsSmtpServerSetting()

            for server in settings:
                ret.append(str(server.Name))
        except wmi.x_wmi as error:
            _LOG.error('Encountered WMI error: %s', error.com_error)
        except (AttributeError, IndexError) as error:
            _LOG.error('Error getting IIsSmtpServerSetting: %s', error)

    _LOG.debug('Found SMTP servers: %s', ret)
    return ret


def get_server_setting(*args, **kwargs):
    '''
    Get the value of the setting for the SMTP virtual server.

    :param args: The setting names.

    *Keyword Arguments (kwargs)*

    :param server: The SMTP server name.

    :return: dictionary of the provided settings and their values.

    CLI Example:

    .. code-block:: bash

        salt '*' win_smtp_server.get_server_setting 'MaxRecipients'
    '''
    ret = dict()
    server = kwargs.pop('server', _DEFAULT_SERVER)

    if not args:
        _LOG.warning('No settings provided.')
        return ret

    with salt.utils.winapi.Com():
        try:
            connection = wmi.WMI(namespace=_WMI_NAMESPACE)
            settings = connection.IIsSmtpServerSetting(args, Name=server)[0]

            for arg in args:
                ret[arg] = str(getattr(settings, arg))
        except wmi.x_wmi as error:
            _LOG.error('Encountered WMI error: %s', error.com_error)
        except (AttributeError, IndexError) as error:
            _LOG.error('Error getting IIsSmtpServerSetting: %s', error)
    return ret


def set_server_setting(**kwargs):
    '''
    Set the value of the setting for the SMTP virtual server.
    The setting names are case-sensitive.

    :param kwargs: The setting names and their values.
    :param server: The SMTP server name.

    :return: A boolean representing whether all changes succeeded.

    CLI Example:

    .. code-block:: bash

        salt '*' win_smtp_server.set_server_setting 'MaxRecipients'='500'
    '''
    kwargs = salt.utils.clean_kwargs(**kwargs)
    server = kwargs.pop('server', _DEFAULT_SERVER)

    if not kwargs:
        _LOG.warning('No settings provided')
        return False

    # Some fields are formatted like '{data}'. Salt tries to convert these to dicts
    # automatically on input, so convert them back to the proper format.
    kwargs = _normalize_server_settings(**kwargs)

    current_settings = get_server_setting(*kwargs.keys(), **{'server': server})

    if kwargs == current_settings:
        _LOG.debug('Settings already contain the provided values.')
        return True

    # Note that we must fetch all properties of IIsSmtpServerSetting below, since
    # filtering for specific properties and then attempting to set them will cause
    # an error like: wmi.x_wmi Unexpected COM Error -2147352567
    with salt.utils.winapi.Com():
        try:
            connection = wmi.WMI(namespace=_WMI_NAMESPACE)
            settings = connection.IIsSmtpServerSetting(Name=server)[0]
        except wmi.x_wmi as error:
            _LOG.error('Encountered WMI error: %s', error.com_error)
        except (AttributeError, IndexError) as error:
            _LOG.error('Error getting IIsSmtpServerSetting: %s', error)

        for key in kwargs:
            if str(kwargs[key]) != str(current_settings[key]):
                try:
                    setattr(settings, key, kwargs[key])
                except wmi.x_wmi as error:
                    _LOG.error('Encountered WMI error: %s', error.com_error)
                except AttributeError as error:
                    _LOG.error('Error setting %s: %s', key, error)

    # Get the settings post-change so that we can verify tht all properties
    # were modified successfully. Track the ones that weren't.
    new_settings = get_server_setting(*kwargs.keys(), **{'server': server})
    failed_settings = dict()

    for key in kwargs:
        if str(kwargs[key]) != str(new_settings[key]):
            failed_settings[key] = kwargs[key]
    if failed_settings:
        _LOG.error('Failed to change settings: %s', failed_settings)
        return False

    _LOG.debug('Settings configured successfully: %s', kwargs.keys())
    return True


def get_log_format(server=_DEFAULT_SERVER):
    '''
    Get the active log format for the SMTP virtual server.

    :param server: The SMTP server name.

    :return: A string of the log format name.

    CLI Example:

    .. code-block:: bash

        salt '*' win_smtp_server.get_log_format
    '''
    log_format_types = get_log_format_types()
    format_id = _get_wmi_setting('IIsSmtpServerSetting', 'LogPluginClsid', server)

    # Since IIsSmtpServerSetting stores the log type as an id, we need
    # to get the mapping from IISLogModuleSetting and extract the name.
    for key in log_format_types:
        if str(format_id) == log_format_types[key]:
            return key
    _LOG.warning('Unable to determine log format.')
    return None


def set_log_format(log_format, server=_DEFAULT_SERVER):
    '''
    Set the active log format for the SMTP virtual server.

    :param log_format: The log format name.
    :param server: The SMTP server name.

    :return: A boolean representing whether the change succeeded.

    CLI Example:

    .. code-block:: bash

        salt '*' win_smtp_server.set_log_format 'Microsoft IIS Log File Format'
    '''
    setting = 'LogPluginClsid'
    log_format_types = get_log_format_types()
    format_id = log_format_types.get(log_format, None)

    if not format_id:
        message = ("Invalid log format '{0}' specified. Valid formats:"
                   ' {1}').format(log_format, log_format_types.keys())
        raise SaltInvocationError(message)

    _LOG.debug("Id for '%s' found: %s", log_format, format_id)

    current_log_format = get_log_format(server)

    if log_format == current_log_format:
        _LOG.debug('%s already contains the provided format.', setting)
        return True

    _set_wmi_setting('IIsSmtpServerSetting', setting, format_id, server)

    new_log_format = get_log_format(server)
    ret = log_format == new_log_format

    if ret:
        _LOG.debug("Setting %s configured successfully: %s", setting, log_format)
    else:
        _LOG.error("Unable to configure %s with value: %s", setting, log_format)
    return ret


def get_connection_ip_list(server=_DEFAULT_SERVER):
    '''
    Get the IPGrant list for the SMTP virtual server.

    :param server: The SMTP server name.

    :return: A list of the IP and subnet pairs.

    CLI Example:

    .. code-block:: bash

        salt '*' win_smtp_server.get_connection_ip_list
    '''
    ret = list()
    setting = 'IPGrant'

    lines = _get_wmi_setting('IIsIPSecuritySetting', setting, server)

    # WMI returns the addresses as a tuple of unicode strings, each representing
    # an address/subnet pair. Remove extra spaces that may be present.
    ret = _normalize_connection_ips(*lines)

    if not ret:
        _LOG.debug('%s is empty.', setting)
    return ret


def set_connection_ip_list(*args, **kwargs):
    '''
    Set the IPGrant list for the SMTP virtual server.

    :param args: The IP + subnet pairs, formatted as 'ip_address, netmask' per pair.

    *Keyword Arguments (kwargs)*

    :param grant_by_default: Whether the args should be a blacklist or whitelist.
    :param server: The SMTP server name.

    :return: A boolean representing whether the change succeeded.

    CLI Example:

    .. code-block:: bash

        salt '*' win_smtp_server.set_connection_ip_list '127.0.0.1, 255.255.255.255'
    '''
    setting = 'IPGrant'
    server = kwargs.pop('server', _DEFAULT_SERVER)
    grant_by_default = kwargs.pop('grant_by_default', False)

    # It's okay to accept an empty list for set_connection_ip_list,
    # since an empty list may be desirable.
    if not args:
        _LOG.debug('Empty %s specified.', setting)

    # Remove any extra spaces that may be present.
    addresses = _normalize_connection_ips(*args)

    current_addresses = get_connection_ip_list(server)

    # Order is not important, so compare to the current addresses as unordered sets.
    if set(addresses) == set(current_addresses):
        _LOG.debug('%s already contains the provided addresses.', setting)
        return True

    # First we should check GrantByDefault, and change it if necessary.
    current_grant_by_default = _get_wmi_setting('IIsIPSecuritySetting', 'GrantByDefault', server)

    if grant_by_default != current_grant_by_default:
        _LOG.debug('Setting GrantByDefault to: %s', grant_by_default)
        _set_wmi_setting('IIsIPSecuritySetting', 'GrantByDefault', grant_by_default, server)

    _set_wmi_setting('IIsIPSecuritySetting', setting, addresses, server)

    new_addresses = get_connection_ip_list(server)
    ret = set(addresses) == set(new_addresses)

    if ret:
        _LOG.debug('%s configured successfully: %s', setting, args)
        return ret
    _LOG.error('Unable to configure %s with value: %s', setting, args)
    return ret


def get_relay_ip_list(server=_DEFAULT_SERVER):
    '''
    Get the RelayIpList list for the SMTP virtual server.

    :param server: The SMTP server name.

    :return: A list of the relay IPs.

    A return value of None corresponds to the restrictive 'Only the list below' GUI parameter
    with an empty access list, and setting an empty list/tuple corresponds to the more
    permissive 'All except the list below' GUI parameter.

    CLI Example:

    .. code-block:: bash

        salt '*' win_smtp_server.get_relay_ip_list
    '''
    ret = list()
    setting = 'RelayIpList'

    lines = _get_wmi_setting('IIsSmtpServerSetting', setting, server)

    if not lines:
        _LOG.debug('%s is empty: %s', setting, lines)
        if lines is None:
            lines = [None]
        return list(lines)

    # WMI returns the addresses as a tuple of individual octets, so we
    # need to group them and reassemble them into IP addresses.
    i = 0
    while i < len(lines):
        octets = [str(x) for x in lines[i: i + 4]]
        address = '.'.join(octets)
        ret.append(address)
        i += 4
    return ret


def set_relay_ip_list(*args, **kwargs):
    '''
    Set the RelayIpList list for the SMTP virtual server.

    Due to the unusual way that Windows stores the relay IPs, it is advisable to retrieve
    the existing list you wish to set from a pre-configured server.

    For example, setting '127.0.0.1' as an allowed relay IP through the GUI would generate
    an actual relay IP list similar to the following:

    .. code-block:: cfg

        ['24.0.0.128', '32.0.0.128', '60.0.0.128', '68.0.0.128', '1.0.0.0', '76.0.0.0',
         '0.0.0.0', '0.0.0.0', '1.0.0.0', '1.0.0.0', '2.0.0.0', '2.0.0.0', '4.0.0.0',
         '0.0.0.0', '76.0.0.128', '0.0.0.0', '0.0.0.0', '0.0.0.0', '0.0.0.0',
         '255.255.255.255', '127.0.0.1']

    Setting the list to None corresponds to the restrictive 'Only the list below' GUI parameter
    with an empty access list configured, and setting an empty list/tuple corresponds to the
    more permissive 'All except the list below' GUI parameter.

    :param args: The relay IPs.

    *Keyword Arguments (kwargs)*

    :param server: The SMTP server name.

    :return: A boolean representing whether the change succeeded.

    CLI Example:

    .. code-block:: bash

        salt '*' win_smtp_server.set_relay_ip_list '192.168.1.1' '172.16.1.1'
    '''
    setting = 'RelayIpList'
    server = kwargs.pop('server', _DEFAULT_SERVER)
    formatted_addresses = list()

    current_addresses = get_relay_ip_list(server)

    if list(args) == current_addresses:
        _LOG.debug('%s already contains the provided addresses.', setting)
        return True

    if args:
        # The WMI input data needs to be in the format used by RelayIpList. Order
        # is also important due to the way RelayIpList orders the address list.

        if args[0] is None:
            formatted_addresses = None
        else:
            for arg in args:
                for octet in arg.split('.'):
                    formatted_addresses.append(octet)

    _LOG.debug('Formatted %s addresses: %s', setting, formatted_addresses)

    _set_wmi_setting('IIsSmtpServerSetting', setting, formatted_addresses, server)

    new_addresses = get_relay_ip_list(server)

    ret = list(args) == new_addresses

    if ret:
        _LOG.debug('%s configured successfully: %s', setting, args)
        return ret
    _LOG.error('Unable to configure %s with value: %s', setting, args)
    return ret
