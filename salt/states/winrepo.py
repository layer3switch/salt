# -*- coding: utf-8 -*-
'''
Manage Windows Package Repository

.. note::

    This state only loads on minions that have the ``roles: salt-master`` grain
    set.
'''
from __future__ import absolute_import

# Python Libs
import os
import stat
import itertools

# Salt Modules
import salt.runner
import salt.utils
import salt.config


def __virtual__():
    '''
    Load this state if this is the salt-master
    '''
    try:
        return ('winrepo'
                if 'salt-master' in __grains__.get('roles', [])
                else False)
    except TypeError:
        return False


def genrepo(name, force=False, allow_empty=False):
    '''
    Refresh the winrepo.p file of the repository (salt-run winrepo.genrepo)

    If ``force`` is ``True`` no checks will be made and the repository will be
    generated if ``allow_empty`` is ``True`` then the state will not return an
    error if there are 0 packages,

    .. note::

        This state only loads on minions that have the ``roles: salt-master``
        grain set.

    Example:

    .. code-block:: yaml

        winrepo:
          winrepo.genrepo
    '''

    ret = {'name': name,
           'result': True,
           'changes': {},
           'comment': ''}

    if 'win_repo' in __opts__:
        salt.utils.warn_until(
            'Nitrogen',
            'The \'win_repo\' config option is deprecated, please use '
            '\'winrepo_dir\' instead.'
        )
        winrepo_dir = __opts__['win_repo']
    else:
        winrepo_dir = __opts__['winrepo_dir']

    if 'win_repo_mastercachefile' in __opts__:
        salt.utils.warn_until(
            'Nitrogen',
            'The \'win_repo_mastercachefile\' config option is deprecated, '
            'please use \'winrepo_cachefile\' instead.'
        )
        winrepo_cachefile = __opts__['win_repo_mastercachefile']
    else:
        winrepo_cachefile = __opts__['winrepo_cachefile']

    # We're actually looking for the full path to the cachefile here, so
    # prepend the winrepo_dir
    winrepo_cachefile = os.path.join(winrepo_dir, winrepo_cachefile)

    master_config = salt.config.master_config(os.path.join(salt.syspaths.CONFIG_DIR, 'master'))

    # Check if the winrepo directory exists
    # if not search for a file with a newer mtime than the winrepo_cachefile file
    execute = False
    if not force:
        if not os.path.exists(winrepo_dir):
            ret['result'] = False
            ret['comment'] = '{0} is missing'.format(winrepo_dir)
            return ret
        elif not os.path.exists(winrepo_cachefile):
            execute = True
            ret['comment'] = '{0} is missing'.format(winrepo_cachefile)
        else:
            winrepo_cachefile_mtime = os.stat(winrepo_cachefile)[stat.ST_MTIME]
            for root, dirs, files in os.walk(winrepo_dir):
                for name in itertools.chain(files, dirs):
                    full_path = os.path.join(root, name)
                    if os.stat(full_path)[stat.ST_MTIME] > winrepo_cachefile_mtime:
                        ret['comment'] = 'mtime({0}) < mtime({1})'.format(winrepo_cachefile, full_path)
                        execute = True
                        break

    if __opts__['test']:
        ret['result'] = None
        return ret

    if not execute and not force:
        return ret

    runner = salt.runner.RunnerClient(master_config)
    runner_ret = runner.cmd('winrepo.genrepo', [])
    ret['changes'] = {'winrepo': runner_ret}
    if isinstance(runner_ret, dict) and runner_ret == {} and not allow_empty:
        os.remove(winrepo_cachefile)
        ret['result'] = False
        ret['comment'] = 'winrepo.genrepo returned empty'
    return ret
