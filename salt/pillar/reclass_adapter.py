# -*- coding: utf-8 -*-
'''
.. |reclass| replace:: **reclass**

This ``ext_pillar`` plugin provides access to the |reclass| database, such
that Pillar data for a specific minion are fetched using |reclass|.

You can find more information about |reclass| at
http://reclass.pantsfullofunix.net.

To use the plugin, add it to the ``ext_pillar`` list in the Salt master config
and tell |reclass| by way of a few options how and where to find the
inventory:

.. code-block:: yaml

    ext_pillar:
        - reclass:
            storage_type: yaml_fs
            base_inventory_uri: /srv/salt

This would cause |reclass| to read the inventory from YAML files in
``/srv/salt/nodes`` and ``/srv/salt/classes``.

If you are also using |reclass| as ``master_tops`` plugin, and you want to
avoid having to specify the same information for both, use YAML anchors (take
note of the differing data types for ``ext_pillar`` and ``master_tops``):

.. code-block:: yaml

    reclass: &reclass
        storage_type: yaml_fs
        base_inventory_uri: /srv/salt
        reclass_source_path: ~/code/reclass

    ext_pillar:
        - reclass: *reclass

    master_tops:
        reclass: *reclass

If you want to run reclass from source, rather than installing it, you can
either let the master know via the ``PYTHONPATH`` environment variable, or by
setting the configuration option, like in the example above.
'''

# This file cannot be called reclass.py, because then the module import would
# not work. Thanks to the __virtual__ function, however, the plugin still
# responds to the name 'reclass'.

from salt.utils.reclass import (
    prepend_reclass_source_path,
    filter_out_source_path_option,
    set_inventory_base_uri_default
)


def __virtual__(retry=False):
    try:
        import reclass
        return 'reclass'

    except ImportError as e:
        if retry:
            return False

        for pillar in __opts__.get('ext_pillar', []):
            if 'reclass' not in pillar.keys():
                continue

            # each pillar entry is a single-key hash of name -> options
            opts = pillar.values()[0]
            prepend_reclass_source_path(opts)
            break

        return __virtual__(retry=True)


from salt.exceptions import SaltInvocationError

def ext_pillar(minion_id, pillar, **kwargs):
    '''
    Obtain the Pillar data from **reclass** for the given ``minion_id``.
    '''

    # If reclass is installed, __virtual__ put it onto the search path, so we
    # don't need to protect against ImportError:
    from reclass.adapters.salt import ext_pillar as reclass_ext_pillar
    from reclass.errors import ReclassException

    try:
        # the source path we used above isn't something reclass needs to care
        # about, so filter it:
        filter_out_source_path_option(kwargs)

        # if no inventory_base_uri was specified, initialize it to the first
        # file_roots of class 'base' (if that exists):
        set_inventory_base_uri_default(__opts__, kwargs)

        # I purposely do not pass any of __opts__ or __salt__ or __grains__
        # to reclass, as I consider those to be Salt-internal and reclass
        # should not make any assumptions about it.
        return reclass_ext_pillar(minion_id, pillar, **kwargs)

    except TypeError as e:
        if 'unexpected keyword argument' in e.message:
            arg = e.message.split()[-1]
            raise SaltInvocationError('ext_pillar.reclass: unexpected option: '
                                      + arg)
        else:
            raise

    except KeyError as e:
        if 'id' in e.message:
            raise SaltInvocationError('ext_pillar.reclass: __opts__ does not '
                                      'define minion ID')
        else:
            raise

    except ReclassException as e:
        raise SaltInvocationError('ext_pillar.reclass: {0}'.format(e.message))
