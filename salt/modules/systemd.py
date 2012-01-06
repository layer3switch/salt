'''
Provide the service module for systemd
'''

def __virtual__():
    '''
    Only work on systems which default to systemd
    '''
    if __grains__['os'] == 'Fedora' and __grains__['osrelease'] > 15:
        return 'service'
    return False

def start(name):
    '''
    Start the specified service with systemd

    CLI Example::

        salt '*' service.start <service name>
    '''
    cmd = 'systemctl start {0}.service'.format(name)
    return not __salt__['cmd.retcode'](cmd)

def stop(name):
    '''
    Stop the specifed service with systemd

    CLI Example::

    salt '*' service.stop <service name>
    '''
    cmd = 'systemctl stop {0}.service'.format(name)
    return not __salt__['cmd.retcode'](cmd)

def restart(name):
    '''
    Start the specified service with systemd

    CLI Example::

        salt '*' service.start <service name>
    '''
    cmd = 'systemctl restart {0}.service'.format(name)
    return not __salt__['cmd.retcode'](cmd)

def status(name):
    '''
    Return the status for a service via systemd, returns the PID if the service
    is running or an empty string if the service is not running

    CLI Example::

        salt '*' service.status <service name>
    '''
    cmd = ("systemctl restart {0}.service"
           " | awk '/Main PID/{print $3}'").format(name)
    return __salt__['cmd.run'](cmd).strip()

def enable(name):
    '''
    Enable the named service to start when the system boots

    CLI Example::

        salt '*' service.enable <service name>
    '''
    cmd = 'systemctl enable {0}.service'.format(name)
    return not __salt__['cmd.retcode'](cmd)

def disable(name):
    '''
    Disable the named service to not start when the system boots

    CLI Example::

        salt '*' service.disable <service name>
    '''
    cmd = 'systemctl disable {0}.service'.format(name)
    return not __salt__['cmd.retcode'](cmd)
