# -*- coding: utf-8 -*-
'''
Manage VMware vCenter servers and ESXi hosts.

.. versionadded:: 2015.8.4

:depends: pyVmomi
'''

# Import Python Libs
from __future__ import absolute_import
import datetime
import logging

# Import Salt Libs
import salt.ext.six as six
import salt.utils.vmware
import salt.utils.http
from salt.exceptions import CommandExecutionError

# Import Third Party Libs
try:
    from pyVmomi import vim
    HAS_PYVMOMI = True
except ImportError:
    HAS_PYVMOMI = False

log = logging.getLogger(__name__)

__virtualname__ = 'vsphere'


def __virtual__():
    if not HAS_PYVMOMI:
        return False, 'The vSphere module requires the pyVmomi Python module.'

    return __virtualname__


def upload_ssh_key(host, username, password, ssh_key=None, ssh_key_file=None,
                   protocol='https', port=443, certificate_verify=False):
    '''

    Upload an ssh key for root to an ESXi host via http PUT.
    This function only works for ESXi, not vCenter.
    Only one ssh key can be uploaded for root.  Uploading a second key will
    replace any existing key.

    :param host: The location of the ESXi Host
    :param username: Username to connect as
    :param password: Password for the ESXi web endpoint
    :param ssh_key: Public SSH key, will be added to authorized_keys on ESXi
    :param ssh_key_file: File containing the SSH key.  Use 'ssh_key' or
                         ssh_key_file, but not both.
    :param protocol: defaults to https, can be http if ssl is disabled on ESXi
    :param port: defaults to 443 for https
    :param certificate_verify: If true require that the SSL connection present
                               a valid certificate
    :return: Dictionary with a 'status' key, True if upload is successful.
             If upload is unsuccessful, 'status' key will be False and
             an 'Error' key will have an informative message.
    '''
    url = '{0}://{1}:{2}/host/ssh_root_authorized_keys'.format(protocol,
                                                               host,
                                                               port)
    ret = {}
    result = None
    try:
        if ssh_key:
            result = salt.utils.http.query(url,
                                           status=True,
                                           text=True,
                                           method='PUT',
                                           username=username,
                                           password=password,
                                           data=ssh_key,
                                           verify_ssl=certificate_verify)
        elif ssh_key_file:
            result = salt.utils.http.query(url,
                                           status=True,
                                           text=True,
                                           method='PUT',
                                           username=username,
                                           password=password,
                                           data_file=ssh_key_file,
                                           data_render=False,
                                           verify_ssl=certificate_verify)
        if result.get('status') == 200:
            ret['status'] = True
        else:
            ret['status'] = False
            ret['Error'] = result['error']
    except Exception as msg:
        ret['status'] = False
        ret['Error'] = msg

    return ret


def get_ssh_key(host, username, password,
                protocol='https', port=443, certificate_verify=False):
    '''

    Retrieve the authorized_keys entry for root.
    This function only works for ESXi, not vCenter.

    :param host: The location of the ESXi Host
    :param username: Username to connect as
    :param password: Password for the ESXi web endpoint
    :param protocol: defaults to https, can be http if ssl is disabled on ESXi
    :param port: defaults to 443 for https
    :param certificate_verify: If true require that the SSL connection present
                               a valid certificate
    :return: True if upload is successful
    '''
    url = '{0}://{1}:{2}/host/ssh_root_authorized_keys'.format(protocol,
                                                               host,
                                                               port)
    ret = {}
    try:
        result = salt.utils.http.query(url,
                                       status=True,
                                       text=True,
                                       method='GET',
                                       username=username,
                                       password=password,
                                       verify_ssl=certificate_verify)
        if result.get('status') == 200:
            ret['status'] = True
            ret['key'] = result['text']
        else:
            ret['status'] = False
            ret['Error'] = result['error']
    except Exception as msg:
        ret['status'] = False
        ret['Error'] = msg

    return ret


def get_host_datetime(host, username, password, protocol=None, port=None, host_names=None):
    '''
    Get the date/time information for a given host or list of host_names.

    host
        The location of the host.

    username
        The username used to login to the host, such as ``root``.

    password
        The password used to login to the host.

    protocol
        Optionally set to alternate protocol if the host is not using the default
        protocol. Default protocol is ``https``.

    port
        Optionally set to alternate port if the host is not using the default
        port. Default port is ``443``.

    host_names
        List of ESXi host names. When the host, username, and password credentials
        are provided for a vCenter Server, the host_names argument is required to tell
        vCenter the hosts for which to get date/time information.

        If host_names is not provided, the date/time information will be retrieved for the
        ``host`` location instead. This is useful for when service instance connection
        information is used for a single ESXi host.

    CLI Example:

    .. code-block:: bash

        # Used for single ESXi host connection information
        salt '*' vsphere.get_host_datetime my.esxi.host root bad-password

        # Used for connecting to a vCenter Server
        salt '*' vsphere.get_host_datetime my.vcenter.location root bad-password \
        host_names='[esxi-1.host.com, esxi-2.host.com]'
    '''
    service_instance = salt.utils.vmware.get_service_instance(host=host,
                                                              username=username,
                                                              password=password,
                                                              protocol=protocol,
                                                              port=port)
    host_names = _check_hosts(service_instance, host, host_names)
    ret = {}
    for host_name in host_names:
        host_ref = _get_host_ref(service_instance, host, host_name=host_name)
        date_time_manager = _get_date_time_mgr(host_ref)
        date_time = date_time_manager.QueryDateTime()
        ret.update({host_name: date_time})

    return ret


def get_ntp_config(host, username, password, protocol=None, port=None, host_names=None):
    '''
    Get the NTP configuration information for a given host or list of host_names.

    host
        The location of the host.

    username
        The username used to login to the host, such as ``root``.

    password
        The password used to login to the host.

    protocol
        Optionally set to alternate protocol if the host is not using the default
        protocol. Default protocol is ``https``.

    port
        Optionally set to alternate port if the host is not using the default
        port. Default port is ``443``.

    host_names
        List of ESXi host names. When the host, username, and password credentials
        are provided for a vCenter Server, the host_names argument is required to tell
        vCenter the hosts for which to get ntp configuration information.

        If host_names is not provided, the NTP configuration will be retrieved for the
        ``host`` location instead. This is useful for when service instance connection
        information is used for a single ESXi host.

    CLI Example:

    .. code-block:: bash

        # Used for single ESXi host connection information
        salt '*' vsphere.get_ntp_config my.esxi.host root bad-password

        # Used for connecting to a vCenter Server
        salt '*' vsphere.get_ntp_config my.vcenter.location root bad-password \
        host_names='[esxi-1.host.com, esxi-2.host.com]'
    '''
    service_instance = salt.utils.vmware.get_service_instance(host=host,
                                                              username=username,
                                                              password=password,
                                                              protocol=protocol,
                                                              port=port)
    host_names = _check_hosts(service_instance, host, host_names)
    ret = {}
    for host_name in host_names:
        host_ref = _get_host_ref(service_instance, host, host_name=host_name)
        ntp_config = _get_ntp_config(host_ref)
        ret.update({host_name: ntp_config})

    return ret


def get_service_policy(host, username, password, service_name, protocol=None, port=None, host_names=None):
    '''
    Get the service name's policy for a given host or list of hosts.

    host
        The location of the host.

    username
        The username used to login to the host, such as ``root``.

    password
        The password used to login to the host.

    service_name
        The name of the service for which to retrieve the policy. Supported service names are:
          - DCUI
          - TSM
          - SSH
          - lbtd
          - lsassd
          - lwiod
          - netlogond
          - ntpd
          - sfcbd-watchdog
          - snmpd
          - vprobed
          - vpxa
          - xorg

    protocol
        Optionally set to alternate protocol if the host is not using the default
        protocol. Default protocol is ``https``.

    port
        Optionally set to alternate port if the host is not using the default
        port. Default port is ``443``.

    host_names
        List of ESXi host names. When the host, username, and password credentials
        are provided for a vCenter Server, the host_names argument is required to tell
        vCenter the hosts for which to get service policy information.

        If host_names is not provided, the service policy information will be retrieved
        for the ``host`` location instead. This is useful for when service instance
        connection information is used for a single ESXi host.

    CLI Example:

    .. code-block:: bash

        # Used for single ESXi host connection information
        salt '*' vsphere.get_service_policy my.esxi.host root bad-password 'ssh'

        # Used for connecting to a vCenter Server
        salt '*' vsphere.get_service_policy my.vcenter.location root bad-password 'ntpd' \
        host_names='[esxi-1.host.com, esxi-2.host.com]'
    '''
    service_instance = salt.utils.vmware.get_service_instance(host=host,
                                                              username=username,
                                                              password=password,
                                                              protocol=protocol,
                                                              port=port)
    host_names = _check_hosts(service_instance, host, host_names)

    ret = {}
    for host_name in host_names:
        host_ref = _get_host_ref(service_instance, host, host_name=host_name)
        services = host_ref.configManager.serviceSystem.serviceInfo.service
        for service in services:
            if service.key == service_name:
                ret.update({host_name: service.policy})
            elif service_name == 'ssh' or service_name == 'SSH':
                if service.key == 'TSM-SSH':
                    ret.update({host_name: service.policy})
            else:
                msg = 'Could not find service \'{0}\' for host \'{1}\'.'.format(service_name,
                                                                                host_name)
                log.debug(msg)
                ret.update({host_name: {'Error': msg}})

        if ret.get(host_name) is None:
            msg = '\'vsphere.get_service_policy\' failed for host {0}.'.format(host_name)
            log.debug(msg)
            ret.update({host_name: {'Error': msg}})

    return ret


def get_service_running(host, username, password, service_name, protocol=None, port=None, host_names=None):
    '''
    Get the service name's running state for a given host or list of hosts.

    host
        The location of the host.

    username
        The username used to login to the host, such as ``root``.

    password
        The password used to login to the host.

    service_name
        The name of the service for which to retrieve the policy. Supported service names are:
          - DCUI
          - TSM
          - SSH
          - lbtd
          - lsassd
          - lwiod
          - netlogond
          - ntpd
          - sfcbd-watchdog
          - snmpd
          - vprobed
          - vpxa
          - xorg

    protocol
        Optionally set to alternate protocol if the host is not using the default
        protocol. Default protocol is ``https``.

    port
        Optionally set to alternate port if the host is not using the default
        port. Default port is ``443``.

    host_names
        List of ESXi host names. When the host, username, and password credentials
        are provided for a vCenter Server, the host_names argument is required to tell
        vCenter the hosts for which to get the service's running state.

        If host_names is not provided, the service's running state will be retrieved
        for the ``host`` location instead. This is useful for when service instance
        connection information is used for a single ESXi host.

    CLI Example:

    .. code-block:: bash

        # Used for single ESXi host connection information
        salt '*' vsphere.get_service_running my.esxi.host root bad-password 'ssh'

        # Used for connecting to a vCenter Server
        salt '*' vsphere.get_service_running my.vcenter.location root bad-password 'ntpd' \
        host_names='[esxi-1.host.com, esxi-2.host.com]'
    '''
    service_instance = salt.utils.vmware.get_service_instance(host=host,
                                                              username=username,
                                                              password=password,
                                                              protocol=protocol,
                                                              port=port)
    host_names = _check_hosts(service_instance, host, host_names)

    ret = {}
    for host_name in host_names:
        host_ref = _get_host_ref(service_instance, host, host_name=host_name)
        services = host_ref.configManager.serviceSystem.serviceInfo.service
        for service in services:
            if service.key == service_name:
                ret.update({host_name: service.running})
            elif service_name == 'SSH' or service_name == 'ssh':
                if service.key == 'TSM-SSH':
                    ret.update({host_name: service.running})
            else:
                msg = 'Could not find service \'{0}\' for host \'{1}\'.'.format(service_name,
                                                                                host_name)
                log.debug(msg)
                ret.update({host_name: {'Error': msg}})

        if ret.get(host_name) is None:
            msg = '\'vsphere.get_service_running\' failed for host {0}.'.format(host_name)
            log.debug(msg)
            ret.update({host_name: {'Error': msg}})

    return ret


def get_vsan_enabled(host, username, password, protocol=None, port=None, host_names=None):
    '''
    Get the VSAN enabled status for a given host or a list of host_names. Returns ``True``
    if VSAN is enabled, ``False`` if it is not enabled, and ``None`` if a VSAN Host Config
    is unset, per host.

    host
        The location of the host.

    username
        The username used to login to the host, such as ``root``.

    password
        The password used to login to the host.

    protocol
        Optionally set to alternate protocol if the host is not using the default
        protocol. Default protocol is ``https``.

    port
        Optionally set to alternate port if the host is not using the default
        port. Default port is ``443``.

    host_names
        List of ESXi host names. When the host, username, and password credentials
        are provided for a vCenter Server, the host_names argument is required to
        tell vCenter which hosts to check if VSAN enabled.

        If host_names is not provided, the VSAN status will be retrieved for the
        ``host`` location instead. This is useful for when service instance
        connection information is used for a single ESXi host.

    CLI Example:

    .. code-block:: bash

        # Used for single ESXi host connection information
        salt '*' vsphere.get_vsan_enabled my.esxi.host root bad-password

        # Used for connecting to a vCenter Server
        salt '*' vsphere.get_vsan_enabled my.vcenter.location root bad-password \
        host_names='[esxi-1.host.com, esxi-2.host.com]'
    '''
    service_instance = salt.utils.vmware.get_service_instance(host=host,
                                                              username=username,
                                                              password=password,
                                                              protocol=protocol,
                                                              port=port)
    host_names = _check_hosts(service_instance, host, host_names)
    ret = {}
    for host_name in host_names:
        host_ref = _get_host_ref(service_instance, host, host_name=host_name)
        vsan_config = host_ref.config.vsanHostConfig
        if vsan_config is None:
            msg = 'VSAN System Config Manager is unset for host \'{0}\'.'.format(host_name)
            log.debug(msg)
            ret.update({host_name: {'Error': msg}})
        else:
            ret.update({host_name: vsan_config.enabled})

    return ret


def get_vsan_eligible_disks(host, username, password, protocol=None, port=None, host_names=None):
    '''
    Returns a list of VSAN-eligible disks for a given host or list of host_names.

    host
        The location of the host.

    username
        The username used to login to the host, such as ``root``.

    password
        The password used to login to the host.

    protocol
        Optionally set to alternate protocol if the host is not using the default
        protocol. Default protocol is ``https``.

    port
        Optionally set to alternate port if the host is not using the default
        port. Default port is ``443``.

    host_names
        List of ESXi host names. When the host, username, and password credentials
        are provided for a vCenter Server, the host_names argument is required to
        tell vCenter which hosts to check if any VSAN-eligible disks are available.

        If host_names is not provided, the VSAN-eligible disks will be retrieved
        for the ``host`` location instead. This is useful for when service instance
        connection information is used for a single ESXi host.

    CLI Example:

    .. code-block:: bash

        # Used for single ESXi host connection information
        salt '*' vsphere.get_vsan_eligible_disks my.esxi.host root bad-password

        # Used for connecting to a vCenter Server
        salt '*' vsphere.get_vsan_eligible_disks my.vcenter.location root bad-password \
        host_names='[esxi-1.host.com, esxi-2.host.com]'
    '''
    service_instance = salt.utils.vmware.get_service_instance(host=host,
                                                              username=username,
                                                              password=password,
                                                              protocol=protocol,
                                                              port=port)
    host_names = _check_hosts(service_instance, host, host_names)
    return _get_vsan_eligible_disks(service_instance, host, host_names)


def system_info(host, username, password, protocol=None, port=None):
    '''
    Return system information about a VMware environment.

    host
        The location of the host.

    username
        The username used to login to the host, such as ``root``.

    password
        The password used to login to the host.

    protocol
        Optionally set to alternate protocol if the host is not using the default
        protocol. Default protocol is ``https``.

    port
        Optionally set to alternate port if the host is not using the default
        port. Default port is ``443``.

    CLI Example:

    .. code-block:: bash

        salt '*' vsphere.system_info 1.2.3.4 root bad-password
    '''
    service_instance = salt.utils.vmware.get_service_instance(host=host,
                                                              username=username,
                                                              password=password,
                                                              protocol=protocol,
                                                              port=port)
    return salt.utils.vmware.get_inventory(service_instance).about.__dict__


def list_datacenters(host, username, password, protocol=None, port=None):
    '''
    Returns a list of datacenters for the the specified host.

    host
        The location of the host.

    username
        The username used to login to the host, such as ``root``.

    password
        The password used to login to the host.

    protocol
        Optionally set to alternate protocol if the host is not using the default
        protocol. Default protocol is ``https``.

    port
        Optionally set to alternate port if the host is not using the default
        port. Default port is ``443``.

    .. code-block:: bash

        salt '*' vsphere.list_datacenters 1.2.3.4 root bad-password
    '''
    service_instance = salt.utils.vmware.get_service_instance(host=host,
                                                              username=username,
                                                              password=password,
                                                              protocol=protocol,
                                                              port=port)
    return salt.utils.vmware.list_datacenters(service_instance)


def list_clusters(host, username, password, protocol=None, port=None):
    '''
    Returns a list of clusters for the the specified host.

    host
        The location of the host.

    username
        The username used to login to the host, such as ``root``.

    password
        The password used to login to the host.

    protocol
        Optionally set to alternate protocol if the host is not using the default
        protocol. Default protocol is ``https``.

    port
        Optionally set to alternate port if the host is not using the default
        port. Default port is ``443``.

    .. code-block:: bash

        salt '*' vsphere.list_clusters 1.2.3.4 root bad-password
    '''
    service_instance = salt.utils.vmware.get_service_instance(host=host,
                                                              username=username,
                                                              password=password,
                                                              protocol=protocol,
                                                              port=port)
    return salt.utils.vmware.list_clusters(service_instance)


def list_datastore_clusters(host, username, password, protocol=None, port=None):
    '''
    Returns a list of datastore clusters for the the specified host.

    host
        The location of the host.

    username
        The username used to login to the host, such as ``root``.

    password
        The password used to login to the host.

    protocol
        Optionally set to alternate protocol if the host is not using the default
        protocol. Default protocol is ``https``.

    port
        Optionally set to alternate port if the host is not using the default
        port. Default port is ``443``.

    .. code-block:: bash

        salt '*' vsphere.list_datastore_clusters 1.2.3.4 root bad-password
    '''
    service_instance = salt.utils.vmware.get_service_instance(host=host,
                                                              username=username,
                                                              password=password,
                                                              protocol=protocol,
                                                              port=port)
    return salt.utils.vmware.list_datastore_clusters(service_instance)


def list_datastores(host, username, password, protocol=None, port=None):
    '''
    Returns a list of datastores for the the specified host.

    host
        The location of the host.

    username
        The username used to login to the host, such as ``root``.

    password
        The password used to login to the host.

    protocol
        Optionally set to alternate protocol if the host is not using the default
        protocol. Default protocol is ``https``.

    port
        Optionally set to alternate port if the host is not using the default
        port. Default port is ``443``.

    .. code-block:: bash

        salt '*' vsphere.list_datastores 1.2.3.4 root bad-password
    '''
    service_instance = salt.utils.vmware.get_service_instance(host=host,
                                                              username=username,
                                                              password=password,
                                                              protocol=protocol,
                                                              port=port)
    return salt.utils.vmware.list_datastores(service_instance)


def list_hosts(host, username, password, protocol=None, port=None):
    '''
    Returns a list of hosts for the the specified VMware environment.

    host
        The location of the host.

    username
        The username used to login to the host, such as ``root``.

    password
        The password used to login to the host.

    protocol
        Optionally set to alternate protocol if the host is not using the default
        protocol. Default protocol is ``https``.

    port
        Optionally set to alternate port if the host is not using the default
        port. Default port is ``443``.

    .. code-block:: bash

        salt '*' vsphere.list_hosts 1.2.3.4 root bad-password
    '''
    service_instance = salt.utils.vmware.get_service_instance(host=host,
                                                              username=username,
                                                              password=password,
                                                              protocol=protocol,
                                                              port=port)
    return salt.utils.vmware.list_hosts(service_instance)


def list_resourcepools(host, username, password, protocol=None, port=None):
    '''
    Returns a list of resource pools for the the specified host.

    host
        The location of the host.

    username
        The username used to login to the host, such as ``root``.

    password
        The password used to login to the host.

    protocol
        Optionally set to alternate protocol if the host is not using the default
        protocol. Default protocol is ``https``.

    port
        Optionally set to alternate port if the host is not using the default
        port. Default port is ``443``.

    .. code-block:: bash

        salt '*' vsphere.list_resourcepools 1.2.3.4 root bad-password
    '''
    service_instance = salt.utils.vmware.get_service_instance(host=host,
                                                              username=username,
                                                              password=password,
                                                              protocol=protocol,
                                                              port=port)
    return salt.utils.vmware.list_resourcepools(service_instance)


def list_networks(host, username, password, protocol=None, port=None):
    '''
    Returns a list of networks for the the specified host.

    host
        The location of the host.

    username
        The username used to login to the host, such as ``root``.

    password
        The password used to login to the host.

    protocol
        Optionally set to alternate protocol if the host is not using the default
        protocol. Default protocol is ``https``.

    port
        Optionally set to alternate port if the host is not using the default
        port. Default port is ``443``.

    .. code-block:: bash

        salt '*' vsphere.list_networks 1.2.3.4 root bad-password
    '''
    service_instance = salt.utils.vmware.get_service_instance(host=host,
                                                              username=username,
                                                              password=password,
                                                              protocol=protocol,
                                                              port=port)
    return salt.utils.vmware.list_networks(service_instance)


def list_vms(host, username, password, protocol=None, port=None):
    '''
    Returns a list of VMs for the the specified host.

    host
        The location of the host.

    username
        The username used to login to the host, such as ``root``.

    password
        The password used to login to the host.

    protocol
        Optionally set to alternate protocol if the host is not using the default
        protocol. Default protocol is ``https``.

    port
        Optionally set to alternate port if the host is not using the default
        port. Default port is ``443``.

    .. code-block:: bash

        salt '*' vsphere.list_vms 1.2.3.4 root bad-password
    '''
    service_instance = salt.utils.vmware.get_service_instance(host=host,
                                                              username=username,
                                                              password=password,
                                                              protocol=protocol,
                                                              port=port)
    return salt.utils.vmware.list_vms(service_instance)


def list_folders(host, username, password, protocol=None, port=None):
    '''
    Returns a list of folders for the the specified host.

    host
        The location of the host.

    username
        The username used to login to the host, such as ``root``.

    password
        The password used to login to the host.

    protocol
        Optionally set to alternate protocol if the host is not using the default
        protocol. Default protocol is ``https``.

    port
        Optionally set to alternate port if the host is not using the default
        port. Default port is ``443``.

    .. code-block:: bash

        salt '*' vsphere.list_folders 1.2.3.4 root bad-password
    '''
    service_instance = salt.utils.vmware.get_service_instance(host=host,
                                                              username=username,
                                                              password=password,
                                                              protocol=protocol,
                                                              port=port)
    return salt.utils.vmware.list_folders(service_instance)


def list_dvs(host, username, password, protocol=None, port=None):
    '''
    Returns a list of distributed virtual switches for the the specified host.

    host
        The location of the host.

    username
        The username used to login to the host, such as ``root``.

    password
        The password used to login to the host.

    protocol
        Optionally set to alternate protocol if the host is not using the default
        protocol. Default protocol is ``https``.

    port
        Optionally set to alternate port if the host is not using the default
        port. Default port is ``443``.

    .. code-block:: bash

        salt '*' vsphere.list_dvs 1.2.3.4 root bad-password
    '''
    service_instance = salt.utils.vmware.get_service_instance(host=host,
                                                              username=username,
                                                              password=password,
                                                              protocol=protocol,
                                                              port=port)
    return salt.utils.vmware.list_dvs(service_instance)


def list_vapps(host, username, password, protocol=None, port=None):
    '''
    Returns a list of vApps for the the specified host.

    host
        The location of the host.

    username
        The username used to login to the host, such as ``root``.

    password
        The password used to login to the host.

    protocol
        Optionally set to alternate protocol if the host is not using the default
        protocol. Default protocol is ``https``.

    port
        Optionally set to alternate port if the host is not using the default
        port. Default port is ``443``.

    .. code-block:: bash

        salt '*' vsphere.list_vapps 1.2.3.4 root bad-password
    '''
    service_instance = salt.utils.vmware.get_service_instance(host=host,
                                                              username=username,
                                                              password=password,
                                                              protocol=protocol,
                                                              port=port)
    return salt.utils.vmware.list_vapps(service_instance)


def list_ssds(host, username, password, protocol=None, port=None, host_names=None):
    '''
    Returns a list of SSDs for the given host or list of host_names.

    host
        The location of the host.

    username
        The username used to login to the host, such as ``root``.

    password
        The password used to login to the host.

    protocol
        Optionally set to alternate protocol if the host is not using the default
        protocol. Default protocol is ``https``.

    port
        Optionally set to alternate port if the host is not using the default
        port. Default port is ``443``.

    host_names
        List of ESXi host names. When the host, username, and password credentials
        are provided for a vCenter Server, the host_names argument is required to
        tell vCenter the hosts for which to retrieve SSDs.

        If host_names is not provided, SSDs will be retrieved for the
        ``host`` location instead. This is useful for when service instance
        connection information is used for a single ESXi host.

    CLI Example:

    .. code-block:: bash

        # Used for single ESXi host connection information
        salt '*' vsphere.list_ssds my.esxi.host root bad-password

        # Used for connecting to a vCenter Server
        salt '*' vsphere.list_ssds my.vcenter.location root bad-password \
        host_names='[esxi-1.host.com, esxi-2.host.com]'
    '''
    service_instance = salt.utils.vmware.get_service_instance(host=host,
                                                              username=username,
                                                              password=password,
                                                              protocol=protocol,
                                                              port=port)
    host_names = _check_hosts(service_instance, host, host_names)
    ret = {}
    names = []
    for host_name in host_names:
        host_ref = _get_host_ref(service_instance, host, host_name=host_name)
        disks = _get_host_ssds(host_ref)
        for disk in disks:
            names.append(disk.canonicalName)
        ret.update({host_name: names})

    return ret


def list_non_ssds(host, username, password, protocol=None, port=None, host_names=None):
    '''
    Returns a list of Non-SSD disks for the given host or list of host_names.

    .. note::

        In the pyVmomi StorageSystem, ScsiDisks may, or may not have an ``ssd`` attribute.
        This attribute indicates if the ScsiDisk is SSD backed. As this option is optional,
        if a relevant disk in the StorageSystem does not have ``ssd = true``, it will end
        up in the ``non_ssds`` list here.

    host
        The location of the host.

    username
        The username used to login to the host, such as ``root``.

    password
        The password used to login to the host.

    protocol
        Optionally set to alternate protocol if the host is not using the default
        protocol. Default protocol is ``https``.

    port
        Optionally set to alternate port if the host is not using the default
        port. Default port is ``443``.

    host_names
        List of ESXi host names. When the host, username, and password credentials
        are provided for a vCenter Server, the host_names argument is required to
        tell vCenter the hosts for which to retrieve Non-SSD disks.

        If host_names is not provided, Non-SSD disks will be retrieved for the
        ``host`` location instead. This is useful for when service instance
        connection information is used for a single ESXi host.

    CLI Example:

    .. code-block:: bash

        # Used for single ESXi host connection information
        salt '*' vsphere.list_non_ssds my.esxi.host root bad-password

        # Used for connecting to a vCenter Server
        salt '*' vsphere.list_non_ssds my.vcenter.location root bad-password \
        host_names='[esxi-1.host.com, esxi-2.host.com]'
    '''
    service_instance = salt.utils.vmware.get_service_instance(host=host,
                                                              username=username,
                                                              password=password,
                                                              protocol=protocol,
                                                              port=port)
    host_names = _check_hosts(service_instance, host, host_names)
    ret = {}
    names = []
    for host_name in host_names:
        host_ref = _get_host_ref(service_instance, host, host_name=host_name)
        disks = _get_host_non_ssds(host_ref)
        for disk in disks:
            names.append(disk.canonicalName)
        ret.update({host_name: names})

    return ret


def set_ntp_config(host, username, password, ntp_servers, protocol=None, port=None, host_names=None):
    '''
    Set NTP configuration for a given host of list of host_names.

    host
        The location of the host.

    username
        The username used to login to the host, such as ``root``.

    password
        The password used to login to the host.

    ntp_servers
        A list of servers that should be added to and configured for the specified
        host's NTP configuration.

    protocol
        Optionally set to alternate protocol if the host is not using the default
        protocol. Default protocol is ``https``.

    port
        Optionally set to alternate port if the host is not using the default
        port. Default port is ``443``.

    host_names
        List of ESXi host names. When the host, username, and password credentials
        are provided for a vCenter Server, the host_names argument is required to tell
        vCenter which hosts to configure ntp servers.

        If host_names is not provided, the NTP servers will be configured for the
        ``host`` location instead. This is useful for when service instance connection
        information is used for a single ESXi host.

    CLI Example:

    .. code-block:: bash

        # Used for single ESXi host connection information
        salt '*' vsphere.ntp_configure my.esxi.host root bad-password '[192.174.1.100, 192.174.1.200]'

        # Used for connecting to a vCenter Server
        salt '*' vsphere.ntp_configure my.vcenter.location root bad-password '[192.174.1.100, 192.174.1.200]' \
        host_names='[esxi-1.host.com, esxi-2.host.com]'
    '''
    service_instance = salt.utils.vmware.get_service_instance(host=host,
                                                              username=username,
                                                              password=password,
                                                              protocol=protocol,
                                                              port=port)
    if not isinstance(ntp_servers, list):
        raise CommandExecutionError('\'ntp_servers\' must be a list.')

    # Get NTP Config Object from ntp_servers
    ntp_config = vim.HostNtpConfig(server=ntp_servers)

    # Get DateTimeConfig object from ntp_config
    date_config = vim.HostDateTimeConfig(ntpConfig=ntp_config)

    host_names = _check_hosts(service_instance, host, host_names)
    ret = {}
    for host_name in host_names:
        host_ref = _get_host_ref(service_instance, host, host_name=host_name)
        date_time_manager = _get_date_time_mgr(host_ref)
        log.debug('Configuring NTP Servers \'{0}\' for host \'{1}\'.'.format(ntp_servers, host_name))

        try:
            date_time_manager.UpdateDateTimeConfig(config=date_config)
        except vim.fault.HostConfigFault as err:
            msg = 'vsphere.ntp_configure_servers failed: {0}'.format(err)
            log.debug(msg)
            ret.update({host_name: {'Error': msg}})
            continue

        ret.update({host_name: ntp_config})
    return ret


def ntp_restart(host, username, password, protocol=None, port=None, host_names=None):
    '''
    Restart the ntp service for a given host or list of host_names.

    host
        The location of the host.

    username
        The username used to login to the host, such as ``root``.

    password
        The password used to login to the host.

    protocol
        Optionally set to alternate protocol if the host is not using the default
        protocol. Default protocol is ``https``.

    port
        Optionally set to alternate port if the host is not using the default
        port. Default port is ``443``.

    host_names
        List of ESXi host names. When the host, username, and password credentials
        are provided for a vCenter Server, the host_names argument is required to tell
        vCenter which hosts need to restart ntp deamons.

        If host_names is not provided, the NTP daemon will be restarted for the
        ``host`` location instead. This is useful for when service instance connection
        information is used for a single ESXi host.

    CLI Example:

    .. code-block:: bash

        # Used for single ESXi host connection information
        salt '*' vsphere.ntp_restart my.esxi.host root bad-password

        # Used for connecting to a vCenter Server
        salt '*' vsphere.ntp_restart my.vcenter.location root bad-password \
        host_names='[esxi-1.host.com, esxi-2.host.com]'
    '''
    service_instance = salt.utils.vmware.get_service_instance(host=host,
                                                              username=username,
                                                              password=password,
                                                              protocol=protocol,
                                                              port=port)
    host_names = _check_hosts(service_instance, host, host_names)
    ret = {}
    for host_name in host_names:
        host_ref = _get_host_ref(service_instance, host, host_name=host_name)
        ntp_config = _get_ntp_config(host_ref)
        if ntp_config:
            service_manager = _get_service_manager(host_ref)
            log.debug('Restarting \'ntpd\' service on {0}.'.format(ntp_config))

            try:
                service_manager.RestartService(id='ntpd')
            except vim.fault.HostConfigFault as err:
                msg = '\'vsphere.ntp_restart\' failed: {0}'.format(err)
                log.debug(msg)
                ret.update({host_name: {'Error': msg}})
                continue
            except vim.fault.RestrictedVersion as err:
                log.debug(err)
                ret.update({host_name: {'Error': err}})
                continue

            ret.update({host_name: ntp_config})
        else:
            log.warning('Unable to restart the \'ntpd\' service. '
                        'NTP servers have not been configured for \'{0}\'.'.format(host_name))
            ret.update({host_name: None})

    return ret


def ntp_start(host, username, password, protocol=None, port=None, host_names=None):
    '''
    Start the ntp service for a given host or list of host_names.

    host
        The location of the host.

    username
        The username used to login to the host, such as ``root``.

    password
        The password used to login to the host.

    protocol
        Optionally set to alternate protocol if the host is not using the default
        protocol. Default protocol is ``https``.

    port
        Optionally set to alternate port if the host is not using the default
        port. Default port is ``443``.

    host_names
        List of ESXi host names. When the host, username, and password credentials
        are provided for a vCenter Server, the host_names argument is required to tell
        vCenter which hosts need to start ntp deamons.

        If host_names is not provided, the NTP daemon will be started for the
        ``host`` location instead. This is useful for when service instance connection
        information is used for a single ESXi host.

    CLI Example:

    .. code-block:: bash

        # Used for single ESXi host connection information
        salt '*' vsphere.ntp_start my.esxi.host root bad-password

        # Used for connecting to a vCenter Server
        salt '*' vsphere.ntp_start my.vcenter.location root bad-password \
        host_names='[esxi-1.host.com, esxi-2.host.com]'
    '''
    service_instance = salt.utils.vmware.get_service_instance(host=host,
                                                              username=username,
                                                              password=password,
                                                              protocol=protocol,
                                                              port=port)
    host_names = _check_hosts(service_instance, host, host_names)
    ret = {}
    for host_name in host_names:
        host_ref = _get_host_ref(service_instance, host, host_name=host_name)
        ntp_config = _get_ntp_config(host_ref)
        if ntp_config:
            service_manager = _get_service_manager(host_ref)
            log.debug('Starting \'ntpd\' service on {0}.'.format(ntp_config))

            try:
                service_manager.StartService(id='ntpd')
            except vim.fault.HostConfigFault as err:
                msg = '\'vsphere.ntp_start\' failed: {0}'.format(err)
                log.debug(msg)
                ret.update({host_name: {'Error': msg}})
                continue
            except vim.fault.RestrictedVersion as err:
                log.debug(err)
                ret.update({host_name: {'Error': err}})
                continue

            ret.update({host_name: ntp_config})
        else:
            msg = 'Unable to start the \'ntpd\' service. ' \
                  'NTP servers have not been configured for \'{0}\'.'.format(host_name)
            log.debug(msg)
            ret.update({host_name: {'Error': msg}})

    return ret


def ntp_stop(host, username, password, protocol=None, port=None, host_names=None):
    '''
    Stop the ntp service for a given host or list of host_names.

    host
        The location of the host.

    username
        The username used to login to the host, such as ``root``.

    password
        The password used to login to the host.

    protocol
        Optionally set to alternate protocol if the host is not using the default
        protocol. Default protocol is ``https``.

    port
        Optionally set to alternate port if the host is not using the default
        port. Default port is ``443``.

    host_names
        List of ESXi host names. When the host, username, and password credentials
        are provided for a vCenter Server, the host_names argument is required to tell
        vCenter which hosts need to stop ntp deamons.

        If host_names is not provided, the NTP daemon will be stopped for the
        ``host`` location instead. This is useful for when service instance connection
        information is used for a single ESXi host.

    CLI Example:

    .. code-block:: bash

        # Used for single ESXi host connection information
        salt '*' vsphere.ntp_stop my.esxi.host root bad-password

        # Used for connecting to a vCenter Server
        salt '*' vsphere.ntp_stop my.vcenter.location root bad-password \
        host_names='[esxi-1.host.com, esxi-2.host.com]'
    '''
    service_instance = salt.utils.vmware.get_service_instance(host=host,
                                                              username=username,
                                                              password=password,
                                                              protocol=protocol,
                                                              port=port)
    host_names = _check_hosts(service_instance, host, host_names)
    ret = {}
    for host_name in host_names:
        host_ref = _get_host_ref(service_instance, host, host_name=host_name)
        ntp_config = _get_ntp_config(host_ref)
        if ntp_config:
            service_manager = _get_service_manager(host_ref)
            log.debug('Stopping \'ntpd\' service on {0}.'.format(ntp_config))

            try:
                service_manager.StopService(id='ntpd')
            except vim.fault.HostConfigFault as err:
                msg = '\'vsphere.ntp_stop\' failed: {0}'.format(err)
                log.debug(msg)
                ret.update({host_name: {'Error': msg}})
                continue
            except vim.fault.RestrictedVersion as err:
                log.debug(err)
                ret.update({host_name: {'Error': err}})
                continue

            ret.update({host_name: ntp_config})
        else:
            msg = 'Unable to stop the \'ntpd\' service. ' \
                  'NTP servers have not been configured for \'{0}\'.'.format(host_name)
            log.debug(msg)
            ret.update({host_name: {'Error': msg}})
    
    return ret


def set_service_policy(host,
                       username,
                       password,
                       service_name,
                       service_policy,
                       protocol=None,
                       port=None,
                       host_names=None):
    '''
    Set the service name's policy for a given host or list of hosts.

    host
        The location of the host.

    username
        The username used to login to the host, such as ``root``.

    password
        The password used to login to the host.

    service_name
        The name of the service for which to set the policy. Supported service names are:
          - DCUI
          - TSM
          - SSH
          - lbtd
          - lsassd
          - lwiod
          - netlogond
          - ntpd
          - sfcbd-watchdog
          - snmpd
          - vprobed
          - vpxa
          - xorg

    service_policy
        The policy to set for the service. For example, 'automatic'.

    protocol
        Optionally set to alternate protocol if the host is not using the default
        protocol. Default protocol is ``https``.

    port
        Optionally set to alternate port if the host is not using the default
        port. Default port is ``443``.

    host_names
        List of ESXi host names. When the host, username, and password credentials
        are provided for a vCenter Server, the host_names argument is required to tell
        vCenter the hosts for which to set the service policy.

        If host_names is not provided, the service policy information will be retrieved
        for the ``host`` location instead. This is useful for when service instance
        connection information is used for a single ESXi host.

    CLI Example:

    .. code-block:: bash

        # Used for single ESXi host connection information
        salt '*' vsphere.get_host_datetime my.esxi.host root bad-password 'ntpd' 'automatic'

        # Used for connecting to a vCenter Server
        salt '*' vsphere.get_service_policy my.vcenter.location root bad-password 'ntpd' 'automatic' \
        host_names='[esxi-1.host.com, esxi-2.host.com]'
    '''
    service_instance = salt.utils.vmware.get_service_instance(host=host,
                                                              username=username,
                                                              password=password,
                                                              protocol=protocol,
                                                              port=port)
    host_names = _check_hosts(service_instance, host, host_names)
    ret = {}
    for host_name in host_names:
        host_ref = _get_host_ref(service_instance, host, host_name=host_name)
        service_manager = _get_service_manager(host_ref)
        services = host_ref.configManager.serviceSystem.serviceInfo.service
        for service in services:
            service_key = None

            # Find the service key based on the given service_name
            if service.key == service_name:
                service_key = service.key
            elif service_name == 'ssh' or service_name == 'SSH':
                if service.key == 'TSM-SSH':
                    service_key = 'TSM-SSH'

            # If we have a service_key, we've found a match. Update the policy.
            if service_key:
                try:
                    service_manager.UpdateServicePolicy(id=service_key, policy=service_policy)
                except vim.fault.NotFound:
                    msg = 'The service name \'{0}\' was not found.'.format(service_name)
                    log.debug(msg)
                    ret.update({host_name: {'Error': msg}})
                    continue
                except vim.fault.HostConfigFault as err:
                    msg = '\'vsphere.set_service_policy\' failed for host {0}: {1}'.format(host_name, err)
                    log.debug(msg)
                    ret.update({host_name: {'Error': msg}})
                    continue

                ret.update({host_name: True})

            if ret.get(host_name) is None:
                msg = 'Could not find service \'{0}\' for host \'{1}\'.'.format(service_name, host_name)
                log.debug(msg)
                ret.update({host_name: {'Error': msg}})

    return ret


def ssh_disable(host, username, password, protocol=None, port=None, host_names=None):
    '''
    Disable the SSH service for a given host or list of host_names.

    host
        The location of the host.

    username
        The username used to login to the host, such as ``root``.

    password
        The password used to login to the host.

    protocol
        Optionally set to alternate protocol if the host is not using the default
        protocol. Default protocol is ``https``.

    port
        Optionally set to alternate port if the host is not using the default
        port. Default port is ``443``.

    host_names
        List of ESXi host names. When the host, username, and password credentials
        are provided for a vCenter Server, the host_names argument is required to
        tell vCenter which hosts will have SSH disabled.

        If host_names is not provided, the SSH will be disabled for the ``host``
        location instead. This is useful for when service instance connection
        information is used for a single ESXi host.

    CLI Example:

    .. code-block:: bash

        # Used for single ESXi host connection information
        salt '*' vsphere.ssh_disable my.esxi.host root bad-password

        # Used for connecting to a vCenter Server
        salt '*' vsphere.ssh_disable my.vcenter.location root bad-password \
        host_names='[esxi-1.host.com, esxi-2.host.com]'
    '''
    service_instance = salt.utils.vmware.get_service_instance(host=host,
                                                              username=username,
                                                              password=password,
                                                              protocol=protocol,
                                                              port=port)
    host_names = _check_hosts(service_instance, host, host_names)
    ret = {}
    for host_name in host_names:
        host_ref = _get_host_ref(service_instance, host, host_name=host_name)
        service_manager = _get_service_manager(host_ref)
        log.debug('Disabling \'ssh\' service on {0}.'.format(host_name))
        try:
            service_manager.StopService(id='TSM-SSH')
        except vim.fault.HostConfigFault as err:
            msg = '\'vsphere.ssh_disable\' failed for host {0}: {1}'.format(host_name, err)
            log.debug(msg)
            ret.update({host_name: {'Error': msg}})
            continue

        ret.update({host_name: True})

    return ret


def ssh_enable(host, username, password, protocol=None, port=None, host_names=None):
    '''
    Enable SSH for a given host or list of host_names.

    host
        The location of the host.

    username
        The username used to login to the host, such as ``root``.

    password
        The password used to login to the host.

    protocol
        Optionally set to alternate protocol if the host is not using the default
        protocol. Default protocol is ``https``.

    port
        Optionally set to alternate port if the host is not using the default
        port. Default port is ``443``.

    host_names
        List of ESXi host names. When the host, username, and password credentials
        are provided for a vCenter Server, the host_names argument is required to
        tell vCenter which hosts will have SSH enabled.

        If host_names is not provided, the SSH will be enabled for the ``host``
        location instead. This is useful for when service instance connection
        information is used for a single ESXi host.

    CLI Example:

    .. code-block:: bash

        # Used for single ESXi host connection information
        salt '*' vsphere.ssh_enable my.esxi.host root bad-password

        # Used for connecting to a vCenter Server
        salt '*' vsphere.ssh_enable my.vcenter.location root bad-password \
        host_names='[esxi-1.host.com, esxi-2.host.com]'
    '''
    service_instance = salt.utils.vmware.get_service_instance(host=host,
                                                              username=username,
                                                              password=password,
                                                              protocol=protocol,
                                                              port=port)
    host_names = _check_hosts(service_instance, host, host_names)
    ret = {}
    for host_name in host_names:
        host_ref = _get_host_ref(service_instance, host, host_name=host_name)
        service_manager = _get_service_manager(host_ref)
        log.debug('Enabling \'ssh\' service on {0}.'.format(host_name))
        try:
            service_manager.StartService(id='TSM-SSH')
        except vim.fault.HostConfigFault as err:
            msg = '\'vsphere.ssh_enabled\' failed for host {0}: {1}'.format(host_name, err)
            log.debug(msg)
            ret.update({host_name: {'Error': msg}})
            continue

        ret.update({host_name: True})

    return ret


def ssh_restart(host, username, password, protocol=None, port=None, host_names=None):
    '''
    Restart the SSH service for a given host or list of host_names.

    host
        The location of the host.

    username
        The username used to login to the host, such as ``root``.

    password
        The password used to login to the host.

    protocol
        Optionally set to alternate protocol if the host is not using the default
        protocol. Default protocol is ``https``.

    port
        Optionally set to alternate port if the host is not using the default
        port. Default port is ``443``.

    host_names
        List of ESXi host names. When the host, username, and password credentials
        are provided for a vCenter Server, the host_names argument is required to
        tell vCenter which hosts should restart the SSH service.

        If host_names is not provided, the SSH service will be restarted for the
        ``host`` location instead. This is useful for when service instance connection
        information is used for a single ESXi host.

    CLI Example:

    .. code-block:: bash

        # Used for single ESXi host connection information
        salt '*' vsphere.ssh_restart my.esxi.host root bad-password

        # Used for connecting to a vCenter Server
        salt '*' vsphere.ssh_restart my.vcenter.location root bad-password \
        host_names='[esxi-1.host.com, esxi-2.host.com]'
    '''
    service_instance = salt.utils.vmware.get_service_instance(host=host,
                                                              username=username,
                                                              password=password,
                                                              protocol=protocol,
                                                              port=port)
    host_names = _check_hosts(service_instance, host, host_names)
    ret = {}
    for host_name in host_names:
        host_ref = _get_host_ref(service_instance, host, host_name=host_name)
        service_manager = _get_service_manager(host_ref)
        log.debug('Restarting \'ssh\' service on {0}.'.format(host_name))
        try:
            service_manager.RestartService(id='TSM-SSH')
        except vim.fault.HostConfigFault as err:
            msg = '\'vsphere.ssh_restart\' failed for host {0}: {1}'.format(host_name, err)
            log.debug(msg)
            ret.update({host_name: {'Error': msg}})
            continue

        ret.update({host_name: True})

    return ret


def update_host_datetime(host, username, password, protocol=None, port=None, host_names=None):
    '''
    Update the date/time on the given host or list of host_names. This function should be
    used with caution since network delays, execution delays can result in time skews.

    host
        The location of the host.

    username
        The username used to login to the host, such as ``root``.

    password
        The password used to login to the host.

    protocol
        Optionally set to alternate protocol if the host is not using the default
        protocol. Default protocol is ``https``.

    port
        Optionally set to alternate port if the host is not using the default
        port. Default port is ``443``.

    host_names
        List of ESXi host names. When the host, username, and password credentials
        are provided for a vCenter Server, the host_names argument is required to
        tell vCenter which hosts should update their date/time.

        If host_names is not provided, the date/time will be updated for the ``host``
        location instead. This is useful for when service instance connection
        information is used for a single ESXi host.

    CLI Example:

    .. code-block:: bash

        # Used for single ESXi host connection information
        salt '*' vsphere.update_date_time my.esxi.host root bad-password

        # Used for connecting to a vCenter Server
        salt '*' vsphere.update_date_time my.vcenter.location root bad-password \
        host_names='[esxi-1.host.com, esxi-2.host.com]'
    '''
    service_instance = salt.utils.vmware.get_service_instance(host=host,
                                                              username=username,
                                                              password=password,
                                                              protocol=protocol,
                                                              port=port)
    host_names = _check_hosts(service_instance, host, host_names)
    ret = {}
    for host_name in host_names:
        host_ref = _get_host_ref(service_instance, host, host_name=host_name)
        date_time_manager = _get_date_time_mgr(host_ref)
        try:
            date_time_manager.UpdateDateTime(datetime.datetime.utcnow())
        except vim.fault.HostConfigFault as err:
            msg = '\'vsphere.update_date_time\' failed for host {0}: {1}'.format(host_name, err)
            log.debug(msg)
            ret.update({host_name: {'Error': msg}})
            continue

        ret.update({host_name: True})

    return ret


def update_host_password(host, username, password, new_password, protocol=None, port=None):
    '''
    Update the password for a given host.

    .. note:: Currently only works with connections to ESXi hosts. Does not work with vCenter servers.

    host
        The location of the ESXi host.

    username
        The username used to login to the ESXi host, such as ``root``.

    password
        The password used to login to the ESXi host.

    new_password
        The new password that will be updated for the provided username on the ESXi host.

    protocol
        Optionally set to alternate protocol if the host is not using the default
        protocol. Default protocol is ``https``.

    port
        Optionally set to alternate port if the host is not using the default
        port. Default port is ``443``.

    CLI Example:

    .. code-block:: bash

        salt '*' vsphere.update_host_password my.esxi.host root original-bad-password new-bad-password

    '''
    service_instance = salt.utils.vmware.get_service_instance(host=host,
                                                              username=username,
                                                              password=password,
                                                              protocol=protocol,
                                                              port=port)
    # Get LocalAccountManager object
    account_manager = salt.utils.vmware.get_inventory(service_instance).accountManager

    # Create user account specification object and assign id and password attributes
    user_account = vim.host.LocalAccountManager.AccountSpecification()
    user_account.id = username
    user_account.password = new_password

    # Update the password
    try:
        account_manager.UpdateUser(user_account)
    except vim.fault.UserNotFound:
        raise CommandExecutionError('\'vsphere.update_host_password\' failed for host {0}: '
                                    'User was not found.'.format(host))
    except vim.fault.AlreadyExists:
        pass

    return True


def vsan_add_disks(host, username, password, protocol=None, port=None, host_names=None):
    '''
    Add any VSAN-eligible disks to the VSAN System for the given host or list of host_names.

    host
        The location of the host.

    username
        The username used to login to the host, such as ``root``.

    password
        The password used to login to the host.

    protocol
        Optionally set to alternate protocol if the host is not using the default
        protocol. Default protocol is ``https``.

    port
        Optionally set to alternate port if the host is not using the default
        port. Default port is ``443``.

    host_names
        List of ESXi host names. When the host, username, and password credentials
        are provided for a vCenter Server, the host_names argument is required to
        tell vCenter which hosts need to add any VSAN-eligible disks to the host's
        VSAN system.

        If host_names is not provided, VSAN-eligible disks will be added to the hosts's
        VSAN system for the ``host`` location instead. This is useful for when service
        instance connection information is used for a single ESXi host.

    CLI Example:

    .. code-block:: bash

        # Used for single ESXi host connection information
        salt '*' vsphere.vsan_add_disks my.esxi.host root bad-password

        # Used for connecting to a vCenter Server
        salt '*' vsphere.vsan_add_disks my.vcenter.location root bad-password \
        host_names='[esxi-1.host.com, esxi-2.host.com]'
    '''
    service_instance = salt.utils.vmware.get_service_instance(host=host,
                                                              username=username,
                                                              password=password,
                                                              protocol=protocol,
                                                              port=port)
    host_names = _check_hosts(service_instance, host, host_names)
    response = _get_vsan_eligible_disks(service_instance, host, host_names)

    ret = {}
    for host_name in response:
        host_ref = _get_host_ref(service_instance, host, host_name=host_name)
        vsan_system = host_ref.configManager.vsanSystem
        eligible = host_name.get('Eligible')
        error = host_name.get('Error')

        if eligible and isinstance(eligible, list):
            # If we have eligible, matching disks, add them to VSAN.
            try:
                task = vsan_system.AddDisks(eligible)
                salt.utils.vmware.wait_for_task(task, host_name, 'Adding disks to VSAN', sleep_seconds=3)
            except Exception as err:
                msg = '\'vsphere.vsan_add_disks\' failed for host {0}: {1}'.format(host_name, err)
                log.debug(msg)
                ret.update({host_name: {'Error': msg}})
                continue

            log.debug('Successfully added disks to the VSAN system for host \'{0}\'.'.format(host_name))
            ret.update({host_name: eligible})
        elif eligible and isinstance(eligible, six.string_types):
            # If we have a string type in the eligible value, we don't
            # have any VSAN-eligible disks. Pull the message through.
            ret.update({host_name: eligible})
        elif error:
            # If we hit an error, populate the Error return dict for state functions.
            ret.update({host_name: {'Error': error}})
        else:
            # If we made it this far, we somehow have eligible disks, but they didn't
            # match the disk list and just got an empty list of matching disks.
            ret.update({host_name: 'No new VSAN-eligible disks were found to add.'})

    return ret


def vsan_disable(host, username, password, protocol=None, port=None, host_names=None):
    '''
    Enable VSAN for a given host or list of host_names.

    host
        The location of the host.

    username
        The username used to login to the host, such as ``root``.

    password
        The password used to login to the host.

    protocol
        Optionally set to alternate protocol if the host is not using the default
        protocol. Default protocol is ``https``.

    port
        Optionally set to alternate port if the host is not using the default
        port. Default port is ``443``.

    host_names
        List of ESXi host names. When the host, username, and password credentials
        are provided for a vCenter Server, the host_names argument is required to
        tell vCenter which hosts should disable VSAN.

        If host_names is not provided, VSAN will be disabled for the ``host``
        location instead. This is useful for when service instance connection
        information is used for a single ESXi host.

    CLI Example:

    .. code-block:: bash

        # Used for single ESXi host connection information
        salt '*' vsphere.vsan_disable my.esxi.host root bad-password

        # Used for connecting to a vCenter Server
        salt '*' vsphere.vsan_disable my.vcenter.location root bad-password \
        host_names='[esxi-1.host.com, esxi-2.host.com]'
    '''
    service_instance = salt.utils.vmware.get_service_instance(host=host,
                                                              username=username,
                                                              password=password,
                                                              protocol=protocol,
                                                              port=port)
    # Create a VSAN Configuration Object and set the enabled attribute to True
    vsan_config = vim.vsan.host.ConfigInfo()
    vsan_config.enabled = False

    host_names = _check_hosts(service_instance, host, host_names)
    ret = {}
    for host_name in host_names:
        host_ref = _get_host_ref(service_instance, host, host_name=host_name)
        vsan_system = host_ref.configManager.vsanSystem
        if vsan_system is None:
            msg = 'VSAN System Config Manager is unset for host \'{0}\'. ' \
                  'VSAN configuration cannot be changed without a configured ' \
                  'VSAN System.'.format(host_name)
            log.debug(msg)
            ret.update({host_name: {'Error': msg}})
        else:
            try:
                # Disable vsan on the host
                task = vsan_system.UpdateVsan_Task(vsan_config)
                salt.utils.vmware.wait_for_task(task, host_name, 'Disabling VSAN', sleep_seconds=3)
            except Exception as err:
                msg = '\'vsphere.vsan_disable\' failed for host {0}: {1}'.format(host_name, err)
                log.debug(msg)
                ret.update({host_name: {'Error': msg}})
                continue

            ret.update({host_name: True})

    return ret


def vsan_enable(host, username, password, protocol=None, port=None, host_names=None):
    '''
    Enable VSAN for a given host or list of host_names.

    host
        The location of the host.

    username
        The username used to login to the host, such as ``root``.

    password
        The password used to login to the host.

    protocol
        Optionally set to alternate protocol if the host is not using the default
        protocol. Default protocol is ``https``.

    port
        Optionally set to alternate port if the host is not using the default
        port. Default port is ``443``.

    host_names
        List of ESXi host names. When the host, username, and password credentials
        are provided for a vCenter Server, the host_names argument is required to
        tell vCenter which hosts should enable VSAN.

        If host_names is not provided, VSAN will be enabled for the ``host``
        location instead. This is useful for when service instance connection
        information is used for a single ESXi host.

    CLI Example:

    .. code-block:: bash

        # Used for single ESXi host connection information
        salt '*' vsphere.vsan_enable my.esxi.host root bad-password

        # Used for connecting to a vCenter Server
        salt '*' vsphere.vsan_enable my.vcenter.location root bad-password \
        host_names='[esxi-1.host.com, esxi-2.host.com]'
    '''
    service_instance = salt.utils.vmware.get_service_instance(host=host,
                                                              username=username,
                                                              password=password,
                                                              protocol=protocol,
                                                              port=port)
    # Create a VSAN Configuration Object and set the enabled attribute to True
    vsan_config = vim.vsan.host.ConfigInfo()
    vsan_config.enabled = True

    host_names = _check_hosts(service_instance, host, host_names)
    ret = {}
    for host_name in host_names:
        host_ref = _get_host_ref(service_instance, host, host_name=host_name)
        vsan_system = host_ref.configManager.vsanSystem
        if vsan_system is None:
            msg = 'VSAN System Config Manager is unset for host \'{0}\'. ' \
                  'VSAN configuration cannot be changed without a configured ' \
                  'VSAN System.'.format(host_name)
            log.debug(msg)
            ret.update({host_name: {'Error': msg}})
        else:
            try:
                # Enable vsan on the host
                task = vsan_system.UpdateVsan_Task(vsan_config)
                salt.utils.vmware.wait_for_task(task, host_name, 'Enabling VSAN', sleep_seconds=3)
            except vim.fault.VsanFault as err:
                msg = '\'vsphere.vsan_enable\' failed for host {0}: {1}'.format(host_name, err)
                log.debug(msg)
                ret.update({host_name: {'Error': msg}})
                continue

            ret.update({host_name: True})

    return ret


def _check_hosts(service_instance, host, host_names):
    '''
    Helper function that checks to see if the host provided is a vCenter Server or
    an ESXi host. If it's an ESXi host, returns a list of a single host_name.

    If a host reference isn't found, we're trying to find a host object for a vCenter
    server. Raises a CommandExecutionError in this case, as we need host references to
    check against.
    '''
    if not host_names:
        host_name = _get_host_ref(service_instance, host)
        if host_name:
            host_names = [host]
        else:
            raise CommandExecutionError('No host reference found. If connecting to a '
                                        'vCenter Server, a list of \'host_names\' must be '
                                        'provided.')
    elif not isinstance(host_names, list):
        raise CommandExecutionError('\'host_names\' must be a list.')

    return host_names


def _get_date_time_mgr(host_reference):
    '''
    Helper function that returns a dateTimeManager object
    '''
    return host_reference.configManager.dateTimeSystem


def _get_host_ref(service_instance, host, host_name=None):
    '''
    Helper function that returns a host object either from the host location or the host_name.
    If host_name is provided, that is the host_object that will be returned.

    The function will first search for hosts by DNS Name. If no hosts are found, it will
    try searching by IP Address.
    '''
    search_index = salt.utils.vmware.get_inventory(service_instance).searchIndex

    # First, try to find the host reference by DNS Name.
    if host_name:
        host_ref = search_index.FindByDnsName(dnsName=host_name, vmSearch=False)
    else:
        host_ref = search_index.FindByDnsName(dnsName=host, vmSearch=False)

    # If we couldn't find the host by DNS Name, then try the IP Address.
    if host_ref is None:
        host_ref = search_index.FindByIp(ip=host, vmSearch=False)

    return host_ref


def _get_host_ssds(host_reference):
    '''
    Helper function that returns a list of ssd objects for a given host.
    '''
    return _get_host_disks(host_reference).get('SSDs')


def _get_host_non_ssds(host_reference):
    '''
    Helper function that returns a list of Non-SSD objects for a given host.
    '''
    return _get_host_disks(host_reference).get('Non-SSDs')


def _get_host_disks(host_reference):
    '''
    Helper function that returns a dictionary containing a list of SSD and Non-SSD disks.
    '''
    storage_system = host_reference.configManager.storageSystem
    disks = storage_system.storageDeviceInfo.scsiLun
    ssds = []
    non_ssds = []

    for disk in disks:
        try:
            has_ssd_attr = disk.ssd
        except AttributeError:
            has_ssd_attr = False
            pass
        if has_ssd_attr:
            ssds.append(disk)
        else:
            non_ssds.append(disk)

    return {'SSDs': ssds, 'Non-SSDs': non_ssds}


def _get_ntp_config(host_reference):
    '''
    Helper function that returns ntp_config information.
    '''
    return host_reference.configManager.dateTimeSystem.dateTimeInfo.ntpConfig.server


def _get_service_manager(host_reference):
    '''
    Helper function that returns a service manager object from a given host object.
    '''
    return host_reference.configManager.serviceSystem


def _get_vsan_eligible_disks(service_instance, host, host_names):
    '''
    Helper function that returns a dictionary of host_name keys with either a list of eligible
    disks that can be added to VSAN or either and 'Error' message or a message saying no
    eligible disks were found. Possible keys/values look like so:

    return = {'host_1': {'Error': 'VSAN System Config Manager is unset ...'},
              'host_2': {'Eligible': 'The host xxx does not have any VSAN eligible disks.'},
              'host_3': {'Eligible': [disk1, disk2, disk3, disk4],
              'host_4': {'Eligible': []}}
    '''
    ret = {}
    for host_name in host_names:

        # Get VSAN System Config Manager, if available.
        host_ref = _get_host_ref(service_instance, host, host_name=host_name)
        vsan_system = host_ref.configManager.vsanSystem
        if vsan_system is None:
            msg = 'VSAN System Config Manager is unset for host \'{0}\'. ' \
                  'VSAN configuration cannot be changed without a configured ' \
                  'VSAN System.'.format(host_name)
            log.debug(msg)
            ret.update({host_name: {'Error': msg}})
            continue

        # Get all VSAN suitable disks for this host.
        suitable_disks = []
        query = vsan_system.QueryDisksForVsan()
        for item in query:
            if item.state == 'eligible':
                suitable_disks.append(item)

        # No suitable disks were found to add. Warn and move on.
        # This isn't an error as the state may run repeatedly after all eligible disks are added.
        if not suitable_disks:
            msg = 'The host \'{0}\' does not have any VSAN eligible disks.'.format(host_name)
            log.warning(msg)
            ret.update({host_name: {'Eligible': msg}})
            continue

        # Get disks for host and combine into one list of Disk Objects
        disks = _get_host_ssds(host_ref) + _get_host_non_ssds(host_ref)

        # Get disks that are in both the disks list and suitable_disks lists.
        matching = []
        for disk in disks:
            for suitable_disk in suitable_disks:
                if disk.canonicalName == suitable_disk.disk.canonicalName:
                    matching.append(disk)

        ret.update({host_name: {'Eligible': matching}})

    return ret
