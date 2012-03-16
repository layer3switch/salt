'''
Install Python packages with pip to either the system or a virtualenv
'''

import os

def _get_pip_bin(bin_env):
    '''
    Return the pip command to call, either from a virtualenv, an argument
    passed in, or from the global modules options
    '''
    if not bin_env:
        pip_bin = 'pip'
    else:
        # try to get pip bin from env
        if os.path.exists(os.path.join(bin_env, 'bin', 'pip')):
            pip_bin = os.path.join(bin_env, 'bin', 'pip')
        else:
            pip_bin = bin_env
    return pip_bin


def install(packages=None,
            requirements=None,
            bin_env=None,
            log=None,
            proxy=None,
            timeout=None,
            editable=None,
            find_links=None,
            index_url=None,
            extra_index_url=None,
            no_index=False,
            mirrors=None,
            build=None,
            target=None,
            download=None,
            download_cache=None,
            source=None,
            upgrade=False,
            force_reinstall=False,
            ignore_installed=False,
            no_deps=False,
            no_install=False,
            no_download=False,
            install_options=None):
    '''
    Install packages with pip

    Install packages individually or from a pip requirements file. Install
    packages globally or to a virtualenv.

    packages
        comma separated list of packages to install
    requirements
        path to requirements
    bin_env
        path to pip bin or path to virtualenv. If doing a system install,
        and want to use a specific pip bin (pip-2.7, pip-2.6, etc..) just
        specify the pip bin you want.
        If installing into a virtualenv, just use the path to the virtualenv
        (/home/code/path/to/virtualenv/)
    log
        Log file where a complete (maximum verbosity) record will be kept
    proxy
        Specify a proxy in the form
        user:passwd@proxy.server:port. Note that the
        user:password@ is optional and required only if you
        are behind an authenticated proxy.  If you provide
        user@proxy.server:port then you will be prompted for a
        password.
    timeout
        Set the socket timeout (default 15 seconds)
    editable
        install something editable(ie git+https://github.com/worldcompany/djangoembed.git#egg=djangoembed)
    find_links
        URL to look for packages at
    index_url
        Base URL of Python Package Index
    extra_index_url
        Extra URLs of package indexes to use in addition to ``index_url``
    no_index
        Ignore package index
    mirrors
        Specific mirror URLs to query (automatically adds --use-mirrors)
    build
        Unpack packages into ``build`` dir
    target
        Install packages into ``target`` dir
    download
        Download packages into ``download`` instead of installing them
    download_cache
        Cache downloaded packages in ``download_cache`` dir
    source
        Check out ``editable`` packages into ``source`` dir
    upgrade
        Upgrade all packages to the newest available version
    force_reinstall
        When upgrading, reinstall all packages even if they are already up-to-date.
    ignore_installed
        Ignore the installed packages (reinstalling instead)
    no_deps
        Ignore package dependencies
    no_install
        Download and unpack all packages, but don't actually install them
    no_download
        Don't download any packages, just install the ones
        already downloaded (completes an install run with
        --no-install)
    install_options
        Extra arguments to be supplied to the setup.py install
        command (use like --install-option="--install-
        scripts=/usr/local/bin").  Use multiple --install-
        option options to pass multiple options to setup.py
        install.  If you are using an option with a directory
        path, be sure to use absolute path.


    CLI Example::

        salt '*' pip.install <package name>,<package2 name>

        salt '*' pip.install requirements=/path/to/requirements.txt

        salt '*' pip.install <package name> bin_env=/path/to/virtualenv

        salt '*' pip.install <package name> bin_env=/path/to/pip_bin

    Comlicated CLI example::

        salt '*' pip.install markdown,django editable=git+https://github.com/worldcompany/djangoembed.git#egg=djangoembed upgrade=True no_deps=True

    '''

    cmd = '{0} install'.format(_get_pip_bin(bin_env))

    if packages:
        pkg = packages.replace(",", " ")
        cmd = '{cmd} {pkg} '.format(
            cmd=cmd, pkg=pkg)

    if requirements:
        cmd = '{cmd} --requirements{requirements} '.format(
            cmd=cmd, requirements=requirements)

    if log:
        try:
            # TODO make this check if writeable
            os.path.exists(log)
        except IOError:
            raise IOError("'%s' is not writeable" % log)
        cmd = '{cmd} --{log} '.format(
            cmd=cmd, log=log)

    if proxy:
        cmd = '{cmd} --proxy={proxy} '.format(
            cmd=cmd, proxy=proxy)

    if timeout:
        try:
            int(timeout)
        except ValueError:
            raise ValueError("'%s' is not a valid integer base 10.")
        cmd = '{cmd} --timeout={timeout} '.format(
            cmd=cmd, timeout=timeout)

    if editable:
        if editable.find('egg') == -1:
            raise Exception('You must specify an egg for this editable')
        cmd = '{cmd} --editable={editable} '.format(
            cmd=cmd, editable=editable)

    if find_links:
        if not find_links.startswith("http://"):
            raise Exception("'%s' must be a valid url" % find_links)
        cmd = '{cmd} --find_links={find_links}'.format(
            cmd=cmd, find_links=find_links)

    if index_url:
        if not index_url.startswith("http://"):
            raise Exception("'%s' must be a valid url" % index_url)
        cmd = '{cmd} --index_url={index_url} '.format(
            cmd=cmd, index_url=index_url)

    if extra_index_url:
        if not extra_index_url.startswith("http://"):
            raise Exception("'%s' must be a valid url" % extra_index_url)
        cmd = '{cmd} --extra_index_url={extra_index_url} '.format(
            cmd=cmd, extra_index_url=extra_index_url)

    if no_index:
        cmd = '{cmd} --no-index '.format(cmd=cmd)

    if mirrors:
        if not mirrors.startswith("http://"):
            raise Exception("'%s' must be a valid url" % mirrors)
        cmd = '{cmd} --use-mirrors --mirrors={mirrors} '.format(
            cmd=cmd, mirrors=mirrors)

    if build:
        cmd = '{cmd} --build={build} '.format(
            cmd=cmd, build=build)

    if target:
        cmd = '{cmd} --target={target} '.format(
            cmd=cmd, target=target)

    if download:
        cmd = '{cmd} --download={download} '.format(
            cmd=cmd, download=download)

    if download_cache:
        cmd = '{cmd} --download_cache={download_cache} '.format(
            cmd=cmd, download_cache=download_cache)

    if source:
        cmd = '{cmd} --source={source} '.format(
            cmd=cmd, source=source)

    if upgrade:
        cmd = '{cmd} --upgrade '.format(cmd=cmd)

    if force_reinstall:
        cmd = '{cmd} --force-reinstall '.format(cmd=cmd)

    if ignore_installed:
        cmd = '{cmd} --ignore-installed '.format(cmd=cmd)

    if no_deps:
        cmd = '{cmd} --no-deps '.format(cmd=cmd)

    if no_install:
        cmd = '{cmd} --no-install '.format(cmd=cmd)

    if no_download:
        cmd = '{cmd} --no-download '.format(cmd=cmd)

    if install_options:
        cmd = '{cmd} --install-options={install_options} '.format(
            cmd=cmd, install_options=install_options)

    return __salt__['cmd.run'](cmd)


def uninstall(packages=None,
              requirements=None,
              bin_env=None,
              log=None,
              proxy=None,
              timeout=None):
    '''
    Uninstall packages with pip

    Uninstall packages individually or from a pip requirements file. Uninstall
    packages globally or from a virtualenv.

    packages
        comma separated list of packages to install
    requirements
        path to requirements
    bin_env
        path to pip bin or path to virtualenv. If doing an uninstall from
        the system python and want to use a specific pip bin (pip-2.7,
        pip-2.6, etc..) just specify the pip bin you want.
        If uninstalling from a virtualenv, just use the path to the virtualenv
        (/home/code/path/to/virtualenv/)
    log
        Log file where a complete (maximum verbosity) record will be kept
    proxy
        Specify a proxy in the form
        user:passwd@proxy.server:port. Note that the
        user:password@ is optional and required only if you
        are behind an authenticated proxy.  If you provide
        user@proxy.server:port then you will be prompted for a
        password.
    timeout
        Set the socket timeout (default 15 seconds)


    CLI Example::

        salt '*' pip.uninstall <package name>,<package2 name>

        salt '*' pip.uninstall requirements=/path/to/requirements.txt

        salt '*' pip.uninstall <package name> bin_env=/path/to/virtualenv

        salt '*' pip.uninstall <package name> bin_env=/path/to/pip_bin

    '''
    cmd = '{0} uninstall -y '.format(_get_pip_bin(bin_env))

    if requirements:
        cmd = '{cmd} --requirements{requirements} '.format(
            cmd=cmd, requirements=requirements)

    if log:
        try:
            # TODO make this check if writeable
            os.path.exists(log)
        except IOError:
            raise IOError("'%s' is not writeable" % log)
        cmd = '{cmd} --{log} '.format(
            cmd=cmd, log=log)

    if proxy:
        cmd = '{cmd} --proxy={proxy} '.format(
            cmd=cmd, proxy=proxy)

    if timeout:
        try:
            int(timeout)
        except ValueError:
            raise ValueError("'%s' is not a valid integer base 10.")
        cmd = '{cmd} --timeout={timeout} '.format(
            cmd=cmd, timeout=timeout)

    return __salt__['cmd.run'](cmd).split('\n')


def freeze(bin_env=None):
    '''
    Return a list of installed packages either globally or in the specified
    virtualenv

    env : None
        The path to a virtualenv that pip should install to. This option takes
        precendence over the ``pip_bin`` argument.
    pip_bin : 'pip'
        The name (and optionally path) of the pip command to call. This option
        will be ignored if the ``env`` argument is given since it will default
        to the pip that is installed in the virtualenv. This option can also be
        set in the minion config file as ``pip.pip_bin``.
    '''

    cmd = '{0} freeze'.format(_get_pip_bin(bin_env))

    return __salt__['cmd.run'](cmd).split('\n')
