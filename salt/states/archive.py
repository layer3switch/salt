# -*- coding: utf-8 -*-
'''
Extract an archive

.. versionadded:: 2014.1.0
'''

# Import Python libs
from __future__ import absolute_import
import errno
import logging
import os
import re
import shlex
import stat
import tarfile
from contextlib import closing

# Import 3rd-party libs
import salt.ext.six as six
from salt.ext.six.moves import shlex_quote as _cmd_quote
from salt.ext.six.moves.urllib.parse import urlparse as _urlparse  # pylint: disable=no-name-in-module

# Import salt libs
import salt.utils
import salt.utils.files
from salt.exceptions import CommandExecutionError

log = logging.getLogger(__name__)

__virtualname__ = 'archive'


def __virtual__():
    '''
    Only load if the archive module is available in __salt__
    '''
    if 'archive.unzip' in __salt__ and 'archive.unrar' in __salt__:
        return __virtualname__
    else:
        return False


def _path_is_abs(path):
    '''
    Return a bool telling whether or ``path`` is absolute. If ``path`` is None,
    return ``True``. This function is designed to validate variables which
    optionally contain a file path.
    '''
    if path is None:
        return True
    try:
        return os.path.isabs(path)
    except AttributeError:
        # Non-string data passed
        return False


def _update_checksum(cached_source, source_sum):
    cached_source_sum = '.'.join((cached_source, 'hash'))
    hash_type = source_sum.get('hash_type')
    hsum = source_sum.get('hsum')
    if hash_type and hsum:
        lines = []
        try:
            try:
                with salt.utils.fopen(cached_source_sum, 'r') as fp_:
                    for line in fp_:
                        try:
                            lines.append(line.rstrip('\n').split(':', 1))
                        except ValueError:
                            continue
            except (IOError, OSError) as exc:
                if exc.errno != errno.ENOENT:
                    raise

            with salt.utils.fopen(cached_source_sum, 'w') as fp_:
                for line in lines:
                    if line[0] == hash_type:
                        line[1] = hsum
                    fp_.write('{0}:{1}\n'.format(*line))
                if hash_type not in [x[0] for x in lines]:
                    fp_.write('{0}:{1}\n'.format(hash_type, hsum))
        except (IOError, OSError) as exc:
            log.warning(
                'Failed to update checksum for %s: %s',
                cached_source, exc.__str__()
            )


def _compare_checksum(cached_source, source_sum):
    cached_source_sum = '.'.join((cached_source, 'hash'))
    try:
        with salt.utils.fopen(cached_source_sum, 'r') as fp_:
            for line in fp_:
                # Should only be one line in this file but just in case it
                # isn't, read only a single line to avoid overuse of memory.
                hash_type, hsum = line.rstrip('\n').split(':', 1)
                if hash_type == source_sum.get('hash_type'):
                    break
            else:
                return False
    except (IOError, OSError, ValueError):
        return False
    return {'hash_type': hash_type, 'hsum': hsum} == source_sum


def _is_bsdtar():
    return 'bsdtar' in __salt__['cmd.run'](['tar', '--version'],
                                           python_shell=False)


def _cleanup_destdir(name):
    '''
    Attempt to remove the specified directory
    '''
    try:
        os.rmdir(name)
    except OSError:
        pass


def extracted(name,
              source,
              source_hash=None,
              source_hash_update=False,
              skip_verify=False,
              password=None,
              options=None,
              list_options=None,
              force=False,
              user=None,
              group=None,
              if_missing=None,
              keep=False,
              trim_output=False,
              use_cmd_unzip=None,
              extract_perms=True,
              enforce_toplevel=True,
              enforce_ownership_on=None,
              archive_format=None,
              **kwargs):
    '''
    .. versionadded:: 2014.1.0
    .. versionchanged:: 2016.11.0
        This state has been rewritten. Some arguments are new to this release
        and will not be available in the 2016.3 release cycle (and earlier).
        Additionally, the **ZIP Archive Handling** section below applies
        specifically to the 2016.11.0 release (and newer).

    Ensure that an archive is extracted to a specific directory.

    .. important::
        **ZIP Archive Handling**

        Salt has two different functions for extracting ZIP archives:

        1. :py:func:`archive.unzip <salt.modules.archive.unzip>`, which uses
           Python's zipfile_ module to extract ZIP files.
        2. :py:func:`archive.cmd_unzip <salt.modules.archive.cmd_unzip>`, which
           uses the ``unzip`` CLI command to extract ZIP files.

        Salt will prefer the use of :py:func:`archive.cmd_unzip
        <salt.modules.archive.cmd_unzip>` when CLI options are specified (via
        the ``options`` argument), and will otherwise prefer the
        :py:func:`archive.unzip <salt.modules.archive.unzip>` function. Use
        of :py:func:`archive.cmd_unzip <salt.modules.archive.cmd_unzip>` can be
        forced however by setting the ``use_cmd_unzip`` argument to ``True``.
        By contrast, setting this argument to ``False`` will force usage of
        :py:func:`archive.unzip <salt.modules.archive.unzip>`. For example:

        .. code-block:: yaml

            /var/www:
              archive.extracted:
                - source: salt://foo/bar/myapp.zip
                - use_cmd_unzip: True

        When ``use_cmd_unzip`` is omitted, Salt will choose which extraction
        function to use based on the source archive and the arguments passed to
        the state. When in doubt, simply do not set this argument; it is
        provided as a means of overriding the logic Salt uses to decide which
        function to use.

        There are differences in the features available in both extraction
        functions. These are detailed below.

        - *Command-line options* (only supported by :py:func:`archive.cmd_unzip
          <salt.modules.archive.cmd_unzip>`) - When the ``options`` argument is
          used, :py:func:`archive.cmd_unzip <salt.modules.archive.cmd_unzip>`
          is the only function that can be used to extract the archive.
          Therefore, if ``use_cmd_unzip`` is specified and set to ``False``,
          and ``options`` is also set, the state will not proceed.

        - *Password-protected ZIP Archives* (only supported by
          :py:func:`archive.unzip <salt.modules.archive.unzip>`) -
          :py:func:`archive.cmd_unzip <salt.modules.archive.cmd_unzip>` is not
          be permitted to extract password-protected ZIP archives, as
          attempting to do so will cause the unzip command to block on user
          input. The :py:func:`archive.is_encrypted
          <salt.modules.archive.unzip>` function will be used to determine if
          the archive is password-protected. If it is, then the ``password``
          argument will be required for the state to proceed. If
          ``use_cmd_unzip`` is specified and set to ``True``, then the state
          will not proceed.

        - *Permissions* - Due to an `upstream bug in Python`_, permissions are
          not preserved when the zipfile_ module is used to extract an archive.
          As of the 2016.11.0 release, :py:func:`archive.unzip
          <salt.modules.archive.unzip>` (as well as this state) has an
          ``extract_perms`` argument which, when set to ``True`` (the default),
          will attempt to match the permissions of the extracted
          files/directories to those defined within the archive. To disable
          this functionality and have the state not attempt to preserve the
          permissions from the ZIP archive, set ``extract_perms`` to ``False``:

          .. code-block:: yaml

              /var/www:
                archive.extracted:
                  - source: salt://foo/bar/myapp.zip
                  - extract_perms: False

    .. _`upstream bug in Python`: https://bugs.python.org/issue15795

    name
        Directory into which the archive should be extracted

    source
        Archive to be extracted

        .. note::
            This argument uses the same syntax as its counterpart in the
            :py:func:`file.managed <salt.states.file.managed>` state.

    source_hash
        Hash of source file, or file with list of hash-to-file mappings

        .. note::
            This argument uses the same syntax as its counterpart in the
            :py:func:`file.managed <salt.states.file.managed>` state.

    source_hash_update
        Set this to ``True`` if archive should be extracted if source_hash has
        changed. This would extract regardless of the ``if_missing`` parameter.

        .. versionadded:: 2016.3.0

    skip_verify : False
        If ``True``, hash verification of remote file sources (``http://``,
        ``https://``, ``ftp://``) will be skipped, and the ``source_hash``
        argument will be ignored.

        .. versionadded:: 2016.3.4

    password
        **For ZIP archives only.** Password used for extraction.

        .. versionadded:: 2016.3.0

    options
        **For tar and zip archives only.**  This option can be used to specify
        a string of additional arguments to pass to the tar/zip command.

        If this argument is not used, then the minion will attempt to use
        Python's native tarfile_/zipfile_ support to extract it. For zip
        archives, this argument is mostly used to overwrite exsiting files with
        ``o``.

        Using this argument means that the ``tar`` or ``unzip`` command will be
        used, which is less platform-independent, so keep this in mind when
        using this option; the CLI options must be valid options for the
        ``tar``/``unzip`` implementation on the minion's OS.

        .. versionadded:: 2016.11.0
            The ``tar_options`` and ``zip_options`` parameters have been
            deprecated in favor of a single argument name.
        .. versionchanged:: 2015.8.11,2016.3.2
            XZ-compressed tar archives no longer require ``J`` to manually be
            set in the ``options``, they are now detected automatically and
            decompressed using xz-utils_ and extracted using ``tar xvf``. This
            is a more platform-independent solution, as not all tar
            implementations support the ``J`` argument for extracting archives.

        .. note::
            For tar archives, main operators like ``-x``, ``--extract``,
            ``--get``, ``-c`` and ``-f``/``--file`` should *not* be used here.

    tar_options
        .. deprecated:: 2016.11.0
            Use ``options`` instead.

    zip_options
        .. versionadded:: 2016.3.1
        .. deprecated:: 2016.11.0
            Use ``options`` instead.

    list_options
        **For tar archives only.** This state uses :py:func:`archive.list
        <salt.modules.archive.list_>` to discover the contents of the source
        archive so that it knows which file paths should exist on the minion if
        the archive has already been extracted. For the vast majority of tar
        archives, :py:func:`archive.list <salt.modules.archive.list_>` "just
        works". Archives compressed using gzip, bzip2, and xz/lzma (with the
        help of xz-utils_) are supported automatically. However, for archives
        compressed using other compression types, CLI options must be passed to
        :py:func:`archive.list <salt.modules.archive.list_>`.

        This argument will be passed through to :py:func:`archive.list
        <salt.modules.archive.list_>` as its ``options`` argument, to allow it
        to successfully list the archive's contents. For the vast majority of
        archives, this argument should not need to be used, it should only be
        needed in cases where the state fails with an error stating that the
        archive's contents could not be listed.

        .. versionadded:: 2016.11.0

    force : False
        If a path that should be occupied by a file in the extracted result is
        instead a directory (or vice-versa), the state will fail. Set this
        argument to ``True`` to force these paths to be removed in order to
        allow the archive to be extracted.

        .. warning::
            Use this option *very* carefully.

        .. versionadded:: 2016.11.0

    user
        The user to own each extracted file. Not available on Windows.

        .. versionadded:: 2015.8.0
        .. versionchanged:: 2016.3.0
            When used in combination with ``if_missing``, ownership will only
            be enforced if ``if_missing`` is a directory.
        .. versionchanged:: 2016.11.0
            Ownership will be enforced only on the file/directory paths found
            by running :py:func:`archive.list <salt.modules.archive.list_>` on
            the source archive. An alternative root directory on which to
            enforce ownership can be specified using the
            ``enforce_ownership_on`` argument.

    group
        The group to own each extracted file. Not available on Windows.

        .. versionadded:: 2015.8.0
        .. versionchanged:: 2016.3.0
            When used in combination with ``if_missing``, ownership will only
            be enforced if ``if_missing`` is a directory.
        .. versionchanged:: 2016.11.0
            Ownership will be enforced only on the file/directory paths found
            by running :py:func:`archive.list <salt.modules.archive.list_>` on
            the source archive. An alternative root directory on which to
            enforce ownership can be specified using the
            ``enforce_ownership_on`` argument.

    if_missing
        If specified, this path will be checked, and if it exists then the
        archive will not be extracted. This path can be either a directory or a
        file, so this option can also be used to check for a semaphore file and
        conditionally skip extraction.

        .. versionchanged:: 2016.3.0
            When used in combination with either ``user`` or ``group``,
            ownership will only be enforced when ``if_missing`` is a directory.
        .. versionchanged:: 2016.11.0
            Ownership enforcement is no longer tied to this argument, it is
            simply checked for existence and extraction will be skipped if
            if is present.

    keep : False
        For ``source`` archives not local to the minion (i.e. from the Salt
        fileserver or a remote source such as ``http(s)`` or ``ftp``), Salt
        will need to download the archive to the minion cache before they can
        be extracted. After extraction, these source archives will be removed
        unless this argument is set to ``True``.

    trim_output : False
        Useful for archives with many files in them. This can either be set to
        ``True`` (in which case only the first 100 files extracted will be
        in the state results), or it can be set to an integer for more exact
        control over the max number of files to include in the state results.

        .. versionadded:: 2016.3.0

    use_cmd_unzip : False
        Set to ``True`` for zip files to force usage of the
        :py:func:`archive.cmd_unzip <salt.modules.archive.cmd_unzip>` function
        to extract.

        .. versionadded:: 2016.11.0

    extract_perms : True
        **For ZIP archives only.** When using :py:func:`archive.unzip
        <salt.modules.archive.unzip>` to extract ZIP archives, Salt works
        around an `upstream bug in Python`_ to set the permissions on extracted
        files/directories to match those encoded into the ZIP archive. Set this
        argument to ``False`` to skip this workaround.

        .. versionadded:: 2016.11.0

    enforce_toplevel : True
        This option will enforce a single directory at the top level of the
        source archive, to prevent extracting a 'tar-bomb'. Set this argument
        to ``False`` to allow archives with files (or multiple directories) at
        the top level to be extracted.

        .. versionadded:: 2016.11.0

    enforce_ownership_on
        When ``user`` or ``group`` is specified, Salt will default to enforcing
        permissions on the file/directory paths detected by running
        :py:func:`archive.list <salt.modules.archive.list_>` on the source
        archive. Use this argument to specify an alternate directory on which
        ownership should be enforced.

        .. note::
            This path must be within the path specified by the ``name``
            argument.

        .. versionadded:: 2016.11.0

    archive_format
        One of ``tar``, ``zip``, or ``rar``.

        .. versionchanged:: 2016.11.0
            If omitted, the archive format will be guessed based on the value
            of the ``source`` argument.

    .. _tarfile: https://docs.python.org/2/library/tarfile.html
    .. _zipfile: https://docs.python.org/2/library/zipfile.html
    .. _xz-utils: http://tukaani.org/xz/

    **Examples**

    1. tar with lmza (i.e. xz) compression:

       .. code-block:: yaml

           graylog2-server:
             archive.extracted:
               - name: /opt/
               - source: https://github.com/downloads/Graylog2/graylog2-server/graylog2-server-0.9.6p1.tar.lzma
               - source_hash: md5=499ae16dcae71eeb7c3a30c75ea7a1a6

    2. tar archive with flag for verbose output, and enforcement of user/group
       ownership:

       .. code-block:: yaml

           graylog2-server:
             archive.extracted:
               - name: /opt/
               - source: https://github.com/downloads/Graylog2/graylog2-server/graylog2-server-0.9.6p1.tar.gz
               - source_hash: md5=499ae16dcae71eeb7c3a30c75ea7a1a6
               - tar_options: v
               - user: foo
               - group: foo

    3. tar archive, with ``source_hash_update`` set to ``True`` to prevent
       state from attempting extraction unless the ``source_hash`` differs
       from the previous time the archive was extracted:

       .. code-block:: yaml

           graylog2-server:
             archive.extracted:
               - name: /opt/
               - source: https://github.com/downloads/Graylog2/graylog2-server/graylog2-server-0.9.6p1.tar.lzma
               - source_hash: md5=499ae16dcae71eeb7c3a30c75ea7a1a6
               - source_hash_update: True
    '''
    ret = {'name': name, 'result': False, 'changes': {}, 'comment': ''}

    # Remove pub kwargs as they're irrelevant here.
    kwargs = salt.utils.clean_kwargs(**kwargs)

    if not _path_is_abs(name):
        ret['comment'] = '{0} is not an absolute path'.format(name)
        return ret
    else:
        if name is None:
            # Only way this happens is if some doofus specifies "- name: None"
            # in their SLS file. Prevent tracebacks by failing gracefully.
            ret['comment'] = 'None is not a valid directory path'
            return ret
        # os.path.isfile() returns False when there is a trailing slash, hence
        # our need for first stripping the slash and then adding it back later.
        # Otherwise, we can't properly check if the extraction location both a)
        # exists and b) is a file.
        #
        # >>> os.path.isfile('/tmp/foo.txt')
        # True
        # >>> os.path.isfile('/tmp/foo.txt/')
        # False
        name = name.rstrip('/')
        if os.path.isfile(name):
            ret['comment'] = '{0} exists and is not a directory'.format(name)
            return ret
        # Add back the slash so that file.makedirs properly creates the
        # destdir if it needs to be created. file.makedirs expects a trailing
        # slash in the directory path.
        name += '/'
    if not _path_is_abs(if_missing):
        ret['comment'] = 'Value for \'if_missing\' is not an absolute path'
        return ret
    if not _path_is_abs(enforce_ownership_on):
        ret['comment'] = ('Value for \'enforce_ownership_on\' is not an '
                          'absolute path')
        return ret
    else:
        if enforce_ownership_on is not None:
            try:
                not_rel = os.path.relpath(enforce_ownership_on,
                                          name).startswith('..' + os.sep)
            except Exception:
                # A ValueError is raised on Windows when the paths passed to
                # os.path.relpath are not on the same drive letter. Using a
                # generic Exception here to keep other possible exception types
                # from making this state blow up with a traceback.
                not_rel = True
            if not_rel:
                ret['comment'] = (
                    'Value for \'enforce_ownership_on\' must be within {0}'
                    .format(name)
                )
                return ret

    if user or group:
        if salt.utils.is_windows():
            ret['comment'] = \
                'User/group ownership cannot be enforced on Windows minions'
            return ret

        if user:
            uid = __salt__['file.user_to_uid'](user)
            if not uid:
                ret['comment'] = 'User {0} does not exist'.format(user)
                return ret
        else:
            uid = -1

        if group:
            gid = __salt__['file.group_to_gid'](group)
            if not gid:
                ret['comment'] = 'Group {0} does not exist'.format(group)
                return ret
        else:
            gid = -1
    else:
        # We should never hit the ownership enforcement code unless user or
        # group was specified, but just in case, set uid/gid to -1 to make the
        # os.chown() a no-op and avoid a NameError.
        uid = gid = -1

    if source_hash_update and not source_hash:
        ret.setdefault('warnings', []).append(
            'The \'source_hash_update\' argument is ignored when '
            '\'source_hash\' is not also specified.'
        )

    try:
        source_match = __salt__['file.source_list'](source,
                                                    source_hash,
                                                    __env__)[0]
    except CommandExecutionError as exc:
        ret['result'] = False
        ret['comment'] = exc.strerror
        return ret

    urlparsed_source = _urlparse(source_match)
    source_hash_name = urlparsed_source.path or urlparsed_source.netloc

    valid_archive_formats = ('tar', 'rar', 'zip')
    if not archive_format:
        archive_format = salt.utils.files.guess_archive_type(source_hash_name)
        if archive_format is None:
            ret['comment'] = (
                'Could not guess archive_format from the value of the '
                '\'source\' argument. Please set this archive_format to one '
                'of the following: {0}'.format(', '.join(valid_archive_formats))
            )
            return ret
    try:
        archive_format = archive_format.lower()
    except AttributeError:
        pass
    if archive_format not in valid_archive_formats:
        ret['comment'] = (
            'Invalid archive_format \'{0}\'. Either set it to a supported '
            'value ({1}) or remove this argument and the archive format will '
            'be guesseed based on file extension.'.format(
                archive_format,
                ', '.join(valid_archive_formats),
            )
        )
        return ret

    tar_options = kwargs.pop('tar_options', None)
    zip_options = kwargs.pop('zip_options', None)
    if tar_options:
        msg = ('The \'tar_options\' argument has been deprecated, please use '
               '\'options\' instead.')
        salt.utils.warn_until('Oxygen', msg)
        ret.setdefault('warnings', []).append(msg)
        options = tar_options
    elif zip_options:
        msg = ('The \'zip_options\' argument has been deprecated, please use '
               '\'options\' instead.')
        salt.utils.warn_until('Oxygen', msg)
        ret.setdefault('warnings', []).append(msg)
        options = zip_options

    if archive_format == 'zip':
        if options:
            if use_cmd_unzip is None:
                log.info(
                    'Presence of CLI options in archive.extracted state for '
                    '\'%s\' implies that use_cmd_unzip is set to True.', name
                )
                use_cmd_unzip = True
            elif not use_cmd_unzip:
                # use_cmd_unzip explicitly disabled
                ret['comment'] = (
                    '\'use_cmd_unzip\' cannot be set to False if CLI options '
                    'are being specified (via the \'options\' argument). '
                    'Either remove \'use_cmd_unzip\', or set it to True.'
                )
                return ret
        if password:
            if use_cmd_unzip is None:
                log.info(
                    'Presence of a password in archive.extracted state for '
                    '\'%s\' implies that use_cmd_unzip is set to False.', name
                )
                use_cmd_unzip = False
            elif use_cmd_unzip:
                ret.setdefault('warnings', []).append(
                    'Using a password in combination with setting '
                    '\'use_cmd_unzip\' to True is considered insecure. It is '
                    'recommended to remove the \'use_cmd_unzip\' argument (or '
                    'set it to False) and allow Salt to extract the archive '
                    'using Python\'s built-in ZIP file support.'
                )
    else:
        if password:
            ret['comment'] = \
                'The \'password\' argument is only supported for zip archives'
            return ret

    supports_options = ('tar', 'zip')
    if options and archive_format not in supports_options:
        ret['comment'] = (
            'The \'options\' argument is only compatible with the following '
            'archive formats: {0}'.format(', '.join(supports_options))
        )
        return ret

    if trim_output and not isinstance(trim_output, (bool, six.integer_types)):
        try:
            # Try to handle cases where trim_output was passed as a
            # string-ified integer.
            trim_output = int(trim_output)
        except TypeError:
            ret['comment'] = (
                'Invalid value for trim_output, must be True/False or an '
                'integer'
            )
            return ret

    cached_source = os.path.join(
        __opts__['cachedir'],
        'files',
        __env__,
        re.sub(r'[:/\\]', '_', source_hash_name),
    )

    if os.path.isdir(cached_source):
        # Prevent a traceback from attempting to read from a directory path
        salt.utils.rm_rf(cached_source)

    if source_hash:
        try:
            source_sum = __salt__['file.get_source_sum'](source_hash_name,
                                                         source_hash,
                                                         __env__)
        except CommandExecutionError as exc:
            ret['comment'] = exc.strerror
            return ret

        if source_hash_update:
            if _compare_checksum(cached_source, source_sum):
                ret['result'] = True
                ret['comment'] = \
                    'Hash {0} has not changed'.format(source_sum['hsum'])
                return ret
    else:
        source_sum = {}

    if not os.path.isfile(cached_source):
        if __opts__['test']:
            ret['result'] = None
            ret['comment'] = \
                'Archive {0} would be downloaded to cache'.format(source_match)
            return ret

        log.debug('%s is not in cache, downloading it', source_match)

        file_result = __salt__['state.single']('file.managed',
                                               cached_source,
                                               source=source_match,
                                               source_hash=source_hash,
                                               makedirs=True,
                                               skip_verify=skip_verify,
                                               saltenv=__env__,
                                               source_hash_name=source_hash_name)
        log.debug('file.managed: {0}'.format(file_result))

        # Get actual state result. The state.single return is a single-element
        # dictionary with the state's unique ID at the top level, and its value
        # being the state's return dictionary. next(iter(dict_name)) will give
        # us the value of the first key, so
        # file_result[next(iter(file_result))] will give us the results of the
        # state.single we just ran.
        try:
            file_result = file_result[next(iter(file_result))]
        except AttributeError:
            pass

        try:
            if not file_result['result']:
                log.debug('failed to download {0}'.format(source_match))
                return file_result
        except TypeError:
            if not file_result:
                log.debug('failed to download {0}'.format(source_match))
                return file_result
    else:
        log.debug('Archive %s is already in cache', source_match)

    if source_hash:
        _update_checksum(cached_source, source_sum)

    if archive_format == 'zip' and not password:
        log.debug('Checking %s to see if it is password-protected',
                  source_match)
        # Either use_cmd_unzip was explicitly set to True, or was
        # implicitly enabled by setting the "options" argument.
        try:
            encrypted_zip = __salt__['archive.is_encrypted'](
                cached_source,
                clean=False,
                saltenv=__env__)
        except CommandExecutionError:
            # This would happen if archive_format=zip and the source archive is
            # not actually a zip file.
            pass
        else:
            if encrypted_zip:
                ret['comment'] = (
                    'Archive {0} is password-protected, but no password was '
                    'specified. Please set the \'password\' argument.'.format(
                        source_match
                    )
                )
                return ret

    try:
        contents = __salt__['archive.list'](cached_source,
                                            archive_format=archive_format,
                                            options=list_options,
                                            clean=False,
                                            verbose=True)
    except CommandExecutionError as exc:
        contents = None
        errors = []
        if not if_missing:
            errors.append('\'if_missing\' must be set')
        if not enforce_ownership_on and (user or group):
            errors.append(
                'Ownership cannot be managed without setting '
                '\'enforce_ownership_on\'.'
            )
        msg = exc.strerror
        if errors:
            msg += '\n\n'
            if archive_format == 'tar':
                msg += (
                    'If the source archive is a tar archive compressed using '
                    'a compression type not natively supported by the tar '
                    'command, then setting the \'list_options\' argument may '
                    'allow the contents to be listed. Otherwise, if Salt is '
                    'unable to determine the files/directories in the '
                    'archive, the following workaround(s) would need to be '
                    'used for this state to proceed'
                )
            else:
                msg += (
                    'The following workarounds must be used for this state to '
                    'proceed'
                )
            msg += (
                ' (assuming the source file is a valid {0} archive):\n'
                .format(archive_format)
            )

            for error in errors:
                msg += '\n- {0}'.format(error)
        ret['comment'] = msg
        return ret

    if enforce_toplevel and contents is not None \
            and (len(contents['top_level_dirs']) > 1
                 or len(contents['top_level_files']) > 0):
        ret['comment'] = ('Archive does not have a single top-level directory. '
                          'To allow this archive to be extracted, set '
                          '\'enforce_toplevel\' to False. To avoid a '
                          '\'{0}-bomb\' it may also be advisable to set a '
                          'top-level directory by adding it to the \'name\' '
                          'value (for example, setting \'name\' to {1} '
                          'instead of {2}).'.format(
                              archive_format,
                              os.path.join(name, 'some_dir'),
                              name,
                          ))
        return ret

    # Check to see if we need to extract the archive. Using os.stat() in a
    # try/except is considerably faster than using os.path.exists(), and we
    # already need to catch an OSError to cover edge cases where the minion is
    # running as a non-privileged user and is trying to check for the existence
    # of a path to which it does not have permission.
    extraction_needed = False
    try:
        if_missing_path_exists = os.path.exists(if_missing)
    except TypeError:
        if_missing_path_exists = False

    if not if_missing_path_exists:
        if contents is None:
            try:
                os.stat(if_missing)
                extraction_needed = False
            except OSError as exc:
                if exc.errno == errno.ENOENT:
                    extraction_needed = True
                else:
                    ret['comment'] = (
                        'Failed to check for existence of if_missing path '
                        '({0}): {1}'.format(if_missing, exc.__str__())
                    )
                    return ret
        else:
            incorrect_type = []
            extraction_needed = False
            for path_list, func in ((contents['dirs'], stat.S_ISDIR),
                                    (contents['files'], stat.S_ISREG)):
                for path in path_list:
                    full_path = os.path.join(name, path)
                    try:
                        path_mode = os.stat(full_path).st_mode
                        if not func(path_mode):
                            incorrect_type.append(path)
                    except OSError as exc:
                        if exc.errno == errno.ENOENT:
                            extraction_needed = True
                        else:
                            ret['comment'] = exc.__str__()
                            return ret

            if incorrect_type:
                if not force:
                    msg = (
                        'The below paths (relative to {0}) exist, but are the '
                        'incorrect type (i.e. file instead of directory or '
                        'vice-versa). To proceed with extraction, set '
                        '\'force\' to True.\n'.format(name)
                    )
                    for path in incorrect_type:
                        msg += '\n- {0}'.format(path)
                    ret['comment'] = msg
                else:
                    errors = []
                    for path in incorrect_type:
                        full_path = os.path.join(name, path)
                        try:
                            salt.utils.rm_rf(full_path)
                            ret['changes'].setdefault(
                                'removed', []).append(full_path)
                        except OSError as exc:
                            if exc.errno != errno.ENOENT:
                                errors.append(exc.__str__())
                    if errors:
                        msg = (
                            'One or more paths existed by were the incorrect '
                            'type (i.e. file instead of directory or '
                            'vice-versa), but could not be removed. The '
                            'following errors were observed:\n'
                        )
                        for error in errors:
                            msg += '\n- {0}'.format(error)
                        ret['comment'] = msg
                        return ret

    created_destdir = False

    if extraction_needed:
        if __opts__['test']:
            ret['result'] = None
            ret['comment'] = \
                'Archive {0} would be extracted to {1}'.format(
                    source_match,
                    name
                )
            return ret

        if not os.path.isdir(name):
            __salt__['file.makedirs'](name, user=user)
            created_destdir = True

        log.debug('Extracting {0} to {1}'.format(cached_source, name))
        try:
            if archive_format == 'zip':
                if use_cmd_unzip:
                    files = __salt__['archive.cmd_unzip'](cached_source,
                                                          name,
                                                          options=options,
                                                          trim_output=trim_output,
                                                          password=password,
                                                          **kwargs)
                else:
                    files = __salt__['archive.unzip'](cached_source,
                                                      name,
                                                      options=options,
                                                      trim_output=trim_output,
                                                      password=password,
                                                      **kwargs)
            elif archive_format == 'rar':
                files = __salt__['archive.unrar'](cached_source,
                                                  name,
                                                  trim_output=trim_output,
                                                  **kwargs)
            else:
                if options is None:
                    try:
                        with closing(tarfile.open(cached_source, 'r')) as tar:
                            tar.extractall(name)
                            files = tar.getnames()
                    except tarfile.ReadError:
                        if salt.utils.which('xz'):
                            if __salt__['cmd.retcode'](
                                    ['xz', '-l', cached_source],
                                    python_shell=False,
                                    ignore_retcode=True) == 0:
                                # XZ-compressed data
                                log.debug(
                                    'Tar file is XZ-compressed, attempting '
                                    'decompression and extraction using xz-utils '
                                    'and the tar command'
                                )
                                # Must use python_shell=True here because not
                                # all tar implementations support the -J flag
                                # for decompressing XZ-compressed data. We need
                                # to dump the decompressed data to stdout and
                                # pipe it to tar for extraction.
                                cmd = 'xz --decompress --stdout {0} | tar xvf -'
                                results = __salt__['cmd.run_all'](
                                    cmd.format(_cmd_quote(cached_source)),
                                    cwd=name,
                                    python_shell=True)
                                if results['retcode'] != 0:
                                    if created_destdir:
                                        _cleanup_destdir(name)
                                    ret['result'] = False
                                    ret['changes'] = results
                                    return ret
                                if _is_bsdtar():
                                    files = results['stderr']
                                else:
                                    files = results['stdout']
                            else:
                                # Failed to open tar archive and it is not
                                # XZ-compressed, gracefully fail the state
                                if created_destdir:
                                    _cleanup_destdir(name)
                                ret['result'] = False
                                ret['comment'] = (
                                    'Failed to read from tar archive using '
                                    'Python\'s native tar file support. If '
                                    'archive is compressed using something '
                                    'other than gzip or bzip2, the '
                                    '\'options\' argument may be required to '
                                    'pass the correct options to the tar '
                                    'command in order to extract the archive.'
                                )
                                return ret
                        else:
                            if created_destdir:
                                _cleanup_destdir(name)
                            ret['result'] = False
                            ret['comment'] = (
                                'Failed to read from tar archive. If it is '
                                'XZ-compressed, install xz-utils to attempt '
                                'extraction.'
                            )
                            return ret
                else:
                    try:
                        tar_opts = shlex.split(options)
                    except AttributeError:
                        tar_opts = shlex.split(str(options))

                    tar_cmd = ['tar']
                    tar_shortopts = 'x'
                    tar_longopts = []

                    for position, opt in enumerate(tar_opts):
                        if opt.startswith('-'):
                            tar_longopts.append(opt)
                        else:
                            if position > 0:
                                tar_longopts.append(opt)
                            else:
                                append_opt = opt
                                append_opt = append_opt.replace('x', '')
                                append_opt = append_opt.replace('f', '')
                                tar_shortopts = tar_shortopts + append_opt

                    if __grains__['os'].lower() == 'openbsd':
                        tar_shortopts = '-' + tar_shortopts

                    tar_cmd.append(tar_shortopts)
                    tar_cmd.extend(tar_longopts)
                    tar_cmd.extend(['-f', cached_source])

                    results = __salt__['cmd.run_all'](tar_cmd,
                                                      cwd=name,
                                                      python_shell=False)
                    if results['retcode'] != 0:
                        ret['result'] = False
                        ret['changes'] = results
                        return ret
                    if _is_bsdtar():
                        files = results['stderr']
                    else:
                        files = results['stdout']
                    if not files:
                        files = 'no tar output so far'
        except CommandExecutionError as exc:
            ret['comment'] = exc.strerror
            return ret

    # Recursively set user and group ownership of files
    enforce_missing = []
    enforce_failed = []
    if user or group:
        if enforce_ownership_on:
            enforce_dirs = [enforce_ownership_on]
            enforce_files = []
        else:
            if contents is not None:
                enforce_dirs = contents['top_level_dirs']
                enforce_files = contents['top_level_files']

        recurse = []
        if user:
            recurse.append('user')
        if group:
            recurse.append('group')
        recurse_str = ', '.join(recurse)

        owner_changes = dict([
            (x, y) for x, y in (('user', user), ('group', group)) if y
        ])
        for dirname in enforce_dirs:
            full_path = os.path.join(name, dirname)
            if not os.path.isdir(full_path):
                if not __opts__['test']:
                    enforce_missing.append(full_path)
            else:
                log.debug(
                    'Enforcing %s ownership on %s using a file.directory state%s',
                    recurse_str,
                    dirname,
                    ' (dry-run only)' if __opts__['test'] else ''
                )
                dir_result = __salt__['state.single']('file.directory',
                                                      full_path,
                                                      user=user,
                                                      group=group,
                                                      recurse=recurse,
                                                      test=__opts__['test'])
                try:
                    dir_result = dir_result[next(iter(dir_result))]
                except AttributeError:
                    pass
                log.debug('file.directory: %s', dir_result)

                if __opts__['test']:
                    if dir_result.get('pchanges'):
                        ret['changes']['updated ownership'] = True
                else:
                    try:
                        if dir_result['result']:
                            if dir_result['changes']:
                                ret['changes']['updated ownership'] = True
                        else:
                            enforce_failed.append(full_path)
                    except (KeyError, TypeError):
                        log.warning(
                            'Bad state return %s for file.directory state on %s',
                            dir_result, dirname
                        )

        for filename in enforce_files:
            full_path = os.path.join(name, filename)
            try:
                # Using os.stat instead of calling out to
                # __salt__['file.stats'], since we may be doing this for a lot
                # of files, and simply calling os.stat directly will speed
                # things up a bit.
                file_stat = os.stat(full_path)
            except OSError as exc:
                if not __opts__['test']:
                    if exc.errno == errno.ENOENT:
                        enforce_missing.append(full_path)
                    enforce_failed.append(full_path)
            else:
                # Earlier we set uid, gid to -1 if we're not enforcing
                # ownership on user, group, as passing -1 to os.chown will tell
                # it not to change that ownership. Since we've done that, we
                # can selectively compare the uid/gid from the values in
                # file_stat, _only if_ the "desired" uid/gid is something other
                # than -1.
                if (uid != -1 and uid != file_stat.st_uid) \
                        or (gid != -1 and gid != file_stat.st_gid):
                    if __opts__['test']:
                        ret['changes']['updated ownership'] = True
                    else:
                        try:
                            os.chown(full_path, uid, gid)
                            ret['changes']['updated ownership'] = True
                        except OSError:
                            enforce_failed.append(filename)

    if extraction_needed:
        if len(files) > 0:
            if created_destdir:
                ret['changes']['directories_created'] = [name]
            ret['changes']['extracted_files'] = files
            ret['comment'] = '{0} extracted to {1}'.format(source_match, name)
            if not keep:
                log.debug('Cleaning cached source file %s', cached_source)
                try:
                    os.remove(cached_source)
                except OSError as exc:
                    if exc.errno != errno.ENOENT:
                        log.error(
                            'Failed to clean cached source file %s: %s',
                            cached_source, exc.__str__()
                        )
            ret['result'] = True

        else:
            ret['result'] = False
            ret['comment'] = 'Can\'t extract content of {0}'.format(source_match)

    else:
        ret['result'] = True
        if if_missing_path_exists:
            ret['comment'] = '{0} exists'.format(if_missing)
        else:
            ret['comment'] = 'All files in archive are already present'
        if __opts__['test']:
            if ret['changes'].get('updated ownership'):
                ret['result'] = None
                ret['comment'] += (
                    '. Ownership would be updated on one or more '
                    'files/directories.'
                )

    if enforce_missing:
        if not if_missing:
            # If is_missing was used, and both a) the archive had never been
            # extracted, and b) the path referred to by if_missing exists, then
            # enforce_missing would contain paths of top_levle dirs/files that
            # _would_ have been extracted. Since if_missing can be used as a
            # semaphore to conditionally extract, we don't want to make this a
            # case where the state fails, so we only fail the state if
            # is_missing is not used.
            ret['result'] = False
        ret['comment'] += (
            '\n\nWhile trying to enforce user/group ownership, the following '
            'paths were missing:\n'
        )
        for item in enforce_missing:
            ret['comment'] += '\n- {0}'.format(item)

    if enforce_failed:
        ret['result'] = False
        ret['comment'] += (
            '\n\nWhile trying to enforce user/group ownership, Salt was '
            'unable to change ownership on the following paths:\n'
        )
        for item in enforce_failed:
            ret['comment'] += '\n- {0}'.format(item)

    return ret
