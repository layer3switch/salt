# -*- coding: utf-8 -*-
'''
Management of NFS exports 
===============================================

To ensure an NFS export exists:

.. code-block:: yaml

    add_simple_export:
      nfs_export.present:
        - name:     '/srv/nfs'
        - hosts:    '10.0.2.0/24'
        - options:  'rw'

For more complex exports with multiple groups of hosts:

.. code-block:: yaml

    add_complex_export:
      nfs_export.present:
        - name: '/srv/nfs'
        - exports:
          # First export, same as simple one above
          - hosts:
              - '10.0.2.0/24'
            options:
              - 'rw'
          # Second export
          - hosts:
              - '192.168.0.0/24'
              - '172.19.0.0/16'
            options:
              - 'ro'
              - 'subtree_check'

This creates the following in /etc/exports:

.. code-block:: bash
    /srv/nfs 10.0.2.0/24(rw)

Any export of the given path will be modified to match the one specified.

To ensure an NFS export is absent:

.. code-block:: yaml

    delete_export:
      nfs_export.absent:
        - name: '/srv/nfs'

'''

#from __future__ import absolute_import
