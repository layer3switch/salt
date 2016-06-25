# -*- coding: utf-8 -*-
#
# Copyright 2015 SUSE LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

# Import Python Libs
from __future__ import absolute_import, print_function
import os
import sys
from subprocess import Popen, PIPE, STDOUT
import logging

# Import Salt Libs
from salt.modules.inspectlib.exceptions import (InspectorSnapshotException)
from salt.modules.inspectlib import EnvLoader
from salt.modules.inspectlib import kiwiproc
from salt.modules.inspectlib.fsdb import CsvDBEntity

import salt.utils
from salt.utils import fsutils
from salt.utils import reinit_crypto
from salt.exceptions import CommandExecutionError

try:
    import kiwi
except ImportError:
    kiwi = None

log = logging.getLogger(__name__)


class Package(CsvDBEntity):
    _TABLE = 'inspector_pkg'

    def __init__(self):
        self.id = 0
        self.name = ''


class PackageCfgFile(CsvDBEntity):
    _TABLE = 'inspector_pkg_cfg_files'

    def __init__(self):
        self.id = 0
        self.pkgid = 0
        self.path = ''


class PayloadFile(CsvDBEntity):
    _TABLE = 'inspector_payload'

    def __init__(self):
        self.id = 0
        self.path = ''
        self.p_type = ''
        self.mode = 0
        self.uid = 0
        self.gid = 0
        self.p_size = 0
        self.atime = 0.
        self.mtime = 0.
        self.ctime = 0.


class Inspector(EnvLoader):
    DEFAULT_MINION_CONFIG_PATH = '/etc/salt/minion'

    MODE = ['configuration', 'payload', 'all']
    IGNORE_MOUNTS = ["proc", "sysfs", "devtmpfs", "tmpfs", "fuse.gvfs-fuse-daemon"]
    IGNORE_FS_TYPES = ["autofs", "cifs", "nfs", "nfs4"]
    IGNORE_PATHS = ["/tmp", "/var/tmp", "/lost+found", "/var/run",
                    "/var/lib/rpm", "/.snapshots", "/.zfs", "/etc/ssh",
                    "/root", "/home"]

    def __init__(self, cachedir=None, piddir=None, pidfilename=None):
        EnvLoader.__init__(self, cachedir=cachedir, piddir=piddir, pidfilename=pidfilename)

        # TODO: This is nasty. Need to do something with this better. ASAP!
        try:
            self.db.open()
        except Exception as ex:
            log.error('Unable to [re]open db. Already opened?')
        self.db._csv_db.open()

    def _syscall(self, command, input=None, env=None, *params):
        '''
        Call an external system command.
        '''
        return Popen([command] + list(params), stdout=PIPE, stdin=PIPE, stderr=STDOUT,
                     env=env or os.environ).communicate(input=input)

    def _get_cfg_pkgs(self):
        '''
        Package scanner switcher between the platforms.

        :return:
        '''
        if self.grains_core.os_data().get('os_family') == 'Debian':
            return self.__get_cfg_pkgs_dpkg()
        elif self.grains_core.os_data().get('os_family') in ['SUSE', 'redhat']:
            return self.__get_cfg_pkgs_rpm()
        else:
            return dict()

    def __get_cfg_pkgs_dpkg(self):
        '''
        Get packages with configuration files on Dpkg systems.
        :return:
        '''
        # Get list of all available packages
        data = dict()

        for pkg_name in salt.utils.to_str(self._syscall('dpkg-query', None, None,
                                                        '-Wf', "${binary:Package}\\n")[0]).split(os.linesep):
            pkg_name = pkg_name.strip()
            if not pkg_name:
                continue
            data[pkg_name] = list()
            for pkg_cfg_item in salt.utils.to_str(self._syscall('dpkg-query', None, None, '-Wf', "${Conffiles}\\n",
                                                                pkg_name)[0]).split(os.linesep):
                pkg_cfg_item = pkg_cfg_item.strip()
                if not pkg_cfg_item:
                    continue
                pkg_cfg_file, pkg_cfg_sum = pkg_cfg_item.strip().split(" ", 1)
                data[pkg_name].append(pkg_cfg_file)

            # Dpkg meta data is unreliable. Check every package
            # and remove which actually does not have config files.
            if not data[pkg_name]:
                data.pop(pkg_name)

        return data

    def __get_cfg_pkgs_rpm(self):
        '''
        Get packages with configuration files on RPM systems.
        '''
        out, err = self._syscall('rpm', None, None, '-qa', '--configfiles',
                                 '--queryformat', '%{name}-%{version}-%{release}\\n')
        data = dict()
        pkg_name = None
        pkg_configs = []

        out = salt.utils.to_str(out)
        for line in out.split(os.linesep):
            line = line.strip()
            if not line:
                continue
            if not line.startswith("/"):
                if pkg_name and pkg_configs:
                    data[pkg_name] = pkg_configs
                pkg_name = line
                pkg_configs = []
            else:
                pkg_configs.append(line)

        if pkg_name and pkg_configs:
            data[pkg_name] = pkg_configs

        return data

    def _get_changed_cfg_pkgs(self, data):
        '''
        Filter out unchanged packages on the Debian or RPM systems.

        :param data: Structure {package-name -> [ file .. file1 ]}
        :return: Same structure as data, except only files that were changed.
        '''
        f_data = dict()
        for pkg_name, pkg_files in data.items():
            cfgs = list()
            cfg_data = list()
            if self.grains_core.os_data().get('os_family') == 'Debian':
                cfg_data = salt.utils.to_str(self._syscall("dpkg", None, None, '--verify',
                                                           pkg_name)[0]).split(os.linesep)
            elif self.grains_core.os_data().get('os_family') in ['SUSE', 'redhat']:
                cfg_data = salt.utils.to_str(self._syscall("rpm", None, None, '-V', '--nodeps', '--nodigest',
                                                           '--nosignature', '--nomtime', '--nolinkto',
                                                           pkg_name)[0]).split(os.linesep)
            for line in cfg_data:
                line = line.strip()
                if not line or line.find(" c ") < 0 or line.split(" ")[0].find("5") < 0:
                    continue
                cfg_file = line.split(" ")[-1]
                if cfg_file in pkg_files:
                    cfgs.append(cfg_file)
            if cfgs:
                f_data[pkg_name] = cfgs

        return f_data

    def _save_cfg_packages(self, data):
        '''
        Save configuration packages. (NG)

        :param data:
        :return:
        '''
        self.db._csv_db.create_table_from_object(Package())
        self.db._csv_db.create_table_from_object(PackageCfgFile())

        pkg_id = 0
        pkg_cfg_id = 0
        for pkg_name, pkg_configs in data.items():
            pkg = Package()
            pkg.id = pkg_id
            pkg.name = pkg_name
            self.db._csv_db.store(pkg)

            for pkg_config in pkg_configs:
                cfg = PackageCfgFile()
                cfg.id = pkg_cfg_id
                cfg.pkgid = pkg_id
                cfg.path = pkg_config
                self.db._csv_db.store(cfg)
                pkg_cfg_id += 1

            pkg_id += 1

    def _save_cfg_pkgs(self, data):
        '''
        Save configuration packages.
        '''
        pkg_id = 0
        pkg_cfg_id = 0
        for pkg_name, pkg_configs in data.items():
            self.db.cursor.execute("INSERT INTO inspector_pkg (id, name) VALUES (?, ?)",
                                   (pkg_id, pkg_name))
            for pkg_config in pkg_configs:
                self.db.cursor.execute("INSERT INTO inspector_pkg_cfg_files (id, pkgid, path) VALUES (?, ?, ?)",
                                       (pkg_cfg_id, pkg_id, pkg_config))
                pkg_cfg_id += 1
            pkg_id += 1

        self.db.connection.commit()

    def _save_payload(self, files, directories, links):
        '''
        Save payload (unmanaged files)

        :param files:
        :param directories:
        :param links:
        :return:
        '''

        self.db._csv_db.create_table_from_object(PayloadFile())

        idx = 0
        for p_type, p_list in (('f', files), ('d', directories), ('l', links,),):
            for p_obj in p_list:
                stats = os.stat(p_obj)

                payload = PayloadFile()
                payload.id = idx
                payload.path = p_obj
                payload.p_type = p_type
                payload.mode = stats.st_mode
                payload.uid = stats.st_uid
                payload.gid = stats.st_gid
                payload.p_size = stats.st_size
                payload.atime = stats.st_atime
                payload.mtime = stats.st_mtime
                payload.ctime = stats.st_ctime

                idx += 1
                self.db._csv_db.store(payload)


    def _save_pld(self, files, directories, links):
        '''
        Save payload (unmanaged files)
        '''
        idx = 0
        for p_type, p_list in (('f', files), ('d', directories), ('l', links,),):
            for p_obj in p_list:
                stats = os.stat(p_obj)
                self.db.cursor.execute("INSERT INTO inspector_payload "
                                       "(id, path, p_type, mode, uid, gid, p_size, atime, mtime, ctime)"
                                       "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                                       (idx, p_obj, p_type, stats.st_mode, stats.st_uid, stats.st_gid, stats.st_size,
                                        stats.st_atime, stats.st_mtime, stats.st_ctime))
                idx += 1

        self.db.connection.commit()

    def _get_managed_files(self):
        '''
        Build a in-memory data of all managed files.
        '''
        if self.grains_core.os_data().get('os_family') == 'Debian':
            return self.__get_managed_files_dpkg()
        elif self.grains_core.os_data().get('os_family') in ['SUSE', 'redhat']:
            return self.__get_managed_files_rpm()

        return list(), list(), list()

    def __get_managed_files_dpkg(self):
        '''
        Get a list of all system files, belonging to the Debian package manager.
        '''
        dirs = set()
        links = set()
        files = set()

        for pkg_name in salt.utils.to_str(self._syscall("dpkg-query", None, None,
                                                        '-Wf', '${binary:Package}\\n')[0]).split(os.linesep):
            pkg_name = pkg_name.strip()
            if not pkg_name:
                continue
            for resource in salt.utils.to_str(self._syscall("dpkg", None, None, '-L', pkg_name)[0]).split(os.linesep):
                resource = resource.strip()
                if not resource or resource in ['/', './', '.']:
                    continue
                if os.path.isdir(resource):
                    dirs.add(resource)
                elif os.path.islink(resource):
                    links.add(resource)
                elif os.path.isfile(resource):
                    files.add(resource)

        return sorted(files), sorted(dirs), sorted(links)

    def __get_managed_files_rpm(self):
        '''
        Get a list of all system files, belonging to the RedHat package manager.
        '''
        dirs = set()
        links = set()
        files = set()

        for line in salt.utils.to_str(self._syscall("rpm", None, None, '-qlav')[0]).split(os.linesep):
            line = line.strip()
            if not line:
                continue
            line = line.replace("\t", " ").split(" ")
            if line[0][0] == "d":
                dirs.add(line[-1])
            elif line[0][0] == "l":
                links.add(line[-1])
            elif line[0][0] == "-":
                files.add(line[-1])

        return sorted(files), sorted(dirs), sorted(links)

    def _get_all_files(self, path, *exclude):
        '''
        Walk implementation. Version in python 2.x and 3.x works differently.
        '''
        files = list()
        dirs = list()
        links = list()

        for obj in os.listdir(path):
            obj = os.path.join(path, obj)
            valid = True
            for ex_obj in exclude:
                if obj.startswith(str(ex_obj)):
                    valid = False
                    continue
            if not valid or not os.path.exists(obj):
                continue
            if os.path.islink(obj):
                links.append(obj)
            elif os.path.isdir(obj):
                dirs.append(obj)
                f_obj, d_obj, l_obj = self._get_all_files(obj, *exclude)
                files.extend(f_obj)
                dirs.extend(d_obj)
                links.extend(l_obj)
            elif os.path.isfile(obj):
                files.append(obj)

        return sorted(files), sorted(dirs), sorted(links)

    def _get_unmanaged_files(self, managed, system_all):
        '''
        Get the intersection between all files and managed files.
        '''
        def intr(src, data):
            out = set()
            for d_el in data:
                if d_el not in src:
                    out.add(d_el)
            return out

        m_files, m_dirs, m_links = managed
        s_files, s_dirs, s_links = system_all

        return sorted(intr(m_files, s_files)), sorted(intr(m_dirs, s_dirs)), sorted(intr(m_links, s_links))

    def _scan_payload(self):
        '''
        Scan the system.
        '''
        # Get ignored points
        allowed = list()
        self.db.cursor.execute("SELECT path FROM inspector_allowed")
        for alwd_path in self.db.cursor.fetchall():
            if os.path.exists(alwd_path[0]):
                allowed.append(alwd_path[0])

        ignored = list()
        if not allowed:
            self.db.cursor.execute("SELECT path FROM inspector_ignored")
            for ign_path in self.db.cursor.fetchall():
                ignored.append(ign_path[0])

        all_files = list()
        all_dirs = list()
        all_links = list()
        for entry_path in [pth for pth in (allowed or os.listdir("/")) if pth]:
            if entry_path[0] != "/":
                entry_path = "/{0}".format(entry_path)
            if entry_path in ignored or os.path.islink(entry_path):
                continue
            e_files, e_dirs, e_links = self._get_all_files(entry_path, *ignored)
            all_files.extend(e_files)
            all_dirs.extend(e_dirs)
            all_links.extend(e_links)

        return self._get_unmanaged_files(self._get_managed_files(), (all_files, all_dirs, all_links,))

    def _prepare_full_scan(self, **kwargs):
        '''
        Prepare full system scan by setting up the database etc.
        '''
        # TODO: Backup the SQLite database. Backup should be restored automatically if current db failed while queried.
        self.db.purge()

        # Add ignored filesystems
        ignored_fs = set()
        ignored_fs |= set(self.IGNORE_PATHS)
        mounts = fsutils._get_mounts()
        for device, data in mounts.items():
            if device in self.IGNORE_MOUNTS:
                for mpt in data:
                    ignored_fs.add(mpt['mount_point'])
                continue
            for mpt in data:
                if mpt['type'] in self.IGNORE_FS_TYPES:
                    ignored_fs.add(mpt['mount_point'])

        # Remove leafs of ignored filesystems
        ignored_all = list()
        for entry in sorted(list(ignored_fs)):
            valid = True
            for e_entry in ignored_all:
                if entry.startswith(e_entry):
                    valid = False
                    break
            if valid:
                ignored_all.append(entry)
        # Save to the database for further scan
        for ignored_dir in ignored_all:
            self.db.cursor.execute("INSERT INTO inspector_ignored VALUES (?)", (ignored_dir,))

        # Add allowed filesystems (overrides all above at full scan)
        allowed = [elm for elm in kwargs.get("filter", "").split(",") if elm]
        for allowed_dir in allowed:
            self.db.cursor.execute("INSERT INTO inspector_allowed VALUES (?)", (allowed_dir,))

        self.db.connection.commit()

        return ignored_all

    def _init_env(self):
        '''
        Initialize some Salt environment.
        '''
        from salt.config import minion_config
        from salt.grains import core as g_core
        g_core.__opts__ = minion_config(self.DEFAULT_MINION_CONFIG_PATH)
        self.grains_core = g_core

    def snapshot(self, mode):
        '''
        Take a snapshot of the system.
        '''
        self._init_env()

        changed_cfg_pkgs = self._get_changed_cfg_pkgs(self._get_cfg_pkgs())
        self._save_cfg_packages(changed_cfg_pkgs)

        payload = self._scan_payload()
        self._save_payload(*payload)

        # Old stuff
        self._save_cfg_pkgs(changed_cfg_pkgs)
        self._save_pld(*payload)

    def request_snapshot(self, mode, priority=19, **kwargs):
        '''
        Take a snapshot of the system.
        '''
        if mode not in self.MODE:
            raise InspectorSnapshotException("Unknown mode: '{0}'".format(mode))

        self._prepare_full_scan(**kwargs)

        os.system("nice -{0} python {1} {2} {3} {4} & > /dev/null".format(
            priority, __file__, os.path.dirname(self.pidfile), os.path.dirname(self.dbfile), mode))

    def export(self, description, local=False, path='/tmp', format='qcow2'):
        '''
        Export description for Kiwi.

        :param local:
        :param path:
        :return:
        '''
        kiwiproc.__salt__ = __salt__
        return kiwiproc.KiwiExporter(grains=__grains__,
                                     format=format).load(**description).export('something')

    def build(self, format='qcow2', path='/tmp'):
        '''
        Build an image using Kiwi.

        :param format:
        :param path:
        :return:
        '''
        if kiwi is None:
            msg = 'Unable to build the image due to the missing dependencies: Kiwi module is not available.'
            log.error(msg)
            raise CommandExecutionError(msg)

        raise CommandExecutionError("Build is not yet implemented")


def is_alive(pidfile):
    '''
    Check if PID is still alive.
    '''
    # Just silencing os.kill exception if no such PID, therefore try/pass.
    try:
        os.kill(int(open(pidfile).read().strip()), 0)
        sys.exit(1)
    except Exception as ex:
        pass


def main(dbfile, pidfile, mode):
    '''
    Main analyzer routine.
    '''
    Inspector(dbfile, pidfile).snapshot(mode)


if __name__ == '__main__':
    if len(sys.argv) != 4:
        print("This module is not intended to use directly!", file=sys.stderr)
        sys.exit(1)

    pidfile, dbfile, mode = sys.argv[1:]
    is_alive(pidfile)

    # Double-fork stuff
    try:
        if os.fork() > 0:
            reinit_crypto()
            sys.exit(0)
        else:
            reinit_crypto()
    except OSError as ex:
        sys.exit(1)

    os.setsid()
    os.umask(0)

    try:
        pid = os.fork()
        if pid > 0:
            reinit_crypto()
            fpid = open(os.path.join(pidfile, EnvLoader.PID_FILE), "w")
            fpid.write("{0}\n".format(pid))
            fpid.close()
            sys.exit(0)
    except OSError as ex:
        sys.exit(1)

    reinit_crypto()
    main(dbfile, pidfile, mode)
