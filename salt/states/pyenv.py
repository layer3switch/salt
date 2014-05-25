# -*- coding: utf-8 -*-
'''
Managing python installations with pyenv
======================================

This module is used to install and manage python installations with pyenv.
Different versions of python can be installed, and uninstalled. pyenv will
be installed automatically the first time it is needed and can be updated
later. This module will *not* automatically install packages which pyenv
will need to compile the versions of python.

If pyenv is run as the root user then it will be installed to /usr/local/pyenv,
otherwise it will be installed to the users ~/.pyenv directory. To make
pyenv available in the shell you may need to add the pyenv/shims and pyenv/bin
directories to the users PATH. If you are installing as root and want other
users to be able to access pyenv then you will need to add pyenv_ROOT to
their environment.

This is how a state configuration could look like:

.. code-block:: yaml

    pyenv-deps:
      pkg.installed:
        - pkgs:
          - make
          - build-essential
          - libssl-dev
          - zlib1g-dev
          - libbz2-dev
          - libreadline-dev
          - libsqlite3-dev
          - wget 
          - curl
          - llvm
    python-2.6:
      pyenv.absent:
        - require:
          - pkg: pyenv-deps

    python-2.7.6:
      pyenv.installed:
        - default: True
        - require:
          - pkg: pyenv-deps
'''

# Import python libs
import re

# Import salt libs
import salt.utils


def _check_pyenv(ret, user=None):
    '''
    Check to see if pyenv is installed.
    '''
    if not __salt__['pyenv.is_installed'](user):
        ret['result'] = False
        ret['comment'] = 'pyenv is not installed.'
    return ret


def _python_installed(ret, python, user=None):
    '''
    Check to see if given python is installed.
    '''
    default = __salt__['pyenv.default'](runas=user)
    for version in __salt__['pyenv.versions'](user):
        if version == python:
            ret['result'] = True
            ret['comment'] = 'Requested python exists.'
            ret['default'] = default == python
            break

    return ret


def _check_and_install_python(ret, python, default=False, user=None):
    '''
    Verify that python is installed, install if unavailable
    '''
    ret = _python_installed(ret, python, user=user)
    if not ret['result']:
        if __salt__['pyenv.install_python'](python, runas=user):
            ret['result'] = True
            ret['changes'][python] = 'Installed'
            ret['comment'] = 'Successfully installed python'
            ret['default'] = default
        else:
            ret['result'] = False
            ret['comment'] = 'Could not install python.'
            return ret

    if default:
        __salt__['pyenv.default'](python, runas=user)

    return ret


def installed(name, default=False, runas=None, user=None):
    '''
    Verify that the specified python is installed with pyenv. pyenv is
    installed if necessary.

    name
        The version of python to install

    default : False
        Whether to make this python the default.

    runas: None
        The user to run pyenv as.

        .. deprecated:: 0.17.0

    user: None
        The user to run pyenv as.

        .. versionadded:: 0.17.0

    .. versionadded:: 0.16.0
    '''
    ret = {'name': name, 'result': None, 'comment': '', 'changes': {}}

    if user is not None and runas is not None:
        # user wins over runas but let warn about the deprecation.
        ret.setdefault('warnings', []).append(
            'Passed both the \'runas\' and \'user\' arguments. Please don\'t. '
            '\'runas\' is being ignored in favor of \'user\'.'
        )
        runas = None
    elif runas is not None:
        # Support old runas usage
        user = runas
        runas = None

    if name.startswith('python-'):
        name = re.sub(r'^python-', '', name)

    if __opts__['test']:
        ret['comment'] = 'python {0} is set to be installed'.format(name)
        return ret

    ret = _check_pyenv(ret, user)
    if ret['result'] is False:
        if not __salt__['pyenv.install'](user):
            ret['comment'] = 'pyenv failed to install'
            return ret
        else:
            return _check_and_install_python(ret, name, default, user=user)
    else:
        return _check_and_install_python(ret, name, default, user=user)


def _check_and_uninstall_python(ret, python, user=None):
    '''
    Verify that python is uninstalled
    '''
    ret = _python_installed(ret, python, user=user)
    if ret['result']:
        if ret['default']:
            __salt__['pyenv.default']('system', runas=user)

        if __salt__['pyenv.uninstall_python'](python, runas=user):
            ret['result'] = True
            ret['changes'][python] = 'Uninstalled'
            ret['comment'] = 'Successfully removed python'
            return ret
        else:
            ret['result'] = False
            ret['comment'] = 'Failed to uninstall python'
            return ret
    else:
        ret['result'] = True
        ret['comment'] = 'python {0} is already absent'.format(python)

    return ret


def absent(name, runas=None, user=None):
    '''
    Verify that the specified python is not installed with pyenv. pyenv
    is installed if necessary.

    name
        The version of python to uninstall

    runas: None
        The user to run pyenv as.

        .. deprecated:: 0.17.0

    user: None
        The user to run pyenv as.

        .. versionadded:: 0.17.0

    .. versionadded:: 0.16.0
    '''
    ret = {'name': name, 'result': None, 'comment': '', 'changes': {}}

    salt.utils.warn_until(
        'Hydrogen',
        'Please remove \'runas\' support at this stage. \'user\' support was '
        'added in 0.17.0',
        _dont_call_warnings=True
    )
    if runas:
        # Warn users about the deprecation
        ret.setdefault('warnings', []).append(
            'The \'runas\' argument is being deprecated in favor of \'user\', '
            'please update your state files.'
        )
    if user is not None and runas is not None:
        # user wins over runas but let warn about the deprecation.
        ret.setdefault('warnings', []).append(
            'Passed both the \'runas\' and \'user\' arguments. Please don\'t. '
            '\'runas\' is being ignored in favor of \'user\'.'
        )
        runas = None
    elif runas is not None:
        # Support old runas usage
        user = runas
        runas = None

    if name.startswith('python-'):
        name = re.sub(r'^python-', '', name)

    if __opts__['test']:
        ret['comment'] = 'python {0} is set to be uninstalled'.format(name)
        return ret

    ret = _check_pyenv(ret, user)
    if ret['result'] is False:
        ret['result'] = True
        ret['comment'] = 'pyenv not installed, {0} not either'.format(name)
        return ret
    else:
        return _check_and_uninstall_python(ret, name, user=user)
