'''
A module to wrap pacman calls, since Arch is the best
(https://wiki.archlinux.org/index.php/Arch_is_the_best)
'''

import subprocess

def __virtual__():
    '''
    Set the virtual pkg module if the os is Arch
    '''
    return 'pkg' if __grains__['os'] == 'Arch' else False

def _list_removed(old, new):
    '''
    List the packages which have been removed between the two package objects
    '''
    pkgs = []
    for pkg in old:
        if not new.has_key(pkg):
            pkgs.append(pkg)
    return pkgs

def available_version(name):
    '''
    The available version of the package in the repository

    CLI Example:
    salt '*' pkg.available_version <package name>
    '''
    return subprocess.Popen('pacman -Sp --print-format %v ' + name,
        shell=True,
        stdout=subprocess.PIPE).communicate()[0].strip()

def version(name):
    '''
    Returns a bool if the package is installed or not

    CLI Example:
    salt '*' pkg.version <package name>
    '''
    pkgs = list_pkgs()
    if pkgs.has_key(name):
        return pkgs[name]
    else:
        return ''

def list_pkgs():
    '''
    List the packages currently installed in a dict:
    {'<package_name>': '<version>'}

    CLI Example:
    salt '*' pkg.list_pkgs
    '''
    cmd = 'pacman -Q'
    ret = {}
    out = subprocess.Popen(cmd,
            shell=True,
            stdout=subprocess.PIPE).communicate()[0].split('\n')
    for line in out:
        if not line.count(' '):
            continue
        comps = line.split()
        ret[comps[0]] = comps[1]
    return ret

def refresh_db():
    '''
    Just run a pacman -Sy, return a dict:
    {'<database name>': Bool}

    CLI Example:
    salt '*' pkg.refresh_db
    '''
    cmd = 'pacman -Sy'
    ret = {}
    out = subprocess.Popen(cmd,
            shell=True,
            stdout=subprocess.PIPE).communicate()[0].split('\n')
    for line in out:
        if line.strip().startswith('::'):
            continue
        if not line:
            continue
        key = line.strip().split()[0]
        if line.count('is up to date'):
            ret[key] = False
        elif line.count('downloading'):
            ret[key] = True
    return ret

def install(name, refresh=False):
    '''
    Install the passed package, add refresh=True to install with an -Sy

    Return a dict containing the new package names and versions:
    {'<package>': {'old': '<old-version>',
                   'new': '<new-version>']}

    CLI Example:
    salt '*' pkg.install <package name>
    '''
    old = list_pkgs()
    cmd = 'pacman -S --noprogressbar --noconfirm ' + name
    if refresh:
        cmd = 'pacman -Syu --noprogressbar --noconfirm ' + name
    subprocess.call(cmd, shell=True)
    new = list_pkgs()
    pkgs = {}
    for npkg in new:
        if old.has_key(npkg):
            if old[npkg] == new[npkg]:
                # no change in the package
                continue
            else:
                # the package was here before and the version has changed
                pkgs[npkg] = {'old': old[npkg],
                              'new': new[npkg]}
        else:
            # the package is freshly installed
            pkgs[npkg] = {'old': '',
                          'new': new[npkg]}
    return pkgs

def upgrade():
    '''
    Run a full system upgrade, a pacman -Syu

    Return a dict containing the new package names and versions:
    {'<package>': {'old': '<old-version>',
                   'new': '<new-version>']}

    CLI Example:
    salt '*' pkg.upgrade
    '''
    old = list_pkgs()
    cmd = 'pacman -Syu --noprogressbar --noconfirm '
    subprocess.call(cmd, shell=True)
    new = list_pkgs()
    pkgs = {}
    for npkg in new:
        if old.has_key(npkg):
            if old[npkg] == new[npkg]:
                # no change in the package
                continue
            else:
                # the package was here before and the version has changed
                pkgs[npkg] = {'old': old[npkg],
                              'new': new[npkg]}
        else:
            # the package is freshly installed
            pkgs[npkg] = {'old': '',
                          'new': new[npkg]}
    return pkgs
    
def remove(name):
    '''
    Remove a single package with pacman -R

    Return a list containing the removed packages:
    
    CLI Example:
    salt '*' pkg.remove <package name>
    '''
    old = list_pkgs()
    cmd = 'pacman -R --noprogressbar --noconfirm ' + name
    subprocess.call(cmd, shell=True)
    new = list_pkgs()
    return _list_removed(old, new)

def purge(name):
    '''
    Recursively remove a package and all dependencies which were installed
    with it, this will call a pacman -Rsc

    Return a list containing the removed packages:
    
    CLI Example:
    salt '*' pkg.purge <package name>

    '''
    old = list_pkgs()
    cmd = 'pacman -R --noprogressbar --noconfirm ' + name
    subprocess.call(cmd, shell=True)
    new = list_pkgs()
    return _list_removed(old, new)
