# -*- coding: utf-8 -*-
'''
Using states instead of maps to deploy clouds
=============================================

.. versionadded:: 2014.1.0 (Hydrogen)

Use this minion to spin up a cloud instance:

.. code-block:: yaml

    my-ec2-instance:
      cloud.profile:
        my-ec2-config
'''

import pprint
from salt._compat import string_types
import salt.utils.cloud as suc


def __virtual__():
    '''
    Only load if the cloud module is available in __salt__
    '''
    return 'cloud.profile' in __salt__


def _check_name(name):
    ret = {'name': name,
           'changes': {},
           'result': None,
           'comment': ''}
    if suc.check_name(name, 'a-zA-Z0-9._-'):
        ret['comment'] = 'Invalid characters in name.'
        ret['result'] = False
        return ret
    else:
        ret['result'] = True
        return ret


def _valid(name, comment='', changes=None):
    if not changes:
        changes = {}
    return {'name': name,
            'result': True,
            'changes': changes,
            'comment': comment}


def present(name, cloud_provider, onlyif=None, unless=None, **kwargs):
    '''
    Spin up a single instance on a cloud provider, using salt-cloud. This state
    does not take a profile argument; rather, it takes the arguments that would
    normally be configured as part of the state.

    Note that while this function does take any configuration argument that
    would normally be used to create an instance, it will not verify the state
    of any of those arguments on an existing instance. Stateful properties of
    an instance should be configured using their own individual state (i.e.,
    cloud.tagged, cloud.untagged, etc).

    name
        The name of the instance to create

    cloud_provider
        The name of the cloud provider to use

    onlyif
        Do run the state only if is unless succeed

    unless
        Do not run the state at least unless succeed
    '''
    ret = {'name': name,
           'changes': {},
           'result': None,
           'comment': ''}
    instance = __salt__['cloud.action'](
        fun='show_instance', names=[name])
    retcode = __salt__['cmd.retcode']
    prov = str([a for a in instance][0])
    if onlyif is not None:
        if not isinstance(onlyif, string_types):
            if not onlyif:
                return _valid(name, comment='onlyif execution failed')
        elif isinstance(onlyif, string_types):
            if retcode(onlyif) != 0:
                return _valid(name, comment='onlyif execution failed')
    if unless is not None:
        if not isinstance(unless, string_types):
            if unless:
                return _valid(name, comment='unless execution succeeded')
        elif isinstance(unless, string_types):
            if retcode(unless) == 0:
                return _valid(name, comment='unless execution succeeded')
    if instance and 'Not Actioned' not in prov:
        ret['result'] = True
        ret['comment'] = 'Instance {0} already exists in {1}'.format(name,
                                                                     prov)
        return ret
    if __opts__['test']:
        ret['comment'] = 'Instance {0} needs to be created'.format(name)
        return ret
    info = __salt__['cloud.create'](cloud_provider, name, **kwargs)
    if info and 'Error' not in info:
        ret['changes'] = info
        ret['result'] = True
        ret['comment'] = ('Created instance {0} using provider {1}'
                          ' and the following options: {2}').format(
            name,
            cloud_provider,
            pprint.pformat(kwargs)
        )
    elif info and 'Error' not in info:
        ret['result'] = False
        ret['comment'] = ('Failed to create instance {0}'
                          'using profile {1}: {2}').format(
            name,
            profile,
            info['Error'],
        )
    else:
        ret['result'] = False
        ret['comment'] = ('Failed to create instance {0}'
                          ' using profile {1},'
                          ' please check your configuration').format(name,
                                                                     profile)
        return ret


def absent(name, onlyif=None, unless=None):
    '''
    Ensure that no instances with the specified names exist.

    CAUTION: This is a destructive state, which will search all
    configured cloud providers for the named instance,
    and destroy it.

    name
        The name of the instance to destroy

    onlyif
        Do run the state only if is unless succeed

    unless
        Do not run the state at least unless succeed

    '''
    ret = {'name': name,
           'changes': {},
           'result': None,
           'comment': ''}
    retcode = __salt__['cmd.retcode']
    instance = __salt__['cloud.action'](fun='show_instance', names=[name])
    if not instance or \
            ('Not Actioned/Not Running' in ret
            and name in ret['Not Actioned/Not Running']):
        ret['result'] = True
        ret['comment'] = 'Instance {0} already absent'.format(name)
        return ret
    if __opts__['test']:
        ret['comment'] = 'Instance {0} needs to be destroyed'.format(name)
        return ret
    if onlyif is not None:
        if not isinstance(onlyif, string_types):
            if not onlyif:
                return _valid(name, comment='onlyif execution failed')
        elif isinstance(onlyif, string_types):
            if retcode(onlyif) != 0:
                return _valid(name, comment='onlyif execution failed')
    if unless is not None:
        if not isinstance(unless, string_types):
            if unless:
                return _valid(name, comment='unless execution succeeded')
        elif isinstance(unless, string_types):
            if retcode(unless) == 0:
                return _valid(name, comment='unless execution succeeded')
    info = __salt__['cloud.destroy'](name)
    if info and 'Error' not in info:
        ret['changes'] = info
        ret['result'] = True
        ret['comment'] = ('Destroyed instance {0}').format(
            name,
        )
    elif 'Error' in info:
        ret['result'] = False
        ret['comment'] = ('Failed to destroy instance {0}: {1}').format(
            name,
            info['Error'],
        )
    else:
        ret['result'] = False
        ret['comment'] = 'Failed to destroy instance {0}'.format(name)
    return ret


def profile(name, profile, onlyif=None, unless=None, **kwargs):
    '''
    Create a single instance on a cloud provider, using a salt-cloud profile.

    Note that while profiles used this function do take any configuration
    argument that would normally be used to create an instance using a profile,
    this state will not verify the state of any of those arguments on an
    existing instance. Stateful properties of an instance should be configured
    using their own individual state (i.e., cloud.tagged, cloud.untagged, etc).

    name
        The name of the instance to create

    profile
        The name of the cloud profile to use

    onlyif
        Do run the state only if is unless succeed

    unless
        Do not run the state at least unless succeed

    kwargs
        Any profile override or addition

    '''
    ret = {'name': name,
           'changes': {},
           'result': None,
           'comment': ''}
    retcode = __salt__['cmd.retcode']
    if onlyif is not None:
        if not isinstance(onlyif, string_types):
            if not onlyif:
                return _valid(name, comment='onlyif execution failed')
        elif isinstance(onlyif, string_types):
            if retcode(onlyif) != 0:
                return _valid(name, comment='onlyif execution failed')
    if unless is not None:
        if not isinstance(unless, string_types):
            if unless:
                return _valid(name, comment='unless execution succeeded')
        elif isinstance(unless, string_types):
            if retcode(unless) == 0:
                return _valid(name, comment='unless execution succeeded')
    instance = __salt__['cloud.action'](fun='show_instance', names=[name])
    prov = str(instance.keys()[0])
    if instance and 'Not Actioned' not in prov:
        ret['result'] = True
        ret['comment'] = 'Instance {0} already exists in {1}'.format(
            name, prov)
        return ret
    if __opts__['test']:
        ret['comment'] = 'Instance {0} needs to be created'.format(name)
        return ret
    info = __salt__['cloud.profile'](profile, name, vm_overrides=kwargs)

    # get either {Error: ''} or {namestring: {Error: ''}}
    # which is what we can get from providers returns
    main_error = info.get('Error', '')
    name_error = ''
    if isinstance(info, dict):
        subinfo = info.get(name, {})
        if isinstance(subinfo, dict):
            name_error = subinfo.get('Error', None)
    error = main_error or name_error
    if info and not error:
        node_info = info.get(name)
        ret['result'] = True
        default_msg = 'Created instance {0} using profile {1}'.format(
            name, profile,)
        # some providers support changes
        if 'changes' in node_info:
            ret['changes'] = node_info['changes']
            ret['comment'] = node_info.get('comment', default_msg)
        else:
            ret['changes'] = info
            ret['comment'] = default_msg
    elif error:
        ret['result'] = False
        ret['comment'] = ('Failed to create instance {0}'
                          ' using profile {1}: {2}').format(
            name,
            profile,
            '{0}\n{1}\n'.format(main_error, name_error).strip(),
        )
    else:
        ret['result'] = False
        ret['comment'] = ('Failed to create instance {0}'
                          'using profile {1}').format(
            name,
            profile,
        )
    return ret


def volume_present(name, provider=None, **kwargs):
    '''
    Check that a block volume exists.
    '''
    ret = _check_name(name)
    if not ret['result']:
        return ret

    volumes = __salt__['cloud.volume_list'](provider=provider)

    if name in volumes.keys():
        ret['comment'] = 'Volume exists: {0}'.format(name)
        ret['result'] = True
        return ret
    elif __opts__['test']:
        ret['comment'] = 'Volume {0} will be created.'.format(name)
        ret['result'] = None
        return ret

    response = __salt__['cloud.volume_create'](
        names=name,
        provider=provider,
        **kwargs
    )
    if response:
        ret['result'] = True
        ret['comment'] = 'Volume {0} was created'.format(name)
        ret['changes'] = {'old': None, 'new': response}
    else:
        ret['result'] = False
        ret['comment'] = 'Volume {0} failed to create.'.format(name)
    return ret


def volume_absent(name, provider=None, **kwargs):
    '''
    Check that a block volume exists.
    '''
    ret = _check_name(name)
    if not ret['result']:
        return ret

    volumes = __salt__['cloud.volume_list'](provider=provider)

    if name not in volumes.keys():
        ret['comment'] = 'Volume is absent.'
        ret['result'] = True
        return ret
    elif __opts__['test']:
        ret['comment'] = 'Volume {0} will be deleted.'.format(name)
        ret['result'] = None
        return ret

    response = __salt__['cloud.volume_delete'](
        names=name,
        provider=provider,
        **kwargs
    )
    if response:
        ret['result'] = True
        ret['comment'] = 'Volume {0} was deleted'.format(name)
        ret['changes'] = {'old': volumes[name], 'new': response}
    else:
        ret['result'] = False
        ret['comment'] = 'Volume {0} failed to delete.'.format(name)
    return ret


def volume_attached(name, server_name, provider=None, **kwargs):
    '''
    Check if a block volume is attached.
    '''
    ret = _check_name(name)
    if not ret['result']:
        return ret

    ret = _check_name(server_name)
    if not ret['result']:
        return ret

    volumes = __salt__['cloud.volume_list'](provider=provider)
    instance = __salt__['cloud.action'](
        fun='show_instance',
        names=server_name
    )

    if name in volumes.keys() and volumes[name]['attachments']:
        volume = volumes[name]
        ret['comment'] = ('Volume {name} is already'
                          'attached: {attachments}').format(**volumes[name])
        ret['result'] = True
        return ret
    elif name not in volumes.keys():
        ret['comment'] = 'Volume {0} does not exist'.format(name)
        ret['result'] = False
        return ret
    elif not instance:
        ret['comment'] = 'Server {0} does not exist'.format(server_name)
        ret['result'] = False
        return ret
    elif __opts__['test']:
        ret['comment'] = 'Volume {0} will be will be attached.'.format(
            name
        )
        ret['result'] = None
        return ret

    response = __salt__['cloud.volume_attach'](
        provider=provider,
        names=name,
        server_name=server_name,
        **kwargs
    )
    if response:
        ret['result'] = True
        ret['comment'] = 'Volume {0} was created'.format(name)
        ret['changes'] = {'old': volumes[name], 'new': response}
    else:
        ret['result'] = False
        ret['comment'] = 'Volume {0} failed to attach.'.format(name)
    return ret


def volume_detached(name, server_name=None, provider=None, **kwargs):
    '''
    Check if a block volume is attached.

    Returns True if server or Volume do not exist.
    '''
    ret = _check_name(name)
    if not ret['result']:
        return ret

    if not server_name is None:
        ret = _check_name(server_name)
        if not ret['result']:
            return ret

    volumes = __salt__['cloud.volume_list'](provider=provider)
    if server_name:
        instance = __salt__['cloud.action'](fun='show_instance', names=[name])
    else:
        instance = None

    if name in volumes.keys() and not volumes[name]['attachments']:
        volume = volumes[name]
        ret['comment'] = (
            'Volume {name} is not currently attached to anything.'
        ).format(**volumes[name])
        ret['result'] = True
        return ret
    elif name not in volumes.keys():
        ret['comment'] = 'Volume {0} does not exist'.format(name)
        ret['result'] = True
        return ret
    elif not instance and not server_name is None:
        ret['comment'] = 'Server {0} does not exist'.format(server_name)
        ret['result'] = True
        return ret
    elif __opts__['test']:
        ret['comment'] = 'Volume {0} will be will be detached.'.format(
            name
        )
        ret['result'] = None
        return ret

    response = __salt__['cloud.volume_detach'](
        provider=provider,
        names=name,
        server_name=server_name,
        **kwargs
    )
    if response:
        ret['result'] = True
        ret['comment'] = 'Volume {0} was created'.format(name)
        ret['changes'] = {'old': volumes[name], 'new': response}
    else:
        ret['result'] = False
        ret['comment'] = 'Volume {0} failed to detach.'.format(name)
    return ret
