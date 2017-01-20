# -*- coding: utf-8 -*-
'''
A module to wrap (non-Windows) archive calls

.. versionadded:: 2014.1.0
'''
from __future__ import absolute_import
import contextlib  # For < 2.7 compat
import errno
import logging
import os
import re
import shlex
import stat
import tarfile
import tempfile
import zipfile
try:
    from shlex import quote as _quote  # pylint: disable=E0611
except ImportError:
    from pipes import quote as _quote

try:
    import rarfile
    HAS_RARFILE = True
except ImportError:
    HAS_RARFILE = False

# Import salt libs
from salt.exceptions import SaltInvocationError, CommandExecutionError
from salt.ext.six import string_types, integer_types
from salt.ext.six.moves.urllib.parse import urlparse as _urlparse  # pylint: disable=no-name-in-module
import salt.utils
import salt.utils.itertools

# TODO: Check that the passed arguments are correct

# Don't shadow built-in's.
__func_alias__ = {
    'zip_': 'zip',
    'list_': 'list'
}

log = logging.getLogger(__name__)


def list_(name,
          archive_format=None,
          options=None,
          strip_components=None,
          clean=False,
          verbose=False,
          saltenv='base'):
    '''
    .. versionadded:: 2016.11.0
    .. versionchanged:: 2016.11.2
        The rarfile_ Python module is now supported for listing the contents of
        rar archives. This is necessary on minions with older releases of the
        ``rar`` CLI tool, which do not support listing the contents in a
        parsable format.

    .. _rarfile: https://pypi.python.org/pypi/rarfile

    List the files and directories in an tar, zip, or rar archive.

    .. note::
        This function will only provide results for XZ-compressed archives if
        the xz_ CLI command is available, as Python does not at this time
        natively support XZ compression in its tarfile_ module. Keep in mind
        however that most Linux distros ship with xz_ already installed.

        To check if a given minion has xz_, the following Salt command can be
        run:

        .. code-block:: bash

            salt minion_id cmd.which xz

        If ``None`` is returned, then xz_ is not present and must be installed.
        It is widely available and should be packaged as either ``xz`` or
        ``xz-utils``.

    name
        Path/URL of archive

    archive_format
        Specify the format of the archive (``tar``, ``zip``, or ``rar``). If
        this argument is omitted, the archive format will be guessed based on
        the value of the ``name`` parameter.

    options
        **For tar archives only.** This function will, by default, try to use
        the tarfile_ module from the Python standard library to get a list of
        files/directories. If this method fails, then it will fall back to
        using the shell to decompress the archive to stdout and pipe the
        results to ``tar -tf -`` to produce a list of filenames. XZ-compressed
        archives are already supported automatically, but in the event that the
        tar archive uses a different sort of compression not supported natively
        by tarfile_, this option can be used to specify a command that will
        decompress the archive to stdout. For example:

        .. code-block:: bash

            salt minion_id archive.list /path/to/foo.tar.gz options='gzip --decompress --stdout'

        .. note::
            It is not necessary to manually specify options for gzip'ed
            archives, as gzip compression is natively supported by tarfile_.

    strip_components
        This argument specifies a number of top-level directories to strip from
        the results. This is similar to the paths that would be extracted if
        ``--strip-components`` (or ``--strip``) were used when extracting tar
        archives.

        .. versionadded:: 2016.11.2

    clean : False
        Set this value to ``True`` to delete the path referred to by ``name``
        once the contents have been listed. This option should be used with
        care.

        .. note::
            If there is an error listing the archive's contents, the cached
            file will not be removed, to allow for troubleshooting.

    verbose : False
        If ``False``, this function will return a list of files/dirs in the
        archive. If ``True``, it will return a dictionary categorizing the
        paths into separate keys containing the directory names, file names,
        and also directories/files present in the top level of the archive.

        .. versionchanged:: 2016.11.2
            This option now includes symlinks in their own list. Before, they
            were included with files.

    saltenv : base
        Specifies the fileserver environment from which to retrieve
        ``archive``. This is only applicable when ``archive`` is a file from
        the ``salt://`` fileserver.

    .. _tarfile: https://docs.python.org/2/library/tarfile.html
    .. _xz: http://tukaani.org/xz/

    CLI Examples:

    .. code-block:: bash

            salt '*' archive.list /path/to/myfile.tar.gz
            salt '*' archive.list /path/to/myfile.tar.gz strip_components=1
            salt '*' archive.list salt://foo.tar.gz
            salt '*' archive.list https://domain.tld/myfile.zip
            salt '*' archive.list ftp://10.1.2.3/foo.rar
    '''
    def _list_tar(name, cached, decompress_cmd, failhard=False):
        dirs = []
        files = []
        links = []
        try:
            with contextlib.closing(tarfile.open(cached)) as tar_archive:
                for member in tar_archive.getmembers():
                    if member.issym():
                        links.append(member.name)
                    elif member.isdir():
                        dirs.append(member.name + '/')
                    else:
                        files.append(member.name)
            return dirs, files, links

        except tarfile.ReadError:
            if not failhard:
                if not salt.utils.which('tar'):
                    raise CommandExecutionError('\'tar\' command not available')
                if decompress_cmd is not None:
                    # Guard against shell injection
                    try:
                        decompress_cmd = ' '.join(
                            [_quote(x) for x in shlex.split(decompress_cmd)]
                        )
                    except AttributeError:
                        raise CommandExecutionError('Invalid CLI options')
                else:
                    if salt.utils.which('xz') \
                            and __salt__['cmd.retcode'](['xz', '-l', cached],
                                                        python_shell=False,
                                                        ignore_retcode=True) == 0:
                        decompress_cmd = 'xz --decompress --stdout'

                if decompress_cmd:
                    fd, decompressed = tempfile.mkstemp()
                    os.close(fd)
                    try:
                        cmd = '{0} {1} > {2}'.format(decompress_cmd,
                                                     _quote(cached),
                                                     _quote(decompressed))
                        result = __salt__['cmd.run_all'](cmd, python_shell=True)
                        if result['retcode'] != 0:
                            raise CommandExecutionError(
                                'Failed to decompress {0}'.format(name),
                                info={'error': result['stderr']}
                            )
                        return _list_tar(name, decompressed, None, True)
                    finally:
                        try:
                            os.remove(decompressed)
                        except OSError as exc:
                            if exc.errno != errno.ENOENT:
                                log.warning(
                                    'Failed to remove intermediate '
                                    'decompressed archive %s: %s',
                                    decompressed, exc.__str__()
                                )

        raise CommandExecutionError(
            'Unable to list contents of {0}. If this is an XZ-compressed tar '
            'archive, install XZ Utils to enable listing its contents. If it '
            'is compressed using something other than XZ, it may be necessary '
            'to specify CLI options to decompress the archive. See the '
            'documentation for details.'.format(name)
        )

    def _list_zip(name, cached):
        '''
        Password-protected ZIP archives can still be listed by zipfile, so
        there is no reason to invoke the unzip command.
        '''
        dirs = []
        files = []
        links = []
        try:
            with contextlib.closing(zipfile.ZipFile(cached)) as zip_archive:
                for member in zip_archive.infolist():
                    mode = member.external_attr >> 16
                    path = member.filename
                    if stat.S_ISLNK(mode):
                        links.append(path)
                    elif stat.S_ISDIR(mode):
                        dirs.append(path)
                    else:
                        files.append(path)
            return dirs, files, links
        except zipfile.BadZipfile:
            raise CommandExecutionError('{0} is not a ZIP file'.format(name))

    def _list_rar(name, cached):
        dirs = []
        files = []
        if HAS_RARFILE:
            with rarfile.RarFile(cached) as rf:
                for member in rf.infolist():
                    path = member.filename.replace('\\', '/')
                    if member.isdir():
                        dirs.append(path + '/')
                    else:
                        files.append(path)
        else:
            if not salt.utils.which('rar'):
                raise CommandExecutionError(
                    'rar command not available, is it installed?'
                )
            output = __salt__['cmd.run'](
                ['rar', 'lt', name],
                python_shell=False,
                ignore_retcode=False)
            matches = re.findall(r'Name:\s*([^\n]+)\s*Type:\s*([^\n]+)', output)
            for path, type_ in matches:
                if type_ == 'Directory':
                    dirs.append(path + '/')
                else:
                    files.append(path)
            if not dirs and not files:
                raise CommandExecutionError(
                    'Failed to list {0}, is it a rar file? If so, the '
                    'installed version of rar may be too old to list data in '
                    'a parsable format. Installing the rarfile Python module '
                    'may be an easier workaround if newer rar is not readily '
                    'available.'.format(name),
                    info={'error': output}
                )
        return dirs, files, []

    cached = __salt__['cp.cache_file'](name, saltenv)
    if not cached:
        raise CommandExecutionError('Failed to cache {0}'.format(name))

    try:
        if strip_components:
            try:
                int(strip_components)
            except ValueError:
                strip_components = -1

            if strip_components <= 0:
                raise CommandExecutionError(
                    '\'strip_components\' must be a positive integer'
                )

        parsed = _urlparse(name)
        path = parsed.path or parsed.netloc

        def _unsupported_format(archive_format):
            if archive_format is None:
                raise CommandExecutionError(
                    'Unable to guess archive format, please pass an '
                    '\'archive_format\' argument.'
                )
            raise CommandExecutionError(
                'Unsupported archive format \'{0}\''.format(archive_format)
            )

        if not archive_format:
            guessed_format = salt.utils.files.guess_archive_type(path)
            if guessed_format is None:
                _unsupported_format(archive_format)
            archive_format = guessed_format

        func = locals().get('_list_' + archive_format)
        if not hasattr(func, '__call__'):
            _unsupported_format(archive_format)

        args = (options,) if archive_format == 'tar' else ()
        try:
            dirs, files, links = func(name, cached, *args)
        except (IOError, OSError) as exc:
            raise CommandExecutionError(
                'Failed to list contents of {0}: {1}'.format(
                    name, exc.__str__()
                )
            )
        except CommandExecutionError as exc:
            raise
        except Exception as exc:
            raise CommandExecutionError(
                'Uncaught exception \'{0}\' when listing contents of {1}'
                .format(exc, name)
            )

        if clean:
            try:
                os.remove(cached)
                log.debug('Cleaned cached archive %s', cached)
            except OSError as exc:
                if exc.errno != errno.ENOENT:
                    log.warning(
                        'Failed to clean cached archive %s: %s',
                        cached, exc.__str__()
                    )

        if strip_components:
            for item in (dirs, files, links):
                for index, path in enumerate(item):
                    try:
                        # Strip off the specified number of directory
                        # boundaries, and grab what comes after the last
                        # stripped path separator.
                        item[index] = item[index].split(
                            os.sep, strip_components)[strip_components]
                    except IndexError:
                        # Path is excluded by strip_components because it is not
                        # deep enough. Set this to an empty string so it can
                        # be removed in the generator expression below.
                        item[index] = ''

                # Remove all paths which were excluded
                item[:] = (x for x in item if x)
                item.sort()

        if verbose:
            ret = {'dirs': dirs, 'files': files, 'links': links}
            ret['top_level_dirs'] = [x for x in dirs if x.count('/') == 1]
            ret['top_level_files'] = [x for x in files if x.count('/') == 0]
            ret['top_level_links'] = [x for x in links if x.count('/') == 0]
        else:
            ret = sorted(dirs + files + links)
        return ret

    except CommandExecutionError as exc:
        # Reraise with cache path in the error so that the user can examine the
        # cached archive for troubleshooting purposes.
        info = exc.info or {}
        info['archive location'] = cached
        raise CommandExecutionError(exc.error, info=info)


@salt.utils.decorators.which('tar')
def tar(options, tarfile, sources=None, dest=None,
        cwd=None, template=None, runas=None):
    '''
    .. note::

        This function has changed for version 0.17.0. In prior versions, the
        ``cwd`` and ``template`` arguments must be specified, with the source
        directories/files coming as a space-separated list at the end of the
        command. Beginning with 0.17.0, ``sources`` must be a comma-separated
        list, and the ``cwd`` and ``template`` arguments are optional.

    Uses the tar command to pack, unpack, etc. tar files


    options
        Options to pass to the tar command

        .. versionchanged:: 2015.8.0

            The mandatory `-` prefixing has been removed.  An options string
            beginning with a `--long-option`, would have uncharacteristically
            needed its first `-` removed under the former scheme.

            Also, tar will parse its options differently if short options are
            used with or without a preceding `-`, so it is better to not
            confuse the user into thinking they're using the non-`-` format,
            when really they are using the with-`-` format.

    tarfile
        The filename of the tar archive to pack/unpack

    sources
        Comma delimited list of files to **pack** into the tarfile. Can also be
        passed as a Python list.

    dest
        The destination directory into which to **unpack** the tarfile

    cwd : None
        The directory in which the tar command should be executed. If not
        specified, will default to the home directory of the user under which
        the salt minion process is running.

    template : None
        Can be set to 'jinja' or another supported template engine to render
        the command arguments before execution:

        .. code-block:: bash

            salt '*' archive.tar -cjvf /tmp/salt.tar.bz2 {{grains.saltpath}} template=jinja

    CLI Examples:

    .. code-block:: bash

        # Create a tarfile
        salt '*' archive.tar -cjvf /tmp/tarfile.tar.bz2 /tmp/file_1,/tmp/file_2
        # Unpack a tarfile
        salt '*' archive.tar xf foo.tar dest=/target/directory
    '''
    if not options:
        # Catch instances were people pass an empty string for the "options"
        # argument. Someone would have to be really silly to do this, but we
        # should at least let them know of their silliness.
        raise SaltInvocationError('Tar options can not be empty')

    if isinstance(sources, string_types):
        sources = [s.strip() for s in sources.split(',')]

    cmd = ['tar']
    if dest:
        cmd.extend(['-C', '{0}'.format(dest)])

    if options:
        cmd.extend(options.split())

    cmd.extend(['{0}'.format(tarfile)])

    if sources is not None:
        cmd.extend(sources)

    return __salt__['cmd.run'](cmd,
                               cwd=cwd,
                               template=template,
                               runas=runas,
                               python_shell=False).splitlines()


@salt.utils.decorators.which('gzip')
def gzip(sourcefile, template=None, runas=None, options=None):
    '''
    Uses the gzip command to create gzip files

    template : None
        Can be set to 'jinja' or another supported template engine to render
        the command arguments before execution:

        .. code-block:: bash

            salt '*' archive.gzip template=jinja /tmp/{{grains.id}}.txt

    runas : None
        The user with which to run the gzip command line

    options : None
        Pass any additional arguments to gzip

        .. versionadded:: 2016.3.4

    CLI Example:

    .. code-block:: bash

        # Create /tmp/sourcefile.txt.gz
        salt '*' archive.gzip /tmp/sourcefile.txt
        salt '*' archive.gzip /tmp/sourcefile.txt options='-9 --verbose'
    '''
    cmd = ['gzip']
    if options:
        cmd.append(options)
    cmd.append('{0}'.format(sourcefile))

    return __salt__['cmd.run'](cmd,
                               template=template,
                               runas=runas,
                               python_shell=False).splitlines()


@salt.utils.decorators.which('gunzip')
def gunzip(gzipfile, template=None, runas=None, options=None):
    '''
    Uses the gunzip command to unpack gzip files

    template : None
        Can be set to 'jinja' or another supported template engine to render
        the command arguments before execution:

        .. code-block:: bash

            salt '*' archive.gunzip template=jinja /tmp/{{grains.id}}.txt.gz

    runas : None
        The user with which to run the gzip command line

    options : None
        Pass any additional arguments to gzip

        .. versionadded:: 2016.3.4

    CLI Example:

    .. code-block:: bash

        # Create /tmp/sourcefile.txt
        salt '*' archive.gunzip /tmp/sourcefile.txt.gz
        salt '*' archive.gunzip /tmp/sourcefile.txt options='--verbose'
    '''
    cmd = ['gunzip']
    if options:
        cmd.append(options)
    cmd.append('{0}'.format(gzipfile))

    return __salt__['cmd.run'](cmd,
                               template=template,
                               runas=runas,
                               python_shell=False).splitlines()


@salt.utils.decorators.which('zip')
def cmd_zip(zip_file, sources, template=None, cwd=None, runas=None):
    '''
    .. versionadded:: 2015.5.0
        In versions 2014.7.x and earlier, this function was known as
        ``archive.zip``.

    Uses the ``zip`` command to create zip files. This command is part of the
    `Info-ZIP`_ suite of tools, and is typically packaged as simply ``zip``.

    .. _`Info-ZIP`: http://www.info-zip.org/

    zip_file
        Path of zip file to be created

    sources
        Comma-separated list of sources to include in the zip file. Sources can
        also be passed in a Python list.

    template : None
        Can be set to 'jinja' or another supported template engine to render
        the command arguments before execution:

        .. code-block:: bash

            salt '*' archive.cmd_zip template=jinja /tmp/zipfile.zip /tmp/sourcefile1,/tmp/{{grains.id}}.txt

    cwd : None
        Use this argument along with relative paths in ``sources`` to create
        zip files which do not contain the leading directories. If not
        specified, the zip file will be created as if the cwd was ``/``, and
        creating a zip file of ``/foo/bar/baz.txt`` will contain the parent
        directories ``foo`` and ``bar``. To create a zip file containing just
        ``baz.txt``, the following command would be used:

        .. code-block:: bash

            salt '*' archive.cmd_zip /tmp/baz.zip baz.txt cwd=/foo/bar

        .. versionadded:: 2014.7.1

    runas : None
        Create the zip file as the specified user. Defaults to the user under
        which the minion is running.

        .. versionadded:: 2015.5.0


    CLI Example:

    .. code-block:: bash

        salt '*' archive.cmd_zip /tmp/zipfile.zip /tmp/sourcefile1,/tmp/sourcefile2
    '''
    if isinstance(sources, string_types):
        sources = [s.strip() for s in sources.split(',')]
    cmd = ['zip', '-r']
    cmd.append('{0}'.format(zip_file))
    cmd.extend(sources)
    return __salt__['cmd.run'](cmd,
                               cwd=cwd,
                               template=template,
                               runas=runas,
                               python_shell=False).splitlines()


@salt.utils.decorators.depends('zipfile', fallback_function=cmd_zip)
def zip_(zip_file, sources, template=None, cwd=None, runas=None):
    '''
    Uses the ``zipfile`` Python module to create zip files

    .. versionchanged:: 2015.5.0
        This function was rewritten to use Python's native zip file support.
        The old functionality has been preserved in the new function
        :mod:`archive.cmd_zip <salt.modules.archive.cmd_zip>`. For versions
        2014.7.x and earlier, see the :mod:`archive.cmd_zip
        <salt.modules.archive.cmd_zip>` documentation.

    zip_file
        Path of zip file to be created

    sources
        Comma-separated list of sources to include in the zip file. Sources can
        also be passed in a Python list.

    template : None
        Can be set to 'jinja' or another supported template engine to render
        the command arguments before execution:

        .. code-block:: bash

            salt '*' archive.zip template=jinja /tmp/zipfile.zip /tmp/sourcefile1,/tmp/{{grains.id}}.txt

    cwd : None
        Use this argument along with relative paths in ``sources`` to create
        zip files which do not contain the leading directories. If not
        specified, the zip file will be created as if the cwd was ``/``, and
        creating a zip file of ``/foo/bar/baz.txt`` will contain the parent
        directories ``foo`` and ``bar``. To create a zip file containing just
        ``baz.txt``, the following command would be used:

        .. code-block:: bash

            salt '*' archive.zip /tmp/baz.zip baz.txt cwd=/foo/bar

    runas : None
        Create the zip file as the specified user. Defaults to the user under
        which the minion is running.


    CLI Example:

    .. code-block:: bash

        salt '*' archive.zip /tmp/zipfile.zip /tmp/sourcefile1,/tmp/sourcefile2
    '''
    if runas:
        euid = os.geteuid()
        egid = os.getegid()
        uinfo = __salt__['user.info'](runas)
        if not uinfo:
            raise SaltInvocationError(
                'User \'{0}\' does not exist'.format(runas)
            )

    zip_file, sources = _render_filenames(zip_file, sources, None, template)

    if isinstance(sources, string_types):
        sources = [x.strip() for x in sources.split(',')]
    elif isinstance(sources, (float, integer_types)):
        sources = [str(sources)]

    if not cwd:
        for src in sources:
            if not os.path.isabs(src):
                raise SaltInvocationError(
                    'Relative paths require the \'cwd\' parameter'
                )
    else:
        def _bad_cwd():
            raise SaltInvocationError('cwd must be absolute')
        try:
            if not os.path.isabs(cwd):
                _bad_cwd()
        except AttributeError:
            _bad_cwd()

    if runas and (euid != uinfo['uid'] or egid != uinfo['gid']):
        # Change the egid first, as changing it after the euid will fail
        # if the runas user is non-privileged.
        os.setegid(uinfo['gid'])
        os.seteuid(uinfo['uid'])

    try:
        exc = None
        archived_files = []
        with contextlib.closing(zipfile.ZipFile(zip_file, 'w', zipfile.ZIP_DEFLATED)) as zfile:
            for src in sources:
                if cwd:
                    src = os.path.join(cwd, src)
                if os.path.exists(src):
                    if os.path.isabs(src):
                        rel_root = '/'
                    else:
                        rel_root = cwd if cwd is not None else '/'
                    if os.path.isdir(src):
                        for dir_name, sub_dirs, files in os.walk(src):
                            if cwd and dir_name.startswith(cwd):
                                arc_dir = salt.utils.relpath(dir_name, cwd)
                            else:
                                arc_dir = salt.utils.relpath(dir_name,
                                                             rel_root)
                            if arc_dir:
                                archived_files.append(arc_dir + '/')
                                zfile.write(dir_name, arc_dir)
                            for filename in files:
                                abs_name = os.path.join(dir_name, filename)
                                arc_name = os.path.join(arc_dir, filename)
                                archived_files.append(arc_name)
                                zfile.write(abs_name, arc_name)
                    else:
                        if cwd and src.startswith(cwd):
                            arc_name = salt.utils.relpath(src, cwd)
                        else:
                            arc_name = salt.utils.relpath(src, rel_root)
                        archived_files.append(arc_name)
                        zfile.write(src, arc_name)
    except Exception as exc:
        pass
    finally:
        # Restore the euid/egid
        if runas:
            os.seteuid(euid)
            os.setegid(egid)
        if exc is not None:
            # Wait to raise the exception until euid/egid are restored to avoid
            # permission errors in writing to minion log.
            raise CommandExecutionError(
                'Exception encountered creating zipfile: {0}'.format(exc)
            )

    return archived_files


@salt.utils.decorators.which('unzip')
def cmd_unzip(zip_file,
              dest,
              excludes=None,
              options=None,
              template=None,
              runas=None,
              trim_output=False,
              password=None):
    '''
    .. versionadded:: 2015.5.0
        In versions 2014.7.x and earlier, this function was known as
        ``archive.unzip``.

    Uses the ``unzip`` command to unpack zip files. This command is part of the
    `Info-ZIP`_ suite of tools, and is typically packaged as simply ``unzip``.

    .. _`Info-ZIP`: http://www.info-zip.org/

    zip_file
        Path of zip file to be unpacked

    dest
        The destination directory into which the file should be unpacked

    excludes : None
        Comma-separated list of files not to unpack. Can also be passed in a
        Python list.

    template : None
        Can be set to 'jinja' or another supported template engine to render
        the command arguments before execution:

        .. code-block:: bash

            salt '*' archive.cmd_unzip template=jinja /tmp/zipfile.zip '/tmp/{{grains.id}}' excludes=file_1,file_2

    options
        Optional when using ``zip`` archives, ignored when usign other archives
        files. This is mostly used to overwrite exsiting files with ``o``.
        This options are only used when ``unzip`` binary is used.

        .. versionadded:: 2016.3.1

    runas : None
        Unpack the zip file as the specified user. Defaults to the user under
        which the minion is running.

        .. versionadded:: 2015.5.0

    trim_output : False
        The number of files we should output on success before the rest are trimmed, if this is
        set to True then it will default to 100

    password
        Password to use with password protected zip files

        .. note::
            This is not considered secure. It is recommended to instead use
            :py:func:`archive.unzip <salt.modules.archive.unzip>` for
            password-protected ZIP files. If a password is used here, then the
            unzip command run to extract the ZIP file will not show up in the
            minion log like most shell commands Salt runs do. However, the
            password will still be present in the events logged to the minion
            log at the ``debug`` log level. If the minion is logging at
            ``debug`` (or more verbose), then be advised that the password will
            appear in the log.

        .. versionadded:: 2016.11.0


    CLI Example:

    .. code-block:: bash

        salt '*' archive.cmd_unzip /tmp/zipfile.zip /home/strongbad/ excludes=file_1,file_2
    '''
    if isinstance(excludes, string_types):
        excludes = [x.strip() for x in excludes.split(',')]
    elif isinstance(excludes, (float, integer_types)):
        excludes = [str(excludes)]

    cmd = ['unzip']
    if password:
        cmd.extend(['-P', password])
    if options:
        cmd.append('{0}'.format(options))
    cmd.extend(['{0}'.format(zip_file), '-d', '{0}'.format(dest)])

    if excludes is not None:
        cmd.append('-x')
        cmd.extend(excludes)

    result = __salt__['cmd.run_all'](
        cmd,
        template=template,
        runas=runas,
        python_shell=False,
        redirect_stderr=True,
        output_loglevel='quiet' if password else 'debug')

    if result['retcode'] != 0:
        raise CommandExecutionError(result['stdout'])

    return _trim_files(result['stdout'].splitlines(), trim_output)


def unzip(zip_file,
          dest,
          excludes=None,
          options=None,
          template=None,
          runas=None,
          trim_output=False,
          password=None,
          extract_perms=True):
    '''
    Uses the ``zipfile`` Python module to unpack zip files

    .. versionchanged:: 2015.5.0
        This function was rewritten to use Python's native zip file support.
        The old functionality has been preserved in the new function
        :mod:`archive.cmd_unzip <salt.modules.archive.cmd_unzip>`. For versions
        2014.7.x and earlier, see the :mod:`archive.cmd_zip
        <salt.modules.archive.cmd_zip>` documentation.

    zip_file
        Path of zip file to be unpacked

    dest
        The destination directory into which the file should be unpacked

    excludes : None
        Comma-separated list of files not to unpack. Can also be passed in a
        Python list.

    options
        This options are only used when ``unzip`` binary is used. In this
        function is ignored.

        .. versionadded:: 2016.3.1

    template : None
        Can be set to 'jinja' or another supported template engine to render
        the command arguments before execution:

        .. code-block:: bash

            salt '*' archive.unzip template=jinja /tmp/zipfile.zip /tmp/{{grains.id}}/ excludes=file_1,file_2

    runas : None
        Unpack the zip file as the specified user. Defaults to the user under
        which the minion is running.

    trim_output : False
        The number of files we should output on success before the rest are trimmed, if this is
        set to True then it will default to 100

    CLI Example:

    .. code-block:: bash

        salt '*' archive.unzip /tmp/zipfile.zip /home/strongbad/ excludes=file_1,file_2

    password
        Password to use with password protected zip files

        .. note::
            The password will be present in the events logged to the minion log
            file at the ``debug`` log level. If the minion is logging at
            ``debug`` (or more verbose), then be advised that the password will
            appear in the log.

        .. versionadded:: 2016.3.0

    extract_perms : True
        The Python zipfile_ module does not extract file/directory attributes
        by default. When this argument is set to ``True``, Salt will attempt to
        apply the file permision attributes to the extracted files/folders.

        On Windows, only the read-only flag will be extracted as set within the
        zip file, other attributes (i.e. user/group permissions) are ignored.

        Set this argument to ``False`` to disable this behavior.

        .. versionadded:: 2016.11.0

    .. _zipfile: https://docs.python.org/2/library/zipfile.html

    CLI Example:

    .. code-block:: bash

        salt '*' archive.unzip /tmp/zipfile.zip /home/strongbad/ password='BadPassword'
    '''
    if not excludes:
        excludes = []
    if runas:
        euid = os.geteuid()
        egid = os.getegid()
        uinfo = __salt__['user.info'](runas)
        if not uinfo:
            raise SaltInvocationError(
                "User '{0}' does not exist".format(runas)
            )

    zip_file, dest = _render_filenames(zip_file, dest, None, template)

    if runas and (euid != uinfo['uid'] or egid != uinfo['gid']):
        # Change the egid first, as changing it after the euid will fail
        # if the runas user is non-privileged.
        os.setegid(uinfo['gid'])
        os.seteuid(uinfo['uid'])

    try:
        exc = None
        # Define cleaned_files here so that an exception will not prevent this
        # variable from being defined and cause a NameError in the return
        # statement at the end of the function.
        cleaned_files = []
        with contextlib.closing(zipfile.ZipFile(zip_file, "r")) as zfile:
            files = zfile.namelist()

            if isinstance(excludes, string_types):
                excludes = [x.strip() for x in excludes.split(',')]
            elif isinstance(excludes, (float, integer_types)):
                excludes = [str(excludes)]

            cleaned_files.extend([x for x in files if x not in excludes])
            for target in cleaned_files:
                if target not in excludes:
                    if salt.utils.is_windows() is False:
                        info = zfile.getinfo(target)
                        # Check if zipped file is a symbolic link
                        if stat.S_ISLNK(info.external_attr >> 16):
                            source = zfile.read(target)
                            os.symlink(source, os.path.join(dest, target))
                            continue
                    zfile.extract(target, dest, password)
                    if extract_perms:
                        os.chmod(os.path.join(dest, target), zfile.getinfo(target).external_attr >> 16)
    except Exception as exc:
        pass
    finally:
        # Restore the euid/egid
        if runas:
            os.seteuid(euid)
            os.setegid(egid)
        if exc is not None:
            # Wait to raise the exception until euid/egid are restored to avoid
            # permission errors in writing to minion log.
            raise CommandExecutionError(
                'Exception encountered unpacking zipfile: {0}'.format(exc)
            )

    return _trim_files(cleaned_files, trim_output)


def is_encrypted(name, clean=False, saltenv='base'):
    '''
    .. versionadded:: 2016.11.0

    Returns ``True`` if the zip archive is password-protected, ``False`` if
    not. If the specified file is not a ZIP archive, an error will be raised.

    name
        The path / URL of the archive to check.

    clean : False
        Set this value to ``True`` to delete the path referred to by ``name``
        once the contents have been listed. This option should be used with
        care.

        .. note::
            If there is an error listing the archive's contents, the cached
            file will not be removed, to allow for troubleshooting.


    CLI Examples:

    .. code-block:: bash

            salt '*' archive.is_encrypted /path/to/myfile.zip
            salt '*' archive.is_encrypted salt://foo.zip
            salt '*' archive.is_encrypted salt://foo.zip saltenv=dev
            salt '*' archive.is_encrypted https://domain.tld/myfile.zip clean=True
            salt '*' archive.is_encrypted ftp://10.1.2.3/foo.zip
    '''
    cached = __salt__['cp.cache_file'](name, saltenv)
    if not cached:
        raise CommandExecutionError('Failed to cache {0}'.format(name))

    archive_info = {'archive location': cached}
    try:
        with contextlib.closing(zipfile.ZipFile(cached)) as zip_archive:
            zip_archive.testzip()
    except RuntimeError:
        ret = True
    except zipfile.BadZipfile:
        raise CommandExecutionError(
            '{0} is not a ZIP file'.format(name),
            info=archive_info
        )
    except Exception as exc:
        raise CommandExecutionError(exc.__str__(), info=archive_info)
    else:
        ret = False

    if clean:
        try:
            os.remove(cached)
            log.debug('Cleaned cached archive %s', cached)
        except OSError as exc:
            if exc.errno != errno.ENOENT:
                log.warning(
                    'Failed to clean cached archive %s: %s',
                    cached, exc.__str__()
                )
    return ret


@salt.utils.decorators.which('rar')
def rar(rarfile, sources, template=None, cwd=None, runas=None):
    '''
    Uses `rar for Linux`_ to create rar files

    .. _`rar for Linux`: http://www.rarlab.com/

    rarfile
        Path of rar file to be created

    sources
        Comma-separated list of sources to include in the rar file. Sources can
        also be passed in a Python list.

    cwd : None
        Run the rar command from the specified directory. Use this argument
        along with relative file paths to create rar files which do not
        contain the leading directories. If not specified, this will default
        to the home directory of the user under which the salt minion process
        is running.

        .. versionadded:: 2014.7.1

    template : None
        Can be set to 'jinja' or another supported template engine to render
        the command arguments before execution:

        .. code-block:: bash

            salt '*' archive.rar template=jinja /tmp/rarfile.rar '/tmp/sourcefile1,/tmp/{{grains.id}}.txt'

    CLI Example:

    .. code-block:: bash

        salt '*' archive.rar /tmp/rarfile.rar /tmp/sourcefile1,/tmp/sourcefile2
    '''
    if isinstance(sources, string_types):
        sources = [s.strip() for s in sources.split(',')]
    cmd = ['rar', 'a', '-idp', '{0}'.format(rarfile)]
    cmd.extend(sources)
    return __salt__['cmd.run'](cmd,
                               cwd=cwd,
                               template=template,
                               runas=runas,
                               python_shell=False).splitlines()


@salt.utils.decorators.which_bin(('unrar', 'rar'))
def unrar(rarfile, dest, excludes=None, template=None, runas=None, trim_output=False):
    '''
    Uses `rar for Linux`_ to unpack rar files

    .. _`rar for Linux`: http://www.rarlab.com/

    rarfile
        Name of rar file to be unpacked

    dest
        The destination directory into which to **unpack** the rar file

    template : None
        Can be set to 'jinja' or another supported template engine to render
        the command arguments before execution:

        .. code-block:: bash

            salt '*' archive.unrar template=jinja /tmp/rarfile.rar /tmp/{{grains.id}}/ excludes=file_1,file_2

    trim_output : False
        The number of files we should output on success before the rest are trimmed, if this is
        set to True then it will default to 100

    CLI Example:

    .. code-block:: bash

        salt '*' archive.unrar /tmp/rarfile.rar /home/strongbad/ excludes=file_1,file_2

    '''
    if isinstance(excludes, string_types):
        excludes = [entry.strip() for entry in excludes.split(',')]

    cmd = [salt.utils.which_bin(('unrar', 'rar')),
           'x', '-idp', '{0}'.format(rarfile)]
    if excludes is not None:
        for exclude in excludes:
            cmd.extend(['-x', '{0}'.format(exclude)])
    cmd.append('{0}'.format(dest))
    files = __salt__['cmd.run'](cmd,
                               template=template,
                               runas=runas,
                               python_shell=False).splitlines()

    return _trim_files(files, trim_output)


def _render_filenames(filenames, zip_file, saltenv, template):
    '''
    Process markup in the :param:`filenames` and :param:`zipfile` variables (NOT the
    files under the paths they ultimately point to) according to the markup
    format provided by :param:`template`.
    '''
    if not template:
        return (filenames, zip_file)

    # render the path as a template using path_template_engine as the engine
    if template not in salt.utils.templates.TEMPLATE_REGISTRY:
        raise CommandExecutionError(
            'Attempted to render file paths with unavailable engine '
            '{0}'.format(template)
        )

    kwargs = {}
    kwargs['salt'] = __salt__
    kwargs['pillar'] = __pillar__
    kwargs['grains'] = __grains__
    kwargs['opts'] = __opts__
    kwargs['saltenv'] = saltenv

    def _render(contents):
        '''
        Render :param:`contents` into a literal pathname by writing it to a
        temp file, rendering that file, and returning the result.
        '''
        # write out path to temp file
        tmp_path_fn = salt.utils.mkstemp()
        with salt.utils.fopen(tmp_path_fn, 'w+') as fp_:
            fp_.write(contents)
        data = salt.utils.templates.TEMPLATE_REGISTRY[template](
            tmp_path_fn,
            to_str=True,
            **kwargs
        )
        salt.utils.safe_rm(tmp_path_fn)
        if not data['result']:
            # Failed to render the template
            raise CommandExecutionError(
                'Failed to render file path with error: {0}'.format(
                    data['data']
                )
            )
        else:
            return data['data']

    filenames = _render(filenames)
    zip_file = _render(zip_file)
    return (filenames, zip_file)


def _trim_files(files, trim_output):
    # Trim the file list for output
    count = 100
    if not isinstance(trim_output, bool):
        count = trim_output

    if not(isinstance(trim_output, bool) and trim_output is False) and len(files) > count:
        files = files[:count]
        files.append("List trimmed after {0} files.".format(count))

    return files
