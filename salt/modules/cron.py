'''
Work with cron
'''
import tempfile

TAG = '# Lines below here are managed by Salt, do not edit\n'

def _render_tab(lst):
    '''
    Takes a tab list structure and renders it to a list for applying it to
    a file
    '''
    ret = []
    for pre in lst['pre']:
        ret.append(pre)
    if len(ret):
        if not ret[-1] == TAG:
            ret.append(TAG)
    for cron in lst['crons']:
        ret.append(
            '{0} {1} {2} {3} {4} {5}\n'.format(
                cron['min'],
                cron['hour'],
                cron['daymonth'],
                cron['month'],
                cron['dayweek'],
                cron['cmd']
                )
            )
    for spec in lst['special']:
        ret.append(
            '{0} {1}\n'.format(
                spec['spec'],
                spec['cmd']
                )
            )
    return ret

def _write_cron(user, lines):
    '''
    Takes a list of lines to be commited to a user's crontab and writes it
    '''
    tmpd, path = tempfile.mkstemp()
    open(path, 'w+').writelines(lines)
    cmd = 'crontab -u {0} {1}'.format(user, path)
    return __salt__['cmd.run_all'](cmd)

def raw_cron(user):
    '''
    Return the contents of the user's crontab
    '''
    cmd = 'crontab -l -u {0}'.format(user)
    return __salt__['cmd.run_stdout'](cmd)

def list_tab(user):
    '''
    Return the contents of the specified user's crontab

    CLI Example:
    salt '*' cron.list_tab root
    '''
    data = raw_cron(user)
    ret = {'pre': [],
           'crons': [],
           'special': []}
    flag = False
    for line in data.split('\n'):
        if line == '# Lines below here are managed by Salt, do not edit\n':
            flag = True
            continue
        if flag:
            if line.startswith('@'):
                # Its a "special" line
                dat = {}
                comps = line.split()
                if len(comps) < 2:
                    # Invalid line
                    continue
                dat['spec'] = comps[0]
                dat['cmd'] = ' '.join(comps[1:])
                ret['special'].append(dat)
            if len(line.split()) > 5:
                # Appears to be a standard cron line
                comps = line.split()
                dat = {}
                dat['min'] = comps[0]
                dat['hour'] = comps[1]
                dat['daymonth'] = comps[2]
                dat['month'] = comps[3]
                dat['dayweek'] = comps[4]
                dat['cmd'] = ' '.join(comps[5:])
                ret['crons'].append(dat)
        else:
            ret['pre'].append(line)
    return ret

def set_special(user, special, cmd):
    '''
    Set up a special command in the crontab.

    CLI Example:
    salt '*' cron.set_special @hourly 'echo foobar'
    '''
    lst = list_tab(user)
    for spec in lst['special']:
        if special == cron['special'] and \
            cmd == cron['cmd']:
            return 'present'
    spec = {'special': special,
            'cmd': cmd}
    lst['special'].append(spec)
    comdat = _write_cron(user, _render_tab(lst))
    if not comdat['retcode']:
        # Failed to commit, return the error
        return comdat['stderr']
    return 'new'

def set_job(user, minute, hour, dom, month, dow, cmd):
    '''
    Sets a cron job up for a specified user.
    '''
    lst = list_tab(user)
    for cron in lst['crons']:
        if minute == cron['min'] and \
            hour == cron['hour'] and \
            dom == cron['daymonth'] and \
            month == cron['month'] and \
            dow == cron['dayweek'] and \
            cmd == cron['cmd']:
            return 'present'
    cron = {'min': minute,
            'hour': hour,
            'daymonth': dom,
            'month': month,
            'dayweek': dow,
            'cmd': cmd}
    lst['crons'].append(cron)
    comdat = _write_cron(user, _render_tab(lst))
    if not comdat['retcode']:
        # Failed to commit, return the error
        return comdat['stderr']
    return 'new'
