# -*- coding: utf-8 -*-
'''
Network Config
==============

Manage the configuration on a network device given a specific static config or template.

:codeauthor: Mircea Ulinic <mircea@cloudflare.com> & Jerome Fleury <jf@cloudflare.com>
:maturity:   new
:depends:    napalm
:platform:   unix

Dependencies
------------
- :mod:`NAPALM proxy minion <salt.proxy.napalm>`
- :mod:`Network-related basic features execution module <salt.modules.napalm_network>`

.. versionadded: 2016.11.1
'''


from __future__ import absolute_import

import logging
log = logging.getLogger(__name__)

# third party libs
try:
    # will try to import NAPALM
    # https://github.com/napalm-automation/napalm
    # pylint: disable=W0611
    from napalm_base import get_network_driver
    # pylint: enable=W0611
    HAS_NAPALM = True
except ImportError:
    HAS_NAPALM = False

# ----------------------------------------------------------------------------------------------------------------------
# state properties
# ----------------------------------------------------------------------------------------------------------------------

__virtualname__ = 'netconfig'

# ----------------------------------------------------------------------------------------------------------------------
# global variables
# ----------------------------------------------------------------------------------------------------------------------

# ----------------------------------------------------------------------------------------------------------------------
# property functions
# ----------------------------------------------------------------------------------------------------------------------


def __virtual__():

    '''
    NAPALM library must be installed for this module to work.
    Also, the key proxymodule must be set in the __opts___ dictionary.
    '''

    if HAS_NAPALM and 'proxy' in __opts__:
        return __virtualname__
    else:
        return (False, 'The network config state (netconfig) cannot be loaded: \
                NAPALM or proxy could not be loaded.')

# ----------------------------------------------------------------------------------------------------------------------
# helper functions -- will not be exported
# ----------------------------------------------------------------------------------------------------------------------


def _default_ret(name):
    '''
    Return the default dict of the state output.
    '''
    ret = {
        'name': name,
        'changes': {},
        'already_configured': False,
        'loaded_config': '',
        'result': False,
        'comment': ''
    }
    return ret


def _update_config(template_name,
                   template_source=None,
                   template_path=None,
                   template_hash=None,
                   template_hash_name=None,
                   template_user='root',
                   template_group='root',
                   template_mode='755',
                   saltenv=None,
                   template_engine='jinja',
                   skip_verify=True,
                   defaults=None,
                   test=False,
                   commit=True,
                   debug=False,
                   replace=False,
                   **template_vars):
    '''
    Call the necessary functions in order to execute the state.
    For the moment this only calls the ``net.load_template`` function from the
    :mod:`Network-related basic features execution module <salt.modules.napalm_network>`, but this may change in time.
    '''

    return __salt__['net.load_template'](template_name,
                                         template_source=template_source,
                                         template_path=template_path,
                                         template_hash=template_hash,
                                         template_hash_name=template_hash_name,
                                         template_user=template_user,
                                         template_group=template_group,
                                         template_mode=template_mode,
                                         saltenv=saltenv,
                                         template_engine=template_engine,
                                         skip_verify=skip_verify,
                                         defaults=defaults,
                                         test=test,
                                         commit=commit,
                                         debug=debug,
                                         replace=replace,
                                         **template_vars)

# ----------------------------------------------------------------------------------------------------------------------
# callable functions
# ----------------------------------------------------------------------------------------------------------------------


def managed(name,
            template_name,
            template_source=None,
            template_path=None,
            template_hash=None,
            template_hash_name=None,
            template_user='root',
            template_group='root',
            template_mode='755',
            saltenv=None,
            template_engine='jinja',
            skip_verify=True,
            defaults=None,
            test=False,
            commit=True,
            debug=False,
            replace=False,
            **template_vars):

    '''
    Manages the configuration on network devices.

    By default this state will commit the changes on the device. If there are no changes required, it does not commit
    and the field ``already_configured`` from the output dictionary will be set as ``True`` to notify that.

    To avoid committing the configuration, set the argument ``test`` to ``True`` (or via the CLI argument ``test=True``)
    and will discard (dry run).

    To preserve the chnages, set ``commit`` to ``False`` (either as CLI argument, either as state parameter).
    However, this is recommended to be used only in exceptional cases when there are applied few consecutive states
    and/or configuration changes. Otherwise the user might forget that the config DB is locked and the candidate config
    buffer is not cleared/merged in the running config.

    To replace the config, set ``replace`` to ``True``. This option is recommended to be used with caution!

    template_name
        Identifies path to the template source. The template can be either stored on the local machine,
        either remotely. When locally, the absolute path must be provided. Otherwise, the source can be retrieved via
        ``http``, ``https`` or ``ftp``. Examples:

        - ``/absolute/path/to/my_template.jinja``
        - ``http://example.com/template.cheetah``
        - ``https:/example.com/template.mako``
        - ``ftp://example.com/template.py``

        The file extension is not mandatory, but the content must correspond to the ``template_engine``
        specified (default: ``Jinja``).

    template_source: None
        Inline config template to be rendered and loaded on the device.

    template_path: None
        Required only in case the argument ``template_name`` provides only the file basename.
        E.g.: if ``template_name`` is specified as ``my_template.jinja``, in order to find the
        template, this argument must be provided: ``template_path: /absolute/path/to/``.

    template_hash: None
        Hash of the template file. Format: ``{hash_type: 'md5', 'hsum': <md5sum>}``

    template_hash_name: None
        When ``template_hash`` refers to a remote file, this specifies the filename to look for in that file.

    template_group: root
        Owner of file.

    template_user: root
        Group owner of file.

    template_user: 755
        Permissions of file

    saltenv: base
        Specifies the template environment. This will influence the relative imports inside the templates.

    template_engine: jinja
        The following templates engines are supported:

        - :mod:`cheetah<salt.renderers.cheetah>`
        - :mod:`genshi<salt.renderers.genshi>`
        - :mod:`jinja<salt.renderers.jinja>`
        - :mod:`mako<salt.renderers.mako>`
        - :mod:`py<salt.renderers.py>`
        - :mod:`wempy<salt.renderers.wempy>`

    skip_verify: True
        If ``True``, hash verification of remote file sources (``http://``, ``https://``, ``ftp://``) will be skipped,
        and the ``source_hash`` argument will be ignored.

    test: False
        Dry run? If set to ``True``, will apply the config, discard and return the changes. Default: ``False``
        (will commit the changes on the device).

    commit: True
        Commit? Default: ``True``.

    debug: False
        Debug mode. Will insert a new key under the output dictionary, as ``loaded_config`` contaning the raw
        result after the template was rendered.

    replace: False
        Load and replace the configuration. Default: ``False`` (will apply load merge).

    defaults: None
        Default variables/context passed to the template.

    **template_vars
        Dictionary with the arguments/context to be used when the template is rendered. Do not explicitely specify this
        argument. This represents any other variable that will be sent to the template rendering system. Please
        see an example below! In both ``ntp_peers_example_using_pillar`` and ``ntp_peers_example``, ``peers`` is sent as
        template variable.

    SLS Example (e.g.: under salt://router/config.sls) :

    .. code-block:: yaml

        whole_config_example:
            netconfig.managed:
                - template_name: salt://path/to/complete_config.jinja
                - debug: True
                - replace: True
        bgp_config_example:
            netconfig.managed:
                - template_name: /absolute/path/to/bgp_neighbors.mako
                - template_engine: mako
        prefix_lists_example:
            netconfig.managed:
                - template_name: prefix_lists.cheetah
                - template_path: /absolute/path/to/
                - debug: True
                - template_engine: cheetah
        ntp_peers_example:
            netconfig.managed:
                - template_name: http://bit.ly/2gKOj20
                - skip_verify: False
                - debug: True
                - peers:
                    - 192.168.0.1
                    - 192.168.0.1
        ntp_peers_example_using_pillar:
            netconfig.managed:
                - template_name: http://bit.ly/2gKOj20
                - peers: {{ pillar.get('ntp.peers', []) }}

    Usage examples:

    .. code-block:: bash

        $ sudo salt 'juniper.device' state.sls router.config test=True

        $ sudo salt -N all-routers state.sls router.config debug=True

    ``router.config`` depends on the location of the SLS file (see above). Running this command, will be executed all
    five steps from above. These examples above are not meant to be used in a production environment, their sole purpose
    is to provide usage examples.

    Output example:

    .. code-block:: bash

        $ sudo salt 'juniper.device' state.sls router.config test=True
        juniper.device:
        ----------
                  ID: ntp_peers_example_using_pillar
            Function: netconfig.managed
              Result: None
             Comment: Testing mode: Configuration discarded.
             Started: 12:01:40.744535
            Duration: 8755.788 ms
             Changes:
                      ----------
                      diff:
                          [edit system ntp]
                               peer 192.168.0.1 { ... }
                          +    peer 172.17.17.1;
                          +    peer 172.17.17.3;

        Summary for juniper.device
        ------------
        Succeeded: 1 (unchanged=1, changed=1)
        Failed:    0
        ------------
        Total states run:     1
        Total run time:   8.756 s

    Raw output example (useful when the output is reused in other states/execution modules):

    .. code-block:: python

        $ sudo salt --out=pprint 'juniper.device' state.sls router.config test=True debug=True
        {
            'juniper.device': {
                'netconfig_|-ntp_peers_example_using_pillar_|-ntp_peers_example_using_pillar_|-managed': {
                    '__id__': 'ntp_peers_example_using_pillar',
                    '__run_num__': 0,
                    'already_configured': False,
                    'changes': {
                        'diff': '[edit system ntp]   peer 192.168.0.1 { ... }+   peer 172.17.17.1;+   peer 172.17.17.3;'
                    },
                    'comment': 'Testing mode: Configuration discarded.',
                    'duration': 7400.759,
                    'loaded_config': 'system {\n  ntp {\n  peer 172.17.17.1;\n  peer 172.17.17.3;\n}\n}\n',
                    'name': 'ntp_peers_example_using_pillar',
                    'result': None,
                    'start_time': '12:09:09.811445'
                }
            }
        }
    '''

    ret = _default_ret(name)

    # the user can override the flags the equivalent CLI args
    # which have higher precedence
    test = __opts__.get('test', test)
    debug = __opts__.get('debug', debug)
    commit = __opts__.get('commit', commit)
    replace = __opts__.get('replace', replace)  # this might be a bit risky
    skip_verify = __opts__.get('skip_verify', skip_verify)

    config_update_ret = _update_config(template_name,
                                       template_source=template_source,
                                       template_path=template_path,
                                       template_hash=template_hash,
                                       template_hash_name=template_hash_name,
                                       template_user=template_user,
                                       template_group=template_group,
                                       template_mode=template_mode,
                                       saltenv=saltenv,
                                       template_engine=template_engine,
                                       skip_verify=skip_verify,
                                       defaults=defaults,
                                       test=test,
                                       commit=commit,
                                       debug=debug,
                                       replace=replace,
                                       **template_vars)

    _apply_res = config_update_ret.get('result', False)
    result = (_apply_res if not _apply_res else None) if test else _apply_res
    _comment = config_update_ret.get('comment', '')
    comment = _comment if not test else 'Testing mode: {tail}'.format(tail=_comment)

    if result is True and not comment:
        comment = 'Configuration changed!'

    ret.update({
        'changes': {
            'diff': config_update_ret.get('diff', '')
        },
        'already_configured': config_update_ret.get('already_configured', False),
        'result': result,
        'comment': comment,
        'loaded_config': config_update_ret.get('loaded_config', ''),
    })

    return ret
