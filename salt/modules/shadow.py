'''
Manage the shadow file
'''
# Import python libs
import os
import spwd

def info(name):
    '''
    Return the information for the specified user

    CLI Example::

        salt '*' shadow.user root
    '''
    try:
        data = spwd.getspnam(name)
        ret = {
            'name': data.sp_nam,
            'pwd': data.sp_pwd,
            'lstchg': data.sp_lstchg,
            'min': data.sp_min,
            'max': data.sp_max,
            'warn': data.sp_warn,
            'inact': data.sp_inact,
            'expire': data.sp_expire}
    except KeyError:
        ret = {
            'name': '',
            'pwd': '',
            'lstchg': '',
            'min': '',
            'max': '',
            'warn': '',
            'inact': '',
            'expire': ''}
    return ret

def set_password(name, password):
    '''
    Set the password for a named user, the password must be a properly defined
    hash, the password hash can be generated with this command:
    ``openssl passwd -1 <plaintext password>``

    CLI Example::

        salt '*' root $1$UYCIxa628.9qXjpQCjM4a..
    '''
    s_file = '/etc/shadow'
    ret = {}
    if not os.path.isfile(s_file):
        return ret
    lines = []
    for line in open(s_file, 'rb').readlines():
        comps = line.strip().split(':')
        if not comps[0] == name:
            lines.append(line)
            continue
        comps[1] = password
        line = ':'.join(comps)
        lines.append('{0}\n'.format(line))
    open(s_file, 'w+').writelines(lines)
    print name
    uinfo = info(name)
    if uinfo['pwd'] == password:
        return True
    return False

