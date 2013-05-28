'''
Support for reboot, shutdown, etc
'''

import salt.utils


def __virtual__():
    '''
    This only supports Windows
    '''
    if not salt.utils.is_windows():
        return False
    return 'system'


def halt():
    '''
    Halt a running system
    
    CLI Example::
    
        salt '*' system.halt
    '''
    cmd = 'shutdown /s'
    ret = __salt__['cmd.run'](cmd)
    return ret


def init(runlevel):
    '''
    Change the system runlevel on sysV compatible systems
    
    CLI Example::
    
        salt '*' system.init 3
    '''
    #cmd = 'init {0}'.format(runlevel)
    #ret = __salt__['cmd.run'](cmd)
    #return ret

    # TODO: Create a mapping of runlevels to 
    #       corresponding Windows actions

    return 'Not implemented on Windows yet.'


def poweroff():
    '''
    Poweroff a running system
    
    CLI Example::
    
        salt '*' system.poweroff
    '''
    cmd = 'shutdown /s'
    ret = __salt__['cmd.run'](cmd)
    return ret


def reboot():
    '''
    Reboot the system using the 'reboot' command
    
    CLI Example::
    
        salt '*' system.reboot
    '''
    cmd = 'reboot'
    ret = __salt__['cmd.run'](cmd)
    return ret


def shutdown():
    '''
    Shutdown a running system
    
    CLI Example::
    
        salt '*' system.shutdown
    '''
    cmd = 'shutdown /s'
    ret = __salt__['cmd.run'](cmd)
    return ret

