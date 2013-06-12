'''
Management of Portage package configuration on Gentoo
=====================================================

A state module to manage Portage configuration on Gentoo

.. code-block:: yaml

    salt:
        portage_config.flags:
            - use:
                - openssl
'''

def __virtual__():
    '''
    Only load if the portage_config module is available in __salt__
    '''
    return 'portage_config' if 'portage_config.get_missing_flags' in __salt__ else False

def mod_init(low):
    '''
    Enforce a nice structure on the configuration files.
    '''
    try:
        __salt__['portage_config.enforce_nice_config']()
    except:
        return False
    return True

def _flags_helper(conf, atom, flags, test=False):
    import traceback
    try:
        flags = __salt__['portage_config.get_missing_flags'](conf, atom, flags)
    except:
        return {'result': False, 'comment': traceback.format_exc()}
    if flags:
        old_flags = __salt__['portage_config.get_flags_from_package_conf'](conf, atom)
        if not test:
            __salt__['portage_config.append_to_package_conf'](conf, atom, flags)
        return {'result': True,'changes':{'old': old_flags, 'new': flags}}
    return {'result': None}

def _mask_helper(conf, atom, test=False):
    import traceback
    try:
        is_present = __salt__['portage_config.is_present'](conf, atom)
    except:
        return {'result': False, 'comment': traceback.format_exc()}
    if not is_present:
        if not test:
            __salt__['portage_config.append_to_package_conf'](conf, string = atom)
        return {'result': True}
    return {'result': None}

def flags(name, use=[], accept_keywords=[], env=[], license=[], properties=[], unmask=False, mask=False):
    '''
    Enforce the given flags on the given package or DEPEND atom.
    Please be warned that, in most cases, you need to rebuild the affected packages in
    order to apply the changes.

    name
        The name of the package or his DEPEND atom
    use
        A list of use flags
    accept_keywords
        A list of keywords to accept. "~ARCH" means current host arch, and will
        be translated in a line without keywords
    env
        A list of enviroment files
    license
        A list of accepted licenses
    properties
        A list of additional properties
    unmask
        A boolean to unmask the package
    mask
        A boolean to mask the package
    '''
    ret = {'changes': {},
           'comment': '',
           'name': name,
           'result': True}

    if use:
        result = _flags_helper('use', name, use, __opts__['test'])
        if result['result']:
            ret['changes']['use'] = c
        elif result['result']==False:
            ret['result'] = False
            ret['comment'] = result['comment']
            return ret

    if accept_keywords:
        result = _flags_helper('accept_keywords', name, accept_keywords, __opts__['test'])
        if result['result']:
            ret['changes']['accept_keywords'] = result['changes']
        elif result['result']==False:
            ret['result'] = False
            ret['comment'] = result['comment']
            return ret

    if env:
        result = _flags_helper('env', name, env, __opts__['test'])
        if result['result']:
            ret['changes']['env'] = result['changes']
        elif result['result']==False:
            ret['result'] = False
            ret['comment'] = result['comment']
            return ret

    if license:
        result = _flags_helper('license', name, license, __opts__['test'])
        if result['result']:
            ret['changes']['license'] = result['changes']
        elif result['result']==False:
            ret['result'] = False
            ret['comment'] = result['comment']
            return ret

    if properties:
        result = _flags_helper('properties', name, properties, __opts__['test'])
        if result['result']:
            ret['changes']['properties'] = result['changes']
        elif result['result']==False:
            ret['result'] = False
            ret['comment'] = result['comment']
            return ret

    if mask:
        result = _mask_helper('mask', name, __opts__['test'])
        if result['result']:
            ret['changes']['mask'] = 'masked'
        elif result['result']==False:
            ret['result'] = False
            ret['comment'] = result['comment']
            return ret

    if unmask:
        result = _mask_helper('unmask', name, __opts__['test'])
        if result['result']:
            ret['changes']['unmask'] = 'unmasked'
        elif result['result']==False:
            ret['result'] = False
            ret['comment'] = result['comment']
            return ret

    if __opts__['test']:
        ret['result'] = None

    return ret
