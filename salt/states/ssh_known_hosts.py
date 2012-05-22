'''
SSH known hosts management
==========================

Manage the information stored in the known_hosts files

.. code-block:: yaml

    github.com:
      ssh_known_hosts:
        - present
        - user: root
        - fingerprint: 16:27:ac:a5:76:28:2d:36:63:1b:56:4d:eb:df:a6:48

    example.com:
      ssh_known_hosts:
        - absent
        - user: root
'''

def present(
        name,
        user,
        fingerprint=None,
        port=None,
        enc=None,
        config='.ssh/known_hosts'):
    '''
    Verifies that the specified host is known by the specified user

    name
        The name of the remote host (i.e. "github.com")

    user
        The user who owns the ssh authorized keys file to modify

    enc
        Defines what type of key is being used, can be ssh-rsa or ssh-dss

    fingerprint
        The fingerprint of the key which must be presented in the known_hosts
        file

    port
        optional parameter, denoting the port of the remote host, which will be
        used in case, if the public key will be requested from it. By default
        the port 22 is used.

    config
        The location of the authorized keys file relative to the user's home
        directory, defaults to ".ssh/known_hosts"
    '''
    ret = {'name': name,
           'changes': {},
           'result': True,
           'comment': ''}

    result = __salt__['ssh.set_known_host'](user, name,
                fingerprint=fingerprint,
                port=port,
                enc=enc,
                config=config)
    if result['status'] == 'exists':
        return {'name': name,
                'result': None,
                'comment': '{0} already exists in {1}'.format(name, config)}
    elif result['status'] == 'error':
        return {'name': name,
                'result': False,
                'comment': result['error']}
    else:  # 'updated'
        return {'name': name,
               'result': True,
               'changes': {'old': result['old'], 'new': result['new']},
               'comment': '{0}\'s key saved to {1} (fingerprint: {2})'.format(
                           name, config, result['new']['fingerprint'])}


def absent(name, user, config='.ssh/known_hosts'):
    '''
    Verifies that the specified host is not known by the given user

    name
        The host name

    user
        The user who owns the ssh authorized keys file to modify

    config
        The location of the authorized keys file relative to the user's home
        directory, defaults to ".ssh/known_hosts"
    '''
    ret = {'name': name,
           'changes': {},
           'result': True,
           'comment': ''}
    known_host = __salt__['ssh.get_known_host'](user, name, config=config)
    if not known_host:
        return dict(ret, result=None, comment='Host is already absent')
    rm_result = __salt__['ssh.rm_known_host'](user, name, config=config)
    if rm_result['status'] == 'error':
        return dict(ret, result=False, comment=rm_result['error'])
    else:
        return dict(ret, result=True, comment=rm_result['comment'])
