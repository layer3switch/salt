# -*- coding: utf-8 -*-
'''
Apache Libcloud Storage State
=============================

Manage cloud storage using libcloud

    :codeauthor: :email:`Anthony Shaw <anthonyshaw@apache.org>`

Apache Libcloud Storage (object/blob) management for a full list
of supported clouds, see http://libcloud.readthedocs.io/en/latest/storage/supported_providers.html

Clouds include Amazon S3, Google Storage, Aliyun, Azure Blobs, Ceph, OpenStack swift

.. versionadded:: Oxygen

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

Examples
--------

Creating a container and uploading a file
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: yaml

    web_things:
      libcloud_storage.container_present:
        name: my_container_name  
        profile: profile1
      libcloud_storage.object_present:
        name: my_file.jpg
        container: my_container_name
        path: /path/to/local/file.jpg
        profile: profile1

Downloading a file
~~~~~~~~~~~~~~~~~~

This example will download the file from the remote cloud and keep it locally

.. code-block:: yaml

    web_things:
      libcloud_storage.file_present:
        object_name: my_file.jpg
        container: my_container_name
        path: /path/to/local/file.jpg
        profile: profile1

:depends: apache-libcloud
'''

# Import Python Libs
from __future__ import absolute_import
import logging

# Import salt libs
import salt.utils

log = logging.getLogger(__name__)


def __virtual__():
    return True


def __init__(opts):
    salt.utils.compat.pack_dunder(__name__)


def state_result(result, message):
    return {'result': result, 'comment': message}


def container_present(name, profile):
    '''
    Ensures a container is present.

    :param name: Container name
    :type  name: ``str``

    :param profile: The profile key
    :type  profile: ``str``
    '''
    containers = __salt__['libcloud_dns.list_containers'](profile)
    
    match = [z for z in containers if z.name == name]
    if len(match) > 0:
        return state_result(True, "Container already exists")
    else:
        result = __salt__['libcloud_dns.create_container'](name, profile)
        return state_result(result, "Created new container")


def container_absent(name, profile):
    '''
    Ensures a container is absent.

    :param name: Container name
    :type  name: ``str``

    :param profile: The profile key
    :type  profile: ``str``
    '''
    containers = __salt__['libcloud_dns.list_containers'](profile)
    
    match = [z for z in containers if z.name == name]
    if len(match) == 0:
        return state_result(True, "Container already absent")
    else:
        result = __salt__['libcloud_dns.delete_container'](name, profile)
        return state_result(result, "Deleted container")
