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
import salt.utils.vmware
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
        vCenter which hosts for which to get date/time information.

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
        vCenter which hosts for which to get ntp configuration information.

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


def get_ssh_running(host, username, password, protocol=None, port=None, host_names=None):
    '''
    Get the SSH running status for a given host or a list of host_names. Returns True if
    the SSH service is running, False if it is not running, per host.

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
        salt '*' vsphere.get_ssh_running my.esxi.host root bad-password

        # Used for connecting to a vCenter Server
        salt '*' vsphere.get_ssh_running my.vcenter.location root bad-password \
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
            if service.label == 'SSH':
                ret.update({host_name: service.running})
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
            log.debug('VSAN System Config Manager is unset for host \'{0}\'.'.format(host_name))
            ret.update({host_name: None})
        else:
            ret.update({host_name: vsan_config.enabled})

    return ret


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
            raise CommandExecutionError('vsphere.ntp_configure_servers failed: {0}'.format(err))

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
            except vim.fault.HostConfigFault as msg:
                raise CommandExecutionError('\'vsphere.ntp_restart\' failed: {0}'.format(msg))
            except vim.fault.RestrictedVersion as msg:
                raise CommandExecutionError(msg)
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
            except vim.fault.HostConfigFault as msg:
                raise CommandExecutionError('\'vsphere.ntp_start\' failed: {0}'.format(msg))
            except vim.fault.RestrictedVersion as msg:
                raise CommandExecutionError(msg)
            ret.update({host_name: ntp_config})
        else:
            log.warning('Unable to start the \'ntpd\' service. '
                        'NTP servers have not been configured for \'{0}\'.'.format(host_name))
            ret.update({host_name: None})

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
            except vim.fault.HostConfigFault as msg:
                raise CommandExecutionError('\'vsphere.ntp_stop\' failed: {0}'.format(msg))
            except vim.fault.RestrictedVersion as msg:
                raise CommandExecutionError(msg)
            ret.update({host_name: ntp_config})
        else:
            log.warning('Unable to stop the \'ntpd\' service. '
                        'NTP servers have not been configured for \'{0}\'.'.format(host_name))
            ret.update({host_name: None})
    
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
        except vim.fault.HostConfigFault as msg:
            raise CommandExecutionError('\'vsphere.ssh_disable\' failed for host {0}: {1}'.format(
                host_name,
                msg
            ))

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
        except vim.fault.HostConfigFault as msg:
            raise CommandExecutionError('\'vsphere.ssh_enabled\' failed for host {0}: {1}'.format(
                host_name,
                msg
            ))

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
        except vim.fault.HostConfigFault as msg:
            raise CommandExecutionError('\'vsphere.ssh_restart\' failed for host {0}: {1}'.format(
                host_name,
                msg
            ))

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
            raise CommandExecutionError('\'vsphere.update_date_time\' failed for host {0}: {1}'.format(
                host_name,
                err
            ))
        ret.update({host: True})

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
    ret = {}
    for host_name in host_names:
        if ret.get(host_name) is None:
            ret.update({host_name: {}})

        # Get VSAN System Config Manager, if available.
        host_ref = _get_host_ref(service_instance, host, host_name=host_name)
        vsan_system = host_ref.configManager.vsanSystem
        if vsan_system is None:
            log.warning('VSAN System Config Manager is unset for host \'{0}\'. '
                        'VSAN configuration cannot be changed without a configured '
                        'VSAN System.'.format(host_name))
            ret.update({host_name: False})
            continue

        # Get all VSAN suitable disks for this host.
        suitable_disks = []
        query = vsan_system.QueryDisksForVsan()
        for item in query:
            if item.state == 'eligible':
                suitable_disks.append(item)

        if not suitable_disks:
            log.warning('The host \'{0}\' does not have any VSAN eligible disks.'.format(host_name))
            ret.update({host_name: False})
            continue

        # Get disks for host and combine into one list of Disk Objects
        disks = _get_host_ssds(host_ref) + _get_host_non_ssds(host_ref)

        # Get disks that are in both the disks list and suitable_disks lists.
        matching = []
        for disk in disks:
            for suitable_disk in suitable_disks:
                if disk.canonicalName == suitable_disk.disk.canonicalName:
                    matching.append(disk)

        for disk in matching:
            disk_name = disk.canonicalName
            try:
                task = vsan_system.AddDisks(disk)
            except vim.fault.VsanFault as err:
                log.error('\'vsphere.vsan_add_disks\' failed for host {0}: {1}'.format(host_name, err))
                ret[host_name].update({disk_name: False})
                continue
            # Check if the task returned successfully or if there was an error.
            if task.info.state == 'success':
                log.debug('Successfully added disk \'{0}\' to the VSAN system.'.format(disk_name))
                ret[host_name].update({disk_name: True})
            else:
                log.error('There was an error adding disk \'{0}\' to the '
                          'VSAN system: {1}'.format(disk_name, task.info.error.msg))
                ret[host_name].update({disk_name: False})

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
            log.warning('VSAN System Config Manager is unset for host \'{0}\'. '
                        'VSAN configuration cannot be changed without a configured '
                        'VSAN System.'.format(host_name))
            ret.update({host_name: False})
        else:
            try:
                # Disable vsan on the host
                vsan_system.UpdateVsan_Task(vsan_config)
            except vim.fault.VsanFault as err:
                raise CommandExecutionError('\'vsphere.vsan_disable\' failed for host {0}: {1}'.format(
                    host_name,
                    err
                ))

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
            log.warning('VSAN System Config Manager is unset for host \'{0}\'. '
                        'VSAN configuration cannot be changed without a configured '
                        'VSAN System.'.format(host_name))
            ret.update({host_name: False})
        else:
            try:
                # Enable vsan on the host
                vsan_system.UpdateVsan_Task(vsan_config)
            except vim.fault.VsanFault as err:
                raise CommandExecutionError('\'vsphere.vsan_enable\' failed for host {0}: {1}'.format(
                    host_name,
                    err
                ))

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
