# -*- coding: utf-8 -*-
'''
Management of Jenkins
=====================

.. versionadded:: 2016.3.0

'''

# Import Python libs
from __future__ import absolute_import
import difflib
import logging

# Import Salt libs
import salt.ext.six as six
import salt.utils
from salt.exceptions import CommandExecutionError

log = logging.getLogger(__name__)


def _fail(ret, msg):
    ret['comment'] = msg
    ret['result'] = False
    return ret


def present(name,
            config=None,
            **kwargs):
    '''
    Ensure the job is present in the Jenkins configured jobs

    name
        The unique name for the Jenkins job

    config
        The Salt URL for the file to use for configuring the job
    '''

    ret = {'name': name,
           'result': True,
           'changes': {},
           'comment': ['Job {0} is up to date.'.format(name)]}

    if __salt__['jenkins.job_exists'](name):
        _current_job_config = __salt__['jenkins.get_job_config'](name)
        buf = six.moves.StringIO(_current_job_config)
        _current_job_config = buf.readlines()

        cached_source_path = __salt__['cp.cache_file'](config, __env__)
        with salt.utils.fopen(cached_source_path) as _fp:
            new_config_xml = _fp.readlines()

        if _current_job_config != new_config_xml:
            diff = difflib.unified_diff(_current_job_config, new_config_xml, lineterm='')
            try:
                __salt__['jenkins.update_job'](name, config, __env__)
            except CommandExecutionError as exc:
                return _fail(ret, exc.strerror)
            else:
                ret['changes'] = ''.join(diff)
                ret['comment'].append('Job \'{0}\' updated.'.format(name))

    else:
        cached_source_path = __salt__['cp.cache_file'](config, __env__)
        with salt.utils.fopen(cached_source_path) as _fp:
            new_config_xml = _fp.read()

        try:
            __salt__['jenkins.create_job'](name, config, __env__)
        except CommandExecutionError as exc:
            return _fail(ret, exc.strerror)

        buf = six.moves.StringIO(new_config_xml)
        _current_job_config = buf.readlines()

        diff = difflib.unified_diff('', buf, lineterm='')
        ret['changes'] = ''.join(diff)
        ret['comment'].append('Job \'{0}\' added.'.format(name))

    ret['comment'] = '\n'.join(ret['comment'])
    return ret


def absent(name,
           **kwargs):
    '''
    Ensure the job is absent from the Jenkins configured jobs

    name
        The name of the Jenkins job to remove
    '''
    ret = {'name': name,
           'result': True,
           'changes': {},
           'comment': []}

    if __salt__['jenkins.job_exists'](name):
        try:
            __salt__['jenkins.delete_job'](name)
        except CommandExecutionError as exc:
            return _fail(ret, exc.strerror)
        else:
            ret['comment'] = 'Job \'{0}\' deleted.'.format(name)
    else:
        ret['comment'] = 'Job \'{0}\' already absent.'.format(name)
    return ret
