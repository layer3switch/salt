.. _client-apis:
.. _python-api:

=================
Python client API
=================

Salt provides several entry points for interfacing with Python applications.
These entry points are often referred to as ``*Client()`` APIs. Each client
accesses different parts of Salt, either from the master or from a minion. Each
client is detailed below.

.. seealso:: There are many ways to access Salt programmatically.

    Salt can be used from CLI scripts as well as via a REST interface.

    See Salt's :ref:`outputter system <all-salt.output>` to retrive structured
    data from Salt as JSON, or as shell-friendly text, or many other formats.

    See the :py:func:`state.event <salt.runners.state.event>` runner to utilize
    Salt's event bus from shell scripts.

    See the `salt-api`_ project to access Salt externally via a REST interface.
    It uses Salt's Python interface documented below and is also useful as a
    reference implementation.

.. _`salt-api`: https://github.com/saltstack/salt-api

Salt's ``opts`` dictionary
==========================

Some clients require access to Salt's ``opts`` dictionary. (The dictionary
representation of the :ref:`master <configuration-salt-master>` or
:ref:`minion <configuration-salt-minion>` config files.)

A common pattern for fetching the ``opts`` dictionary is to defer to
environment variables if they exist or otherwise fetch the config from the
default location.

.. autofunction:: salt.config.client_config

.. autofunction:: salt.config.minion_config

Salt's Loader Interface
=======================

Modules in the Salt ecosystem are loaded into memory using a custom loader
system. This allows modules to have conditional requirements (OS, OS version,
installed libraries, etc) and allows Salt to inject special variables
(``__salt__``, ``__opts``, etc).

Each module type has a corresponding loader function.

.. autofunction:: salt.loader.minion_mods

.. autofunction:: salt.loader.raw_mod

.. autofunction:: salt.loader.states

.. autofunction:: salt.loader.grains

Salt's Client Interfaces
========================

LocalClient
-----------

.. autoclass:: salt.client.LocalClient
    :members: cmd, run_job, cmd_async, cmd_subset, cmd_batch, cmd_iter,
        cmd_iter_no_block, get_cli_returns, get_event_iter_returns

Salt Caller
-----------

.. autoclass:: salt.client.Caller
    :members: function

RunnerClient
------------

.. autoclass:: salt.runner.RunnerClient
    :members:

WheelClient
-----------

.. autoclass:: salt.wheel.WheelClient
    :members:

CloudClient
-----------

.. autoclass:: salt.cloud.CloudClient
    :members:
