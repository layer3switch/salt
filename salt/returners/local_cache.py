# -*- coding: utf-8 -*-
'''
Return data to local job cache

'''

# Import python libs
import errno
import logging
import os
import shutil
import datetime

# Import salt libs
import salt.payload
import salt.utils

log = logging.getLogger(__name__)

# load is the published job
LOAD_P = '.load.p'
# the list of minions that the job is targeted to (best effort match on the master side)
MINIONS_P = '.minions.p'
# return is the "return" from the minion data
RETURN_P = 'return.p'
# out is the "out" from the minion data
OUT_P = 'out.p'


def _job_dir():
    '''
    Return root of the jobs cache directory
    '''
    return os.path.join(__opts__['cachedir'], 'jobs')


def _jid_dir(jid, makedirs=False):
    '''
    Return the jid_dir, and optionally create it
    '''
    jid_dir = salt.utils.jid_dir(
                jid,
                os.path.join(__opts__['cachedir'], 'NEWPATHFORTESTING'),
                __opts__['hash_type']
                )

    if makedirs and not os.path.isdir(jid_dir):
        os.makedirs(jid_dir)

    return jid_dir


def _walk_through(job_dir):
    serial = salt.payload.Serial(__opts__)

    for top in os.listdir(job_dir):
        t_path = os.path.join(job_dir, top)

        for final in os.listdir(t_path):
            load_path = os.path.join(t_path, final, LOAD_P)

            if not os.path.isfile(load_path):
                continue

            job = serial.load(salt.utils.fopen(load_path, 'rb'))
            jid = job['jid']
            yield jid, job, t_path, final


def _format_job_instance(job):
    return {'Function': job.get('fun', 'unknown-function'),
            'Arguments': list(job.get('arg', [])),
            # unlikely but safeguard from invalid returns
            'Target': job.get('tgt', 'unknown-target'),
            'Target-type': job.get('tgt_type', []),
            'User': job.get('user', 'root')}


def _format_jid_instance(jid, job):
    ret = _format_job_instance(job)
    ret.update({'StartTime': salt.utils.jid_to_time(jid)})
    return ret


def returner(load):
    '''
    Return data to the local job cache
    '''
    serial = salt.payload.Serial(__opts__)
    jid_dir = _jid_dir(load['jid'], makedirs=True)
    if os.path.exists(os.path.join(jid_dir, 'nocache')):
        return

    # do we need to rewrite the load?
    if load['jid'] == 'req' and bool(load.get('nocache', True)):
        with salt.utils.fopen(os.path.join(jid_dir, LOAD_P), 'w+b') as fp_:
            serial.dump(load, fp_)

    hn_dir = os.path.join(jid_dir, load['id'])

    try:
        os.mkdir(hn_dir)
    except OSError as e:
        if e.errno == errno.EEXIST:
            # Minion has already returned this jid and it should be dropped
            log.error(
                'An extra return was detected from minion {0}, please verify '
                'the minion, this could be a replay attack'.format(
                    load['id']
                )
            )
            return False
        elif e.errno == errno.ENOENT:
            log.error(
                'An inconsistency occurred, a job was received with a job id '
                'that is not present in the local cache: {jid}'.format(**load)
            )
            return False
        raise

    serial.dump(
        load['return'],
        # Use atomic open here to avoid the file being read before it's
        # completely written to. Refs #1935
        salt.utils.atomicfile.atomic_open(
            os.path.join(hn_dir, RETURN_P), 'w+b'
        )
    )

    if 'out' in load:
        serial.dump(
            load['out'],
            # Use atomic open here to avoid the file being read before
            # it's completely written to. Refs #1935
            salt.utils.atomicfile.atomic_open(
                os.path.join(hn_dir, OUT_P), 'w+b'
            )
        )


def save_load(jid, clear_load):
    '''
    Save the load to the specified jid
    '''
    jid_dir = _jid_dir(clear_load['jid'], makedirs=True)

    serial = salt.payload.Serial(__opts__)

    # if you have a tgt, save that for the UI etc
    if 'tgt' in clear_load:
        ckminions = salt.utils.minions.CkMinions(__opts__)
        # Retrieve the minions list
        minions = ckminions.check_minions(
                clear_load['tgt'],
                clear_load.get('tgt_type', 'glob')
                )
        # save the minions to a cache so we can see in the UI
        serial.dump(
            minions,
            salt.utils.fopen(os.path.join(jid_dir, MINIONS_P), 'w+b')
            )

    # Save the invocation information
    serial.dump(
        clear_load,
        salt.utils.fopen(os.path.join(jid_dir, LOAD_P), 'w+b')
        )


def get_load(jid):
    '''
    Return the load data that marks a specified jid
    '''
    jid_dir = _jid_dir(jid)
    if not os.path.exists(jid_dir):
        return {}
    serial = salt.payload.Serial(__opts__)

    ret = serial.load(salt.utils.fopen(os.path.join(jid_dir, LOAD_P), 'rb'))

    minions_path = os.path.join(jid_dir, MINIONS_P)
    if os.path.isfile(minions_path):
        ret['Minions'] = serial.load(salt.utils.fopen(minions_path, 'rb'))

    return ret


def get_jid(jid):
    '''
    Return the information returned when the specified job id was executed
    '''
    jid_dir = _jid_dir(jid)
    serial = salt.payload.Serial(__opts__)

    ret = {}
    # Check to see if the jid is real, if not return the empty dict
    if not os.path.isdir(jid_dir):
        return ret
    for fn_ in os.listdir(jid_dir):
        if fn_.startswith('.'):
            continue
        if fn_ not in ret:
            retp = os.path.join(jid_dir, fn_, RETURN_P)
            outp = os.path.join(jid_dir, fn_, OUT_P)
            if not os.path.isfile(retp):
                continue
            while fn_ not in ret:
                try:
                    ret_data = serial.load(
                        salt.utils.fopen(retp, 'rb'))
                    ret[fn_] = {'return': ret_data}
                    if os.path.isfile(outp):
                        ret[fn_]['out'] = serial.load(
                            salt.utils.fopen(outp, 'rb'))
                except Exception:
                    pass
    return ret


def get_jids():
    '''
    Return a list of all job ids
    '''
    ret = {}
    for jid, job, t_path, final in _walk_through(_job_dir()):
        ret[jid] = _format_jid_instance(jid, job)
    return ret


def clean_old_jobs():
    '''
    Clean out the old jobs from the job cache
    '''
    if __opts__['keep_jobs'] != 0:
        cur = datetime.datetime.now()

        jid_root = _job_dir()
        if not os.path.exists(jid_root):
            return

        for top in os.listdir(jid_root):
            t_path = os.path.join(jid_root, top)
            for final in os.listdir(t_path):
                f_path = os.path.join(t_path, final)
                jid_file = os.path.join(f_path, 'jid')
                if not os.path.isfile(jid_file):
                    # No jid file means corrupted cache entry, scrub it
                    shutil.rmtree(f_path)
                else:
                    with salt.utils.fopen(jid_file, 'r') as fn_:
                        jid = fn_.read()
                    if len(jid) < 18:
                        # Invalid jid, scrub the dir
                        shutil.rmtree(f_path)
                    else:
                        # Parse the jid into a proper datetime object.
                        # We only parse down to the minute, since keep
                        # jobs is measured in hours, so a minute
                        # difference is not important.
                        try:
                            jidtime = datetime.datetime(int(jid[0:4]),
                                                        int(jid[4:6]),
                                                        int(jid[6:8]),
                                                        int(jid[8:10]),
                                                        int(jid[10:12]))
                        except ValueError as e:
                            # Invalid jid, scrub the dir
                            shutil.rmtree(f_path)
                        difference = cur - jidtime
                        hours_difference = difference.seconds / 3600.0
                        if hours_difference > __opts__['keep_jobs']:
                            shutil.rmtree(f_path)
