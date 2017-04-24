# -*- coding: utf-8 -*-
'''
Connection module for Apache Libcloud Storage (object/blob) management for a full list
of supported clouds, see http://libcloud.readthedocs.io/en/latest/storage/supported_providers.html

.. versionadded:: Nitrogen

:configuration:
    This module uses a configuration profile for one or multiple Storage providers

    .. code-block:: yaml

        libcloud_storage:
            profile_test1:
              driver: google_storage
              key: GOOG0123456789ABCXYZ
              secret: mysecret
            profile_test2:
              driver: s3
              key: 12345
              secret: mysecret

:depends: apache-libcloud
'''
# keep lint from choking on _get_conn and _cache_id
#pylint: disable=E0602

from __future__ import absolute_import

# Import Python libs
import logging

# Import salt libs
import salt.utils.compat
from salt.utils.versions import LooseVersion as _LooseVersion

log = logging.getLogger(__name__)

# Import third party libs
REQUIRED_LIBCLOUD_VERSION = '2.0.0'
try:
    #pylint: disable=unused-import
    import libcloud
    from libcloud.storage.providers import get_driver
    #pylint: enable=unused-import
    if hasattr(libcloud, '__version__') and _LooseVersion(libcloud.__version__) < _LooseVersion(REQUIRED_LIBCLOUD_VERSION):
        raise ImportError()
    logging.getLogger('libcloud').setLevel(logging.CRITICAL)
    HAS_LIBCLOUD = True
except ImportError:
    HAS_LIBCLOUD = False


def __virtual__():
    '''
    Only load if libcloud libraries exist.
    '''
    if not HAS_LIBCLOUD:
        msg = ('A apache-libcloud library with version at least {0} was not '
               'found').format(REQUIRED_LIBCLOUD_VERSION)
        return (False, msg)
    return True


def __init__(opts):
    salt.utils.compat.pack_dunder(__name__)


def _get_driver(profile):
    config = __salt__['config.option']('libcloud_storage')[profile]
    cls = get_driver(config['driver'])
    args = config
    del args['driver']
    args['key'] = config.get('key')
    args['secret'] = config.get('secret', None)
    args['secure'] = config.get('secure', True)
    args['host'] = config.get('host', None)
    args['port'] = config.get('port', None)
    return cls(**args)


def list_containers(profile):
    '''
    Return a list of containers.

    :param profile: The profile key
    :type  profile: ``str``

    CLI Example:

    .. code-block:: bash

        salt myminion libcloud_storage.list_containers profile1
    '''
    conn = _get_driver(profile=profile)
    containers = conn.list_containers()
    ret = []
    for container in containers:
        ret.append({
            'name': container.name,
            'extra': container.extra
        })
    return ret

def list_container_objects(container_name, profile):
    '''
    List container objects (e.g. files) for the given container_id on the given profile

    :param container_name: Container name
    :type  container_name: ``str``

    :param profile: The profile key
    :type  profile: ``str``

    CLI Example:

    .. code-block:: bash

        salt myminion libcloud_storage.list_container_objects MyFolder profile1
    '''
    conn = _get_driver(profile=profile)
    container = conn.get_container(container_name)
    objects = conn.list_container_objects(container)
    ret = []
    for obj in objects:
        ret.append({
            'name': obj.name,
            'size': obj.size,
            'hash': obj.hash,
            'container': obj.container.name,
            'extra': obj.extra,
            'meta_data': obj.meta_data
        })
    return ret

def get_container(container_name, profile):
    '''
    List container details for the given container_name on the given profile

    :param container_name: Container name
    :type  container_name: ``str``

    :param profile: The profile key
    :type  profile: ``str``

    CLI Example:

    .. code-block:: bash

        salt myminion libcloud_storage.get_container MyFolder profile1
    '''
    conn = _get_driver(profile=profile)
    container = conn.get_container(container_name)
    return {
            'name': container.name,
            'extra': container.extra
            }

def download_object(container_name, object_name, destination_path, profile, 
                    overwrite_existing=False, delete_on_failure=True):
    """
    Download an object to the specified destination path.

    :param container_name: Container name
    :type  container_name: ``str``

    :param object_name: Object name
    :type  object_name: ``str``

    :param destination_path: Full path to a file or a directory where the
                                incoming file will be saved.
    :type destination_path: ``str``

    :param profile: The profile key
    :type  profile: ``str``

    :param overwrite_existing: True to overwrite an existing file,
                                defaults to False.
    :type overwrite_existing: ``bool``

    :param delete_on_failure: True to delete a partially downloaded file if
                                the download was not successful (hash
                                mismatch / file size).
    :type delete_on_failure: ``bool``

    :return: True if an object has been successfully downloaded, False
                otherwise.
    :rtype: ``bool``
    """
    conn = _get_driver(profile=profile)
    container = conn.get_container(container_name)
    obj = conn.get_object(container_name, object_name)
    return conn.download_object(obj, destination_path, overwrite_existing, delete_on_failure)

def upload_object(self, file_path, container_name, object_name, profile, extra=None,
                      verify_hash=True, headers=None):
    """
    Upload an object currently located on a disk.

    :param file_path: Path to the object on disk.
    :type file_path: ``str``

    :param container_name: Destination container.
    :type container_name: ``str``

    :param object_name: Object name.
    :type object_name: ``str``

    :param profile: The profile key
    :type  profile: ``str``

    :param verify_hash: Verify hash
    :type verify_hash: ``bool``

    :param extra: Extra attributes (driver specific). (optional)
    :type extra: ``dict``

    :param headers: (optional) Additional request headers,
        such as CORS headers. For example:
        headers = {'Access-Control-Allow-Origin': 'http://mozilla.com'}
    :type headers: ``dict``

    :rtype: :class:`Object`
    """
    conn = _get_driver(profile=profile)
    container = conn.get_container(container_name)
    obj = conn.upload_object(file_path, container, object_name, extra, verify_hash, headers)
    return obj.name
