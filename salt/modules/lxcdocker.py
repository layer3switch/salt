#!/usr/bin/env python
# -*- coding: utf-8 -*-
'''
Managment of dockers: overview of this module
=============================================


General notes
------------------
- As we use states, we dont want to pop contineously dockers, we will map each
container id  (or image) with a grain whenever it is relevant.
- As a corollary, we will resolve for a container id eitheir directly this
container id or try to find a container id matching something stocked in grain

installation prerequsuites
------------------------------
- You will need the 'docker-py' python package in your python installation
  running salt.
- For now, you need this fork: https://github.com/kiorky/docker-py

Prerequisite pillar configuration for authentication
----------------------------------------------------

- To push or pull you will need to be authenticated as the docker-py bindings
  require it
- For this to happen, you will need to configure a mapping in the pillar
representing your per URL authentication bits::

    docker-registries:
        registry_url:
            email: foo@foo.com
            password: s3cr3t
            username: foo

- You need at least an entry to the default docker index::

    docker-registries:
        https://index.docker.io/v1:
            email: foo@foo.com
            password: s3cr3t
            username: foo

you can define multiple registries blocks for them to be aggregated, their id
just must finish with -docker-registries::

   ac-docker-registries:
        https://index.bar.io/v1:
            email: foo@foo.com
            password: s3cr3t
            username: foo

   ab-docker-registries:
        https://index.foo.io/v1:
            email: foo@foo.com
            password: s3cr3t
            username: foo

Would be the equivalent to::

   docker-registries:
        https://index.bar.io/v1:
            email: foo@foo.com
            password: s3cr3t
            username: foo
        https://index.foo.io/v1:
            email: foo@foo.com
            password: s3cr3t
            username: foo

Registry dialog methods
-----------------------
    - login
    - push
    - pull

Docker managment
----------------
    - version
    - info

You have those methods:
Image managment
----------------
You have those methods:

    - search
    - inspect_image
    - get_images
    - remove_image
    - import_image
    - build
    - tag

container managment
-------------------
You have those methods:

    - start
    - stop
    - kill
    - wait
    - get_containers
    - inspect_container
    - remove_container
    - is_running
    - top
    - ports
    - logs
    - diff
    - commit
    - create_container
    - export

Runtime execution within a specific container
----------------------------------------------
You have those methods:

    TODO:
    - retcode
    - run

Internal
--------

    - get_image_infos
    - get_container_infos
    - sizeof_fmt

'''
__docformat__ = 'restructuredtext en'

import datetime
import json
import os
import traceback

from salt.exceptions import CommandExecutionError

try:
    import docker
    HAS_DOCKER = True
except ImportError:
    HAS_DOCKER = False

import logging

try:
    from collections import OrderedDict
except:
    from ordereddict import OrderedDict

salt_log = logging.getLogger(__name__)

INVALID_RESPONSE = 'We did not get any expectable answer from docker'
VALID_RESPONSE = ''
NOTSET = object()
base_status = {
    'status': None,
    'id': None,
    'comment': '',
    'out': None
}


def __virtual__():
    if HAS_DOCKER:
        return 'docker'


def sizeof_fmt(num):
    for x in ['bytes', 'KB', 'MB', 'GB', 'TB', 'PB']:
        if num < 1024.0:
            return "%3.1f %s" % (num, x)
        num /= 1024.0


def set_status(m, id=NOTSET, comment=INVALID_RESPONSE, status=False, out=None):
    m['comment'] = comment
    m['status'] = status
    m['out'] = out
    if id is not NOTSET:
        m['id'] = id
    return m


def invalid(m, id=NOTSET, comment=INVALID_RESPONSE, out=None):
    return set_status(m, status=False, id=id, comment=comment, out=out)


def valid(m, id=NOTSET, comment=VALID_RESPONSE, out=None):
    return set_status(m, status=True, id=id, comment=comment, out=out)


def get_client(version=None):
    '''
    Get a connection to a docker API (socket or URL)
    based on config.get mechanism (pillar -> grains)

    By default it will use the base docker-py defaults which
    at the time of writing are using the local socket and
    the 1.4 API

    Set those keys in your configuration tree somehow:

        - docker.url: URL to the docker service
        - docker.version: API version to use

    '''
    kwargs = {}
    get = __salt__['config.get']
    for k, p in {
        'base_url': 'docker.url',
        'version': 'docker.version',
    }.items():
        param = get(p, NOTSET)
        if param is not NOTSET:
            kwargs[k] = param
    client = docker.Client(**kwargs)
    # force 1..5 API for registry login
    if not version:
        if client._version == "1.4":
            client._version = "1.5"
    if getattr(client, '_cfg', None) is None:
        client._cfg = {
            'Configs': {},
            'rootPath': '/dev/null'
        }
    client._cfg.update(merge_auth_bits())
    return client


def merge_auth_bits():
    '''
    Merge the local docker authentication file
    with the pillar configuration
    '''
    cfg = os.path.expanduser('~/.dockercfg')
    try:
        fic = open(cfg)
        try:
            config = json.loads(fic.read())
        finally:
            fic.close()
    except Exception:
        config = {'rootPath': '/dev/null'}
    if not 'Configs' in config:
        config['Configs'] = {}
    config['Configs'].update(
        __pillar__.get('docker-registries', {})
    )
    for k, data in __pillar__.items():
        if k.endswith('-docker-registries'):
            config['Configs'].update(data)
    return config


def get_containers(all=True, trunc=False, since=None, before=None, limit=-1):
    '''
    Get a list of mappings representing all containers

    all
        Return all containers

    trunc
        Set it to True to have the short ID

    Returns a mapping of something which look's like
    container
    '''
    client = get_client()
    status = base_status.copy()
    ret = client.containers(all=all,
                            trunc=trunc,
                            since=since,
                            before=before,
                            limit=limit)
    if ret:
        valid(status, comment='All containers in out', out=ret)
    else:
        invalid(status)
    return status


def get_image_infos(image):
    '''
    Verify that the image exists
    We will try to resolve either by:
        - the mapping grain->docker id or directly
        - dockerid

    image
        Image Id / grain name

    Returns the image id
    '''
    status = base_status.copy()
    client = get_client()
    try:
        infos = client.inspect_image(image)
        if infos:
            valid(
                status,
                id=infos['id'],
                out=infos,
                comment='found')
    except Exception:
        pass
    if not status['id']:
        invalid(status)
        raise CommandExecutionError(
            'ImageID "%s" could not be resolved to '
            'an existing Image' % (image)
        )
    return status['out']


def get_container_infos(container):
    '''
    Get container infos
    We will try to resolve either by:
        - the mapping grain->docker id or directly
        - dockerid

    container
        Image Id / grain name
    '''
    status = base_status.copy()
    client = get_client()
    try:
        info = client.inspect_container(container)
        if info:
            valid(status,
                  id=info['ID'],
                  out=info)
    except Exception:
        pass
    if not status['id']:
        raise CommandExecutionError(
            'Container_id {0} could not be resolved to '
            'an existing container'.format(
                container)
        )
    if (
        (not 'id' in status['out'])
        and ('ID' in status['out'])
    ):
        status['out']['id'] = status['out']['ID']
    return status['out']


def logs(container):
    '''
    Get container logs
    container
        container id
    '''
    status = base_status.copy()
    client = get_client()
    try:
        info = client.logs(get_container_infos(container)['id'])
        valid(status, id=container, out=info)
    except Exception:
        invalid(status, id=container, out=traceback.format_exc())
    return status


def commit(container, repository=None, tag=None, message=None,
           author=None, conf=None):
    '''
    Commit a container (promotes it to an image)
    container
        container id
    repository
        repository/imageName to commit to
    tag
        optionnal tag
    message
        optionnal commit message
    author
        optionnal author
    conf
        optionnal conf

    '''
    status = base_status.copy()
    client = get_client()
    try:
        container = get_container_infos(container)['id']
        info = client.commit(
            container,
            repository=repository,
            tag=tag,
            message=message,
            author=author,
            conf=conf)
        found = False
        for k in 'Id', 'id', 'ID':
            if k in info:
                found = True
                id = info[k]
        if not found:
            raise Exception('Invalid commit return')
        image = get_image_infos(id)['id']
        comment = 'Image {0} created from {1}'.format(image, container)
        valid(status, id=image, out=info, comment=comment)
    except Exception:
        invalid(status, id=container, out=traceback.format_exc())
    return status


def diff(container):
    '''
    Get container diffs
    container
        container id
    '''
    status = base_status.copy()
    client = get_client()
    try:
        info = client.diff(get_container_infos(container)['id'])
        valid(status, id=container, out=info)
    except Exception:
        invalid(status, id=container, out=traceback.format_exc())
    return status


def export(container, path):
    '''
    Export a container to a file
    container
        container id
    path
        path to the export
    '''

    try:
        ppath = os.path.abspath(path)
        fic = open(ppath, 'w')
        status = base_status.copy()
        client = get_client()
        response = client.export(get_container_infos(container)['id'])
        try:
            byte = response.read(4096)
            fic.write(byte)
            while byte != "":
                # Do stuff with byte.
                byte = response.read(4096)
                fic.write(byte)
        finally:
            fic.flush()
            fic.close()
        valid(status,
              id=container, out=ppath,
              comment='Exported to {0}'.format(ppath))
    except Exception:
        invalid(status, id=container, out=traceback.format_exc())
    return status


def create_container(image,
                     command='/sbin/init',
                     hostname=None,
                     user=None,
                     detach=True,
                     stdin_open=False,
                     tty=False,
                     mem_limit=0,
                     ports=None,
                     environment=None,
                     dns=None,
                     volumes=None,
                     volumes_from=None):
    '''
     Get container diffs
    image
        image to create the container from
    command
        command to execute while starting
    hostname
        hostname of the container
    user
        user to run docker as
    detach
        daemon mode
    environment
        environment variable mapping ({'foo':'BAR'})
    dns
        list of dns servers
    ports
        ports redirections (['222:22'])
    volumes
        list of volumes mapping::

            (['/mountpoint/in/container:/guest/foo',
              '/same/path/mounted/point'])

    tty
        attach ttys
    stdin_open
        let stdin open
    volumes_from
        container to get volumes definition from

    EG:

        salt-call lxcdocker.create_container o/ubuntu volumes="['/s','/m:/f']"


    '''
    status = base_status.copy()
    client = get_client()
    try:
        mountpoints = {}
        binds = {}
        # create empty mountpoints for them to be
        # editable
        # either we have a list of guest or host:guest
        if isinstance(volumes, list):
            for mountpoint in volumes:
                mounted = mountpoint
                if ':' in mountpoint:
                    parts = mountpoint.split(':')
                    mountpoint = parts[1]
                    mounted = parts[0]
                mountpoints[mountpoint] = {}
                binds[mounted] = mountpoint
        info = client.create_container(
            image=image,
            command=command,
            hostname=hostname,
            user=user,
            detach=detach,
            stdin_open=stdin_open,
            tty=tty,
            mem_limit=mem_limit,
            ports=ports,
            environment=environment,
            dns=dns,
            volumes=mountpoints,
            volumes_from=volumes_from,
        )
        container = info['Id']
        kill(container)
        start(container, binds=binds)
        valid(status,
              id=container,
              comment='Container created',
              out={
                  'info': get_container_infos(container),
                  'out': info
              })
    except Exception:
        invalid(status, id=image, out=traceback.format_exc())
    return status


def version():
    '''
    Get docker version

    .. code-block:: bash

        salt '*' docker.version
    '''
    status = base_status.copy()
    client = get_client()
    try:
        info = client.version()
        valid(status, out=info)
    except Exception:
        invalid(status, out=traceback.format_exc())
    return status


def info():
    '''
    Get the version information about docker

    :rtype: dict
    :returns: A status message with the command output

    .. code-block:: bash

        salt '*' docker.info

    '''
    status = base_status.copy()
    client = get_client()
    try:
        info = client.info()
        valid(status, out=info)
    except Exception:
        invalid(status, out=traceback.format_exc())
    return status


def port(container, private_port):
    '''
    Private/Public for a specific port mapping allocation information
    This method is broken on docker-py side
    Just use the result of inspect to mangle port
    allocation
    container
        container id
    private_port
        private port on the container to query for

    '''
    status = base_status.copy()
    client = get_client()
    try:
        info = client.port(
            get_container_infos(container)['id'],
            port)
        valid(status, id=container, out=info)
    except Exception:
        invalid(status, id=container, out=traceback.format_exc())
    return status


def stop(container, timeout=10):
    '''
    Stop a running container

    :type container: string
    :param container: The container id to stop

    :type timout: int
    :param timeout: Wait for a timeout to let the container exit gracefully
        before killing it

    :rtype: dict
    :returns: A status message with the command output
          ex:
            {'id': 'abcdef123456789',
           'status': True}

    '''
    client = get_client()
    status = base_status.copy()
    try:
        dcontainer = get_container_infos(container)['id']
        if is_running(dcontainer):
            client.stop(dcontainer, timeout=timeout)
            if not is_running(dcontainer):
                valid(
                    status,
                    comment='Container {0} was stopped'.format(
                        container),
                    id=container)
            else:
                invalid(status)
        else:
            valid(
                status,
                comment='Container {0} was already stopped'.format(
                    container),
                id=container)
    except Exception:
        invalid(status, id=container, out=traceback.format_exc(),
                comment=(
                    'An exception occured while stopping '
                    'your container {0}').format(container))
    return status


def kill(container):
    '''
    Kill a running container

    :type container: string
    :param container: The container id to kill

    :rtype: dict
    :returns: A status message with the command output
          ex:
            {'id': 'abcdef123456789',
           'status': True}

    '''
    client = get_client()
    status = base_status.copy()
    try:
        dcontainer = get_container_infos(container)['id']
        if is_running(dcontainer):
            client.kill(dcontainer)
            if not is_running(dcontainer):
                valid(
                    status,
                    comment='Container {0} was killed'.format(
                        container),
                    id=container)
            else:
                invalid(status,
                        comment='Container {0} was not killed'.format(
                            container))
        else:
            valid(
                status,
                comment='Container {0} was already stopped'.format(
                    container),
                id=container)
    except Exception:
        invalid(status,
                id=container,
                out=traceback.format_exc(),
                comment=(
                    'An exception occured while killing '
                    'your container {0}').format(container))
    return status


def restart(container, timeout=10):
    '''
    Restart a running container

    :type container: string
    :param container: The container id to restart

    :type timout: int
    :param timeout: Wait for a timeout to let the container exit gracefully
        before killing it

    :rtype: dict
    :returns: A status message with the command output
          ex:
            {'id': 'abcdef123456789',
           'status': True}

    '''
    client = get_client()
    status = base_status.copy()
    try:
        dcontainer = get_container_infos(container)['id']
        client.restart(dcontainer, timeout=timeout)
        if is_running(dcontainer):
            valid(status,
                  comment='Container {0} was restarted'.format(container),
                  id=container)
        else:
            invalid(status)
    except Exception:
        invalid(status, id=container, out=traceback.format_exc(),
                comment=(
                    'An exception occured while restarting '
                    'your container {0}').format(container))
    return status


def start(container, binds=None, ports=None):
    '''
    restart the specified container
    container
        Container id
    Returns the status mapping as usual
         {'id': id of the container,
          'status': True if started }
    '''
    if not binds:
        binds = {}
    if not ports:
        ports = {}
    client = get_client()
    status = base_status.copy()
    try:
        dcontainer = get_container_infos(container)['id']
        if not is_running(container):
            client.start(dcontainer, binds=binds)
            if is_running(dcontainer):
                valid(status,
                      comment='Container {0} was started'.format(container),
                      id=container)
            else:
                invalid(status)
        else:
            valid(
                status,
                comment='Container {0} was already started'.format(container),
                id=container)
    except Exception:
        invalid(status,
                id=container,
                out=traceback.format_exc(),
                comment=(
                    'An exception occured while starting '
                    'your container {0}').format(container))
    return status


def wait(container):
    '''
    Blocking wait for a container exit gracefully without
    timeout killing it
    container
        Container id
    Return container id if succesful
         {'id': id of the container,
          'status': True if stopped }
    '''
    client = get_client()
    status = base_status.copy()
    try:
        dcontainer = get_container_infos(container)['id']
        if is_running(dcontainer):
            client.wait(dcontainer)
            if not is_running(container):
                valid(status,
                      id=container,
                      comment='Container waited for stop')
            else:
                invalid(status)
        else:
            valid(
                status,
                comment='Container {0} was already stopped'.format(container),
                id=container)
    except Exception:
        invalid(status, id=container, out=traceback.format_exc(),
                comment=(
                    'An exception occured while waitting '
                    'your container {0}').format(container))
    return status


def exists(container):
    '''
    Check if a given container exists

    :type container: string
    :param container: Container id

    :rtype: boolean:

    .. code-block:: bash

        salt '*' docker.exists <container>

    '''
    try:
        get_container_infos(container)
        return True
    except Exception:
        return False


def is_running(container):
    '''
    Is this container running
    container
        Container id
    Return boolean
    '''
    try:
        infos = get_container_infos(container)
        return infos.get('State', {}).get('Running')
    except Exception:
        return False


def remove_container(container=None, force=False, v=False):
    '''
    Removes a container from a docker installation
    container
        Container id to remove
    force
        By default, do not remove a running container, set this
        to remove it unconditionnaly
    v
        verbose mode

    Return True or False in the status mapping and also
    any information about docker in status['out']
    '''
    client = get_client()
    status = base_status.copy()
    status['id'] = container
    dcontainer = None
    try:
        dcontainer = get_container_infos(container)['id']
        if is_running(dcontainer):
            if not force:
                invalid(status, id=container, out=None,
                        comment=(
                            'Container {0} is running, '
                            'won\'t remove it').format(container))
                return status
            else:
                kill(dcontainer)
        client.remove_container(dcontainer, v=v)
        try:
            get_container_infos(dcontainer)
            invalid(status,
                    comment="Container was not removed: {0}".format(container))
        except Exception:
            status['status'] = True
            status['comment'] = 'Container {0} was removed'.format(container)
    except Exception:
        invalid(status, id=container, out=traceback.format_exc())
    return status


def top(container):
    '''
    Run the docker top command on a specific container
    container
        Container id

    Returns in the 'out' status mapping a mapping for
    those running processes::

       {
            'Titles': top titles list,
            'proceeses': list of orderered by
                         titles processes informations,
            'mprocesses': list of mappings processes informations
            constructed above the upon informations
       }

    '''
    client = get_client()
    status = base_status.copy()
    try:
        dcontainer = get_container_infos(container)['id']
        if is_running(dcontainer):
            ret = client.top(dcontainer)
            if ret:
                ret['mprocesses'] = []
                titles = ret['Titles']
                for i in ret['Processes']:
                    data = OrderedDict()
                    for k, j in enumerate(titles):
                        data[j] = i[k]
                    ret['mprocesses'].append(data)
                valid(status,
                      out=ret,
                      id=container,
                      comment='Current top for container')
            if not status['id']:
                invalid(status)
        else:
            invalid(status,
                    comment='Container {0} is not running'.format(container))
    except Exception:
        invalid(status, id=container, out=traceback.format_exc())
    return status


def inspect_container(container):
    '''
    Get container information. This is similar to the docker inspect command.

    :type container: string
    :param container: The id of the container to inspect

    :rtype: dict
    :returns: A status message with the command output

    .. code-block:: bash

        salt '*' docker.inspect_container <container>

    '''
    status = base_status.copy()
    status['id'] = container
    try:
        infos = get_container_infos(container)
        valid(status, id=container, out=infos)
    except Exception:
        invalid(status, id=container, out=traceback.format_exc(),
                comment=(
                    'Container does not exit: {0}'
                ).format(container))
    return status


def login(url=None, username=None, password=None, email=None):
    '''
    Wrapper to the docker.py login method, does not do much yet
    '''
    client = get_client()
    return client.login(url, username=username, password=password, email=email)


def search(term):
    '''
    Search for an image on the registry

    :type term: string
    :param term: The search keyword to query

    .. code-block:: bash

        salt '*' docker.search <term>

    '''
    client = get_client()
    status = base_status.copy()
    ret = client.search(term)
    if ret:
        valid(status, out=ret, id=term)
    else:
        invalid(status)
    return status


def create_image_assemble_error_status(status, ret, logs):
    '''
    Given input in this form::

      [{u'error': u'Get file:///r.tar.gz: unsupported protocol scheme "file"',
       u'errorDetail': {
       u'message':u'Get file:///r.tar.gz:unsupported protocol scheme "file"'}},
       {u'status': u'Downloading from file:///r.tar.gz'}]


    '''
    comment = 'An error occured while importing your image'
    out = None
    is_invalid = True
    status['out'] = ''
    try:
        is_invalid = False
        status['out'] += '\n' + ret
        for log in logs:
            if isinstance(log, dict):
                if 'errorDetail' in log:
                    if 'code' in log['errorDetail']:
                        msg = '\n{0}\n{1}: {2}'.format(
                            log['error'],
                            log['errorDetail']['code'],
                            log['errorDetail']['message']
                        )
                    else:
                        msg = '\n{0}\n{1}'.format(
                            log['error'],
                            log['errorDetail']['message'],
                        )
                    comment += msg
    except Exception:
        is_invalid = True
        trace = traceback.format_exc()
        out = (
            'An error occured while '
            'parsing error output:\n{0}'
        ).format(trace)
    if is_invalid:
        invalid(status, out=out, comment=comment)
    return status


def import_image(src, repo, tag=None):
    '''
    Import content from a local tarball or an url to a docker image

    :type src: string
    :param src: The content to import (URL, absolute path to a tarball)

    :type repo: string
    :param repo: The repository to import to

    :type tag: string
    :param tag: An optional tag to set

    .. code-block:: bash

        salt '*' docker.import_image <src> <repo> [tag]

    '''
    client = get_client()
    status = base_status.copy()
    try:
        ret = client.import_image(src, repository=repo, tag=tag)
        if ret:
            logs, info = parse_image_multilogs_string(ret)
            create_image_assemble_error_status(status, ret, logs)
            if status['status'] is not False:
                infos = get_image_infos(logs[0]['status'])
                valid(status,
                      comment='Image {0} was created'.format(infos['id']),
                      id=infos['id'],
                      out=ret)
        else:
            invalid(status)
    except Exception:
        invalid(status, out=traceback.format_exc())
    return status


def tag(image, repository, tag=None, force=False):
    '''
    Tag an image into a repository

    :type image: string
    :param image: The image to tag

    :type repository: string
    :param repository: The repository to tag the image

    :type tag: string
    :param tag: The tag to apply

    :type force: boolean
    :param force: Forces application of the tag

    .. code-block:: bash

        salt '*' docker.tag <image> <repository> [tag] [force=(True|False)]

    '''
    client = get_client()
    status = base_status.copy()
    try:
        dimage = get_image_infos(image)['id']
        ret = client.tag(dimage, repository, tag=tag, force=force)
    except Exception:
        invalid(status,
                out=traceback.format_exc(),
                comment='Cant tag image {0} {1}{2}'.format(
                    image, repository,
                    tag and (':' + tag) or '').strip())
        return status
    if ret:
        valid(status,
              id=image,
              comment='Image was tagged: {0}{1}'.format(
                  repository,
                  tag and (':' + tag) or '').strip())
    else:
        invalid(status)
    return status


def get_images(name=None, quiet=False, all=True):
    '''
    List docker images

    :type name: string
    :param name: A repository name to filter on

    :type quiet: boolean
    :param quiet: Only show image ids

    :type all: boolean
    :param all: Show all images

    :rtype: dict
    :returns: A status message with the command output

    .. code-block:: bash

        salt '*' docker.get_images [name] [quiet=True|False] [all=True|False]

    '''
    client = get_client()
    status = base_status.copy()
    try:
        infos = client.images(name=name, quiet=quiet, all=all)
        for i in range(len(infos)):
            inf = infos[i]
            try:
                inf['Human_Size'] = sizeof_fmt(int(inf['Size']))
            except ValueError:
                pass
            try:
                ts = int(inf['Created'])
                dts = datetime.datetime.fromtimestamp(ts)
                inf['Human_IsoCreated'] = dts.isoformat()
                inf['Human_Created'] = dts.strftime(
                    '%Y-%m-%d %H:%M:%S')
            except Exception:
                pass
            try:
                inf['Human_VirtualSize'] = (
                    sizeof_fmt(int(inf['VirtualSize'])))
            except ValueError:
                pass
        valid(status, out=infos)
    except Exception:
        invalid(status, out=traceback.format_exc())
    return status


def build(path=None,
          tag=None,
          quiet=False,
          fileobj=None,
          nocache=False):
    client = get_client()
    status = base_status.copy()
    if path or fileobj:
        try:
            ret = client.build(path=path, tag=tag, quiet=quiet,
                               fileobj=fileobj, nocache=nocache)
        except Exception:
            invalid(status,
                    out=traceback.format_exc(),
                    comment='Unexpected error while building an image')
            return status
        if isinstance(ret, tuple):
            id, out = ret[0], ret[1]
            if id:
                valid(status, id=id, out=out, comment='Image built')
            else:
                invalid(status, id=id, out=out)
    return status


def remove_image(image):
    '''
    Remove an image from a system.

    :type image: string
    :param image: The image to remove

    :rtype: string
    :returns: A status message.

    .. code-block:: bash

        salt '*' docker.remove_image <image>

    '''
    client = get_client()
    status = base_status.copy()
    # will raise an error if no deletion
    try:
        infos = get_image_infos(image)
        if infos:
            status['id'] = infos['id']
            try:
                client.remove_image(infos['id'])
            except Exception:
                invalid(status,
                        id=image,
                        out=traceback.format_exc(),
                        comment='Image could not be deleted')
            try:
                infos = get_image_infos(image)
                invalid(status,
                        comment=(
                            'Image marked to be deleted but not deleted yet'))
            except Exception:
                valid(status, id=image, comment='Image deleted')
        else:
            invalid(status)
    except Exception:
        invalid(status,
                out=traceback.format_exc(),
                comment='Image does not exist: {0}'.format(image))
    return status


def inspect_image(image):
    status = base_status.copy()
    try:
        infos = get_image_infos(image)
        try:
            for k in ['Size']:
                infos[
                    'Human_{0}'.format(k)
                ] = sizeof_fmt(int(infos[k]))
        except Exception:
            pass
        valid(status, id=image, out=infos)
    except Exception:
        invalid(status, id=image, out=traceback.format_exc(),
                comment='Image does not exist')
    return status


def parse_image_multilogs_string(ret):
    logs, infos = [], None
    if ret and ret.startswith('{') and ret.endswith('}'):
        pushd = 0
        buf = ''
        for char in ret:
            buf += char
            if char == '{':
                pushd += 1
            if char == '}':
                pushd -= 1
            if pushd == 0:
                try:
                    buf = json.loads(buf)
                except Exception:
                    pass
                logs.append(buf)
                buf = ''
        logs.reverse()
        # search last layer grabbed
        for l in logs:
            if isinstance(l, dict):
                if (
                    l.get('progress', 'not complete') == 'complete'
                    and l.get('id', None)
                ):
                    infos = get_image_infos(l['id'])
                    break
    return logs, infos


def pull_assemble_error_status(status, ret, logs):
    '''
    Given input in this form::

        u'{"status":"Pulling repository foo/ubuntubox"}:
        "image (latest) from foo/  ...
         rogress":"complete","id":"2c80228370c9"}'

    construct something like that (load json data is possible)::

        [u'{"status":"Pulling repository foo/ubuntubox"',
         {"status":"Download","progress":"complete","id":"2c80228370c9"}]
    '''
    comment = 'An error occured pulling your image'
    out = ''
    try:
        out = '\n' + ret
        for log in logs:
            if isinstance(log, dict):
                if 'errorDetail' in log:
                    if 'code' in log['errorDetail']:
                        msg = '\n{0}\n{1}: {2}'.format(
                            log['error'],
                            log['errorDetail']['code'],
                            log['errorDetail']['message']
                        )
                    else:
                        msg = '\n{0}\n{1}'.format(
                            log['error'],
                            log['errorDetail']['message'],
                        )
                    comment += msg
    except Exception:
        out = traceback.format_exc()
    invalid(status, out=out, comment=comment)
    return status


def pull(repo, tag=None):
    '''
    Pulls an image from any registry. See above documentation for
    how to configure authenticated access.

    :type repo: string
    :param repo: The repository to pull. \
        [registryurl://]REPOSITORY_NAME_image
        eg::

            index.docker.io:MyRepo/image
            superaddress.cdn:MyRepo/image
            MyRepo/image

    :type tag: string
    :param tag: The specific tag  to pull

    :rtype: dict
    :returns: A status message with the command output
        Example:

        .. code-block:: yaml

            ----------
            comment:
                Image NAME was pulled (ID
            id:
                None
            out:
                ----------
                - id:
                    2c80228370c9
                - progress:
                    complete
                - status:
                    Download
                ----------
                - id:
                    2c80228370c9
                - progress:
                    image (latest) from NAME, endpoint: URL
                - status:
                    Pulling
                ----------
                - id:
                    2c80228370c9
                - progress:
                    image (latest) from foo/ubuntubox
                - status:
                    Pulling
                ----------
                - status:
                    Pulling repository foo/ubuntubox
            status:
                True

    .. code-block:: bash

        salt '*' docker.pull <repository> [tag]

    '''
    client = get_client()
    status = base_status.copy()
    try:
        ret = client.pull(repo, tag=tag)
        if ret:
            logs, infos = parse_image_multilogs_string(ret)
            if infos and infos.get('id', None):
                repotag = repo
                if tag:
                    repotag = '{0}:{1}'.format(repo, tag)
                valid(status,
                      out=logs and logs or ret,
                      comment='Image {0} was pulled ({1})'.format(
                          repotag, infos['id']))

            else:
                pull_assemble_error_status(status, ret, logs)
        else:
            invalid(status)
    except Exception:
        invalid(status, id=repo, out=traceback.format_exc())
    return status


def push_assemble_error_status(status, ret, logs):
    '''
    Given input in this form::

        u'{"status":"Pulling repository foo/ubuntubox"}:
        "image (latest) from foo/  ...
         rogress":"complete","id":"2c80228370c9"}'

    construct something like that (load json data is possible)::

        [u'{"status":"Pulling repository foo/ubuntubox"',
         {"status":"Download","progress":"complete","id":"2c80228370c9"}]
    '''
    comment = 'An error occured pushing your image'
    status['out'] = ''
    try:
        status['out'] += '\n' + ret
        for log in logs:
            if isinstance(log, dict):
                if 'errorDetail' in log:
                    if 'code' in log['errorDetail']:
                        msg = '\n{0}\n{1}: {2}'.format(
                            log['error'],
                            log['errorDetail']['code'],
                            log['errorDetail']['message']
                        )
                    else:
                        msg = '\n{0}\n{1}'.format(
                            log['error'],
                            log['errorDetail']['message'],
                        )
                    comment += msg
    except Exception:
        trace = traceback.format_exc()
        status['out'] = (
            'An error occured while '
            'parsing error output:\n{0}'
        ).format(trace)
    invalid(status, comment=comment)
    return status


def push(repo):
    '''
    Pushes an image from any registry
    See this top level documentation to know
    how to configure authenticated access

    repo
        [registryurl://]REPOSITORY_NAME_image
        eg::

            index.docker.io:MyRepo/image
            superaddress.cdn:MyRepo/image
            MyRepo/image
    '''
    client = get_client()
    status = base_status.copy()
    registry, repo_name = docker.auth.resolve_repository_name(repo)
    ret = client.push(repo)
    logs, infos = parse_image_multilogs_string(ret)
    if logs:
        laststatus = logs[0].get('status', None)
        if laststatus and (
            ('already pushed' in laststatus)
            or ('Pushing tags for rev' in laststatus)
        ):
            status['status'] = True
            status['id'] = get_image_infos(repo)['id']
            status['comment'] = 'Image {0}({1}) was pushed'.format(
                repo, status['id'])
            if logs:
                status['out'] = logs
            else:
                status['out'] = ret
        else:
            push_assemble_error_status(status, ret, logs)
    else:
        push_assemble_error_status(status, ret, logs)
    return status


def retcode():
    '''.'''


def run():
    '''.'''

## vim:set et sts=4 ts=4 tw=80:
