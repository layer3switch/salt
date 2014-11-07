# -*- coding: utf-8 -*-
'''
A convenience system to manage jobs, both active and already run
'''

from __future__ import print_function

from __future__ import absolute_import

# Import python libs
import fnmatch
import os

# Import salt libs
import salt.client
import salt.payload
import salt.utils
import salt.output
import salt.minion

from salt._compat import string_types

import logging
log = logging.getLogger(__name__)


def active(outputter=None):
    '''
    Return a report on all actively running jobs from a job id centric
    perspective

    CLI Example:

    .. code-block:: bash

        salt-run jobs.active
    '''
    ret = {}
    client = salt.client.get_local_client(__opts__['conf_file'])
    active_ = client.cmd('*', 'saltutil.running', timeout=__opts__['timeout'])
    for minion, data in active_.items():
        if not isinstance(data, list):
            continue
        for job in data:
            if not job['jid'] in ret:
                ret[job['jid']] = _format_job_instance(job)
                ret[job['jid']].update({'Running': [{minion: job.get('pid', None)}], 'Returned': []})
            else:
                ret[job['jid']]['Running'].append({minion: job['pid']})

    mminion = salt.minion.MasterMinion(__opts__)
    for jid in ret:
        returner = _get_returner((__opts__['ext_job_cache'], __opts__['master_job_cache']))
        data = mminion.returners['{0}.get_jid'.format(returner)](jid)
        for minion in data:
            if minion not in ret[jid]['Returned']:
                ret[jid]['Returned'].append(minion)

    salt.output.display_output(ret, outputter, opts=__opts__)
    return ret


def lookup_jid(jid, ext_source=None, missing=False, outputter=None):
    '''
    Return the printout from a previously executed job

    CLI Example:

    .. code-block:: bash

        salt-run jobs.lookup_jid 20130916125524463507
        salt-run jobs.lookup_jid 20130916125524463507 outputter=highstate
    '''
    ret = {}
    mminion = salt.minion.MasterMinion(__opts__)
    returner = _get_returner((__opts__['ext_job_cache'], ext_source, __opts__['master_job_cache']))

    try:
        data = mminion.returners['{0}.get_jid'.format(returner)](jid)
    except TypeError:
        print('Requested returner could not be loaded. No JIDs could be retrieved.')
        return
    for minion in data:
        if u'return' in data[minion]:
            ret[minion] = data[minion].get(u'return')
        else:
            ret[minion] = data[minion].get('return')
    if missing:
        ckminions = salt.utils.minions.CkMinions(__opts__)
        exp = ckminions.check_minions(data['tgt'], data['tgt_type'])
        for minion_id in exp:
            if minion_id not in data:
                ret[minion_id] = 'Minion did not return'
    salt.output.display_output(ret, outputter, opts=__opts__)
    return ret


def list_job(jid, ext_source=None, outputter=None):
    '''
    List a specific job given by its jid

    CLI Example:

    .. code-block:: bash

        salt-run jobs.list_job 20130916125524463507
    '''
    ret = {'jid': jid}
    mminion = salt.minion.MasterMinion(__opts__)
    returner = _get_returner((__opts__['ext_job_cache'], ext_source, __opts__['master_job_cache']))

    job = mminion.returners['{0}.get_load'.format(returner)](jid)
    ret.update(_format_jid_instance(jid, job))
    ret['Result'] = mminion.returners['{0}.get_jid'.format(returner)](jid)
    salt.output.display_output(ret, outputter, opts=__opts__)
    return ret


def list_jobs(ext_source=None,
              outputter=None,
              search_metadata=None,
              search_function=None,
              search_target=None):
    '''
    List all detectable jobs and associated functions

    CLI Example:

    .. code-block:: bash

        salt-run jobs.list_jobs
    '''
    returner = _get_returner((__opts__['ext_job_cache'], ext_source, __opts__['master_job_cache']))
    mminion = salt.minion.MasterMinion(__opts__)

    try:
        ret = mminion.returners['{0}.get_jids'.format(returner)]()
    except TypeError:
        print('Error: Requested returner could not be loaded. No jobs could be retrieved.')
        return

    if search_metadata:
        mret = {}
        for item in ret:
            if 'Metadata' in ret[item]:
                if isinstance(search_metadata, dict):
                    for key in search_metadata:
                        if key in ret[item]['Metadata']:
                            if ret[item]['Metadata'][key] == search_metadata[key]:
                                mret[item] = ret[item]
                else:
                    log.info('The search_metadata parameter must be specified'
                             ' as a dictionary.  Ignoring.')
    else:
        mret = ret.copy()

    if search_target:
        _mret = {}
        for item in mret:
            if 'Target' in ret[item]:
                if isinstance(search_target, list):
                    for key in search_target:
                        if fnmatch.fnmatch(ret[item]['Target'], key):
                            _mret[item] = ret[item]
                elif isinstance(search_target, string_types):
                    if fnmatch.fnmatch(ret[item]['Target'], search_target):
                        _mret[item] = ret[item]
        mret = _mret.copy()

    if search_function:
        _mret = {}
        for item in mret:
            if 'Function' in ret[item]:
                if isinstance(search_function, list):
                    for key in search_function:
                        if fnmatch.fnmatch(ret[item]['Function'], key):
                            _mret[item] = ret[item]
                elif isinstance(search_function, string_types):
                    if fnmatch.fnmatch(ret[item]['Function'], search_function):
                        _mret[item] = ret[item]
        mret = _mret.copy()

    salt.output.display_output(mret, outputter, opts=__opts__)

    return mret


def print_job(jid, ext_source=None, outputter=None):
    '''
    Print a specific job's detail given by it's jid, including the return data.

    CLI Example:

    .. code-block:: bash

        salt-run jobs.print_job 20130916125524463507
    '''
    ret = {}

    returner = _get_returner((__opts__['ext_job_cache'], ext_source, __opts__['master_job_cache']))
    mminion = salt.minion.MasterMinion(__opts__)

    try:
        job = mminion.returners['{0}.get_load'.format(returner)](jid)
        ret[jid] = _format_jid_instance(jid, job)
    except TypeError:
        ret[jid]['Result'] = ('Requested returner {0} is not available. Jobs cannot be retrieved. '
            'Check master log for details.'.format(returner))
        return ret
    ret[jid]['Result'] = mminion.returners['{0}.get_jid'.format(returner)](jid)
    salt.output.display_output(ret, outputter, opts=__opts__)

    return ret


def _get_returner(returner_types):
    '''
    Helper to iterate over returner_types and pick the first one
    '''
    for returner in returner_types:
        if returner and returner is not None:
            return returner


def _format_job_instance(job):
    '''
    Helper to format a job instance
    '''
    ret = {'Function': job.get('fun', 'unknown-function'),
           'Arguments': list(job.get('arg', [])),
           # unlikely but safeguard from invalid returns
           'Target': job.get('tgt', 'unknown-target'),
           'Target-type': job.get('tgt_type', []),
           'User': job.get('user', 'root')}

    if 'metadata' in job:
        ret['Metadata'] = job.get('metadata', {})
    else:
        if 'kwargs' in job:
            if 'metadata' in job['kwargs']:
                ret['Metadata'] = job['kwargs'].get('metadata', {})

    if 'Minions' in job:
        ret['Minions'] = job['Minions']
    return ret


def _format_jid_instance(jid, job):
    '''
    Helper to format jid instance
    '''
    ret = _format_job_instance(job)
    ret.update({'StartTime': salt.utils.jid_to_time(jid)})
    return ret


def _walk_through(job_dir):
    '''
    Walk through the job dir and return jobs
    '''
    serial = salt.payload.Serial(__opts__)

    for top in os.listdir(job_dir):
        t_path = os.path.join(job_dir, top)

        for final in os.listdir(t_path):
            load_path = os.path.join(t_path, final, '.load.p')
            job = serial.load(salt.utils.fopen(load_path, 'rb'))

            if not os.path.isfile(load_path):
                continue

            job = serial.load(salt.utils.fopen(load_path, 'rb'))
            jid = job['jid']
            yield jid, job, t_path, final
