# -*- coding: utf-8 -*-
'''
This is a shim that handles checking and updating salt thin and
then invoking thin.

This is not intended to be instantiated as a module, rather it is a
helper script used by salt.client.ssh.Single.  It is here, in a
seperate file, for convenience of development.
'''

import hashlib
import tarfile
import shutil
import sys
import os
import json
import stat

THIN_ARCHIVE = 'salt-thin.tgz'

# FIXME - it would be ideal if these could be obtained directly from
#         salt.exitcodes rather than duplicated.
EX_THIN_DEPLOY = 11
EX_THIN_CHECKSUM = 12


class OBJ(object):
    pass

OPTIONS = None
ARGS = None
#%%OPTS


def need_deployment():
    if os.path.exists(OPTIONS.saltdir):
        shutil.rmtree(OPTIONS.saltdir)
    old_umask = os.umask(0077)
    os.makedirs(OPTIONS.saltdir)
    os.umask(old_umask)
    # Verify perms on saltdir
    euid = os.geteuid()
    dstat = os.stat(OPTIONS.saltdir)
    if dstat.st_uid != euid:
        # Attack detected, try again
        need_deployment()
    if dstat.st_mode != 16832:
        # Attack detected
        need_deployment()
    # If SUDOing then also give the super user group write permissions
    sudo_gid = os.environ.get('SUDO_GID')
    if sudo_gid:
        os.chown(OPTIONS.saltdir, -1, int(sudo_gid))
        st = os.stat(OPTIONS.saltdir)
        os.chmod(OPTIONS.saltdir, st.st_mode | stat.S_IWGRP | stat.S_IRGRP | stat.S_IXGRP)

    # Delimeter emitted on stdout *only* to indicate shim message to master.
    sys.stdout.write("{0}\ndeploy\n".format(OPTIONS.delimiter))
    sys.exit(EX_THIN_DEPLOY)


# Adapted from salt.utils.get_hash()
def get_hash(path, form='sha1', chunk_size=4096):
    try:
        hash_type = getattr(hashlib, form)
    except AttributeError:
        raise ValueError('Invalid hash type: {0}'.format(form))
    with open(path, 'rb') as ifile:
        hash_obj = hash_type()
        # read the file in in chunks, not the entire file
        for chunk in iter(lambda: ifile.read(chunk_size), b''):
            hash_obj.update(chunk)
        return hash_obj.hexdigest()


def unpack_thin(thin_path):
    tfile = tarfile.TarFile.gzopen(thin_path)
    tfile.extractall(path=OPTIONS.saltdir)
    tfile.close()
    os.unlink(thin_path)


def get_modules():
    glob = ''
    while True:
        sys.stdout.write('_||ext_mods||_')
        sys.stdout.flush()
        glob += raw_input()
        if glob.endswith('|_E|0|'):
            break
    ext_mods = json.loads(glob[:-6])
    write_modules(ext_mods)


def write_modules(ext_mods):
    modcache = os.path.join(
            OPTIONS.saltdir,
            'running_data',
            'var',
            'cache',
            'salt',
            'extmods')
    for mtype in ext_mods:
        dest_dir = os.path.join(modcache, mtype)
        if not os.path.isdir(dest_dir):
            os.makedirs(dest_dir)
        chunks = ext_mods.get(mtype)
        if not chunks:
            continue
        for name in chunks:
            dest = os.path.join(dest_dir, name)
            with open(dest, 'w+') as fp_:
                fp_.write(chunks[name].decode('base64'))


def main(argv):
    thin_path = os.path.join(OPTIONS.saltdir, THIN_ARCHIVE)
    if os.path.exists(thin_path):
        if OPTIONS.checksum != get_hash(thin_path, OPTIONS.hashfunc):
            os.unlink(thin_path)
            sys.stderr.write('WARNING: checksum mismatch for "{0}"\n'.format(thin_path))
            sys.exit(EX_THIN_CHECKSUM)
        unpack_thin(thin_path)
        # Salt thin now is available to use
    else:
        if not os.path.exists(OPTIONS.saltdir):
            need_deployment()

        if not os.path.isdir(OPTIONS.saltdir):
            sys.stderr.write('ERROR: salt path "{0}" exists but is not a directory\n'.format(OPTIONS.saltdir))
            sys.exit(os.EX_CANTCREAT)

        version_path = os.path.join(OPTIONS.saltdir, 'version')
        if not os.path.exists(version_path) or not os.path.isfile(version_path):
            sys.stderr.write('WARNING: Unable to locate current thin version.\n')
            need_deployment()
        with open(version_path, 'r') as vpo:
            cur_version = vpo.readline().strip()
        if cur_version != OPTIONS.version:
            sys.stderr.write('WARNING: current thin version is not up-to-date.\n')
            need_deployment()
        # Salt thin exists and is up-to-date - fall through and use it

    salt_call_path = os.path.join(OPTIONS.saltdir, 'salt-call')
    if not os.path.isfile(salt_call_path):
        sys.stderr.write('ERROR: thin is missing "{0}"\n'.format(salt_call_path))
        need_deployment()

    with open(os.path.join(OPTIONS.saltdir, 'minion'), 'w') as config:
        config.write(OPTIONS.config + '\n')
    if OPTIONS.get_modules:
        get_modules()
    #Fix parameter passing issue
    if len(ARGS) == 1:
        argv_prepared = ARGS[0].split()
    else:
        argv_prepared = ARGS

    salt_argv = [
        sys.executable,
        salt_call_path,
        '--local',
        '--metadata',
        '--out', 'json',
        '-l', 'quiet',
        '-c', OPTIONS.saltdir,
        '--',
    ] + argv_prepared

    sys.stderr.write('SALT_ARGV: {0}\n'.format(salt_argv))

    # Only emit the delimiter on *both* stdout and stderr when completely successful.
    # Yes, the flush() is necessary.
    sys.stdout.write(OPTIONS.delimiter + '\n')
    sys.stdout.flush()
    sys.stderr.write(OPTIONS.delimiter + '\n')
    sys.stderr.flush()
    os.execv(sys.executable, salt_argv)

if __name__ == '__main__':
    sys.exit(main(sys.argv))
