'''
State to manage Linux kernel modules
'''

def present(name):
    '''
    Ensure that the specified kernel module is loaded
    '''
    ret = {'name': name,
           'result': True,
           'changes': {},
           'comment': ''}
    mods = __salt__['kmod.lsmod']()
    for mod in mods:
        if mod['module'] == name:
            ret['comment'] = 'Kernel module {0} is already present'.format(name)
            return ret
    # Module is not loaded, verify availability
    if not __salt__['kmod.available']().count(name):
        ret['comment'] = 'Kernel module {0} is unavailable'.format(name)
        ret['result'] = False
        return ret
    for mod in __salt__['kmod.load'](name):
        ret['changes'][mod] = 'loaded'
    if not ret['changes']:
        ret['result'] = False
        ret['comment'] = 'Failed to load kernel module {0}'.format(name)
        return ret
    ret['comment'] = 'Loaded kernel module {0}'.format(name)
    return ret

def absent(name):
    '''
    Verify that the named kernel module is not loaded
    '''
    ret = {'name': name,
           'result': True,
           'changes': {},
           'comment': ''}
    mods = __salt__['kmod.lsmod']()
    for mod in mods:
        if mod['module'] == name:
            # Found the module, unload it!
            for mod in __salt__['kmod.load'](name):
                ret['changes'][mod] = 'removed'
            for change in ret['changes']:
                if change.has_key(name):
                    ret['comment'] = 'Removed kernel module {0}'.format(name)
                    return ret
            ret['result'] = False
            ret['comment'] = 'Module {0} is present but failed to remove'.format(name)
            return ret
    ret['comment'] = 'Kernel module {0} is already absent'.format(name)
    return ret

