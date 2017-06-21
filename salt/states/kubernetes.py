# -*- coding: utf-8 -*-
'''
Manage kubernetes resources as salt states
==========================================

NOTE: This module requires the proper pillar values set. See
salt.modules.kubernetes for more information.

The kubernetes module is used to manage different kubernetes resources.


.. code-block:: yaml

    my-nginx:
      kubernetes.deployment_present:
        - namespace: default
          metadata:
            app: frontend
          spec:
            replicas: 1
            template:
              metadata:
                labels:
                  run: my-nginx
              spec:
                containers:
                - name: my-nginx
                  image: nginx
                  ports:
                  - containerPort: 80

    my-mariadb:
      kubernetes.deployment_absent:
        - namespace: default

    # kubernetes deployment as specified inside of
    # a file containing the definition of the the
    # deployment using the official kubernetes format
    redis-master-deployment:
      kubernetes.deployment_present:
        - name: redis-master
        - source: salt://k8s/redis-master-deployment.yml
      require:
        - pip: kubernetes-python-module

    # kubernetes service as specified inside of
    # a file containing the definition of the the
    # service using the official kubernetes format
    redis-master-service:
      kubernetes.service_present:
        - name: redis-master
        - source: salt://k8s/redis-master-service.yml
      require:
        - kubernetes.deployment_present: redis-master

    # kubernetes deployment as specified inside of
    # a file containing the definition of the the
    # deployment using the official kubernetes format
    # plus some jinja directives
     nginx-source-template:
      kubernetes.deployment_present:
        - source: salt://k8s/nginx.yml.jinja
        - template: jinja
      require:
        - pip: kubernetes-python-module


    # Kubernetes secret
    k8s-secret:
      kubernetes.secret_present:
        - name: top-secret
          data:
            key1: value1
            key2: value2
            key3: value3
'''
from __future__ import absolute_import

import logging
log = logging.getLogger(__name__)


def __virtual__():
    '''
    Only load if the kubernetes module is available in __salt__
    '''
    return 'kubernetes.ping' in __salt__


def _error(ret, err_msg):
    '''
    Helper function to propagate errors to
    the end user.
    '''
    ret['result'] = False
    ret['comment'] = err_msg
    return ret


def deployment_absent(name, namespace='default', **kwargs):
    '''
    Ensures that the named deployment is absent from the given namespace.

    name
        The name of the deployment

    namespace
        The name of the namespace
    '''

    ret = {'name': name,
           'changes': {},
           'result': False,
           'comment': ''}

    deployment = __salt__['kubernetes.show_deployment'](name, namespace, **kwargs)

    if deployment is None:
        ret['result'] = True if not __opts__['test'] else None
        ret['comment'] = 'The deployment does not exist'
        return ret

    if __opts__['test']:
        ret['comment'] = 'The deployment is going to be deleted'
        ret['result'] = None
        return ret

    res = __salt__['kubernetes.delete_deployment'](name, namespace, **kwargs)
    if res['code'] == 200:
        ret['result'] = True
        ret['changes'] = {
            'kubernetes.deployment': {
                'new': 'absent', 'old': 'present'}}

    ret['comment'] = res['message']
    return ret


def deployment_present(
        name,
        namespace='default',
        metadata=None,
        spec=None,
        source='',
        template='',
        **kwargs):
    '''
    Ensures that the named deployment is present inside of the specified
    namespace with the given metadata and spec.
    If the deployment exists it will be replaced.

    name
        The name of the deployment.

    namespace
        The namespace holding the deployment. The 'default' one is going to be
        used unless a different one is specified.

    metadata
        The metadata of the deployment object.

    spec
        The spec of the deployment object.

    source
        A file containing the definition of the deployment (metadata and
        spec) in the official kubernetes format.

    template
        Template engine to be used to render the source file.
    '''
    ret = {'name': name,
           'changes': {},
           'result': False,
           'comment': ''}

    if (metadata or spec) and source:
        return _error(
            ret,
            '\'source\' cannot be used in combination with \'metadata\' or '
            '\'spec\''
        )

    if metadata is None:
        metadata = {}

    if spec is None:
        spec = {}

    deployment = __salt__['kubernetes.show_deployment'](name, namespace, **kwargs)

    if deployment is None:
        if __opts__['test']:
            ret['result'] = None
            ret['comment'] = 'The deployment is going to be created'
            return ret
        res = __salt__['kubernetes.create_deployment'](name=name,
                                                       namespace=namespace,
                                                       metadata=metadata,
                                                       spec=spec,
                                                       source=source,
                                                       template=template,
                                                       saltenv=__env__,
                                                       **kwargs)
        ret['changes']['{0}.{1}'.format(namespace, name)] = {
            'old': {},
            'new': res}
    else:
        if __opts__['test']:
            ret['result'] = None
            return ret

        # TODO: improve checks  # pylint: disable=fixme
        log.info('Forcing the recreation of the deployment')
        ret['comment'] = 'The deployment is already present. Forcing recreation'
        res = __salt__['kubernetes.replace_deployment'](
            name=name,
            namespace=namespace,
            metadata=metadata,
            spec=spec,
            source=source,
            template=template,
            saltenv=__env__,
            **kwargs)

    ret['changes'] = {
        'metadata': metadata,
        'spec': spec
    }
    ret['result'] = True
    return ret


def service_present(
        name,
        namespace='default',
        metadata=None,
        spec=None,
        source='',
        template='',
        **kwargs):
    '''
    Ensures that the named service is present inside of the specified namespace
    with the given metadata and spec.
    If the deployment exists it will be replaced.

    name
        The name of the service.

    namespace
        The namespace holding the service. The 'default' one is going to be
        used unless a different one is specified.

    metadata
        The metadata of the service object.

    spec
        The spec of the service object.

    source
        A file containing the definition of the service (metadata and
        spec) in the official kubernetes format.

    template
        Template engine to be used to render the source file.
    '''
    ret = {'name': name,
           'changes': {},
           'result': False,
           'comment': ''}

    if (metadata or spec) and source:
        return _error(
            ret,
            '\'source\' cannot be used in combination with \'metadata\' or '
            '\'spec\''
        )

    if metadata is None:
        metadata = {}

    if spec is None:
        spec = {}

    service = __salt__['kubernetes.show_service'](name, namespace, **kwargs)

    if service is None:
        if __opts__['test']:
            ret['result'] = None
            ret['comment'] = 'The service is going to be created'
            return ret
        res = __salt__['kubernetes.create_service'](name=name,
                                                    namespace=namespace,
                                                    metadata=metadata,
                                                    spec=spec,
                                                    source=source,
                                                    template=template,
                                                    saltenv=__env__,
                                                    **kwargs)
        ret['changes']['{0}.{1}'.format(namespace, name)] = {
            'old': {},
            'new': res}
    else:
        if __opts__['test']:
            ret['result'] = None
            return ret

        # TODO: improve checks  # pylint: disable=fixme
        log.info('Forcing the recreation of the service')
        ret['comment'] = 'The service is already present. Forcing recreation'
        res = __salt__['kubernetes.replace_service'](
            name=name,
            namespace=namespace,
            metadata=metadata,
            spec=spec,
            source=source,
            template=template,
            old_service=service,
            saltenv=__env__,
            **kwargs)

    ret['changes'] = {
        'metadata': metadata,
        'spec': spec
    }
    ret['result'] = True
    return ret


def service_absent(name, namespace='default', **kwargs):
    '''
    Ensures that the named service is absent from the given namespace.

    name
        The name of the service

    namespace
        The name of the namespace
    '''

    ret = {'name': name,
           'changes': {},
           'result': False,
           'comment': ''}

    service = __salt__['kubernetes.show_service'](name, namespace, **kwargs)

    if service is None:
        ret['result'] = True if not __opts__['test'] else None
        ret['comment'] = 'The service does not exist'
        return ret

    if __opts__['test']:
        ret['comment'] = 'The service is going to be deleted'
        ret['result'] = None
        return ret

    res = __salt__['kubernetes.delete_service'](name, namespace, **kwargs)
    if res['code'] == 200:
        ret['result'] = True
        ret['changes'] = {
            'kubernetes.service': {
                'new': 'absent', 'old': 'present'}}
    ret['comment'] = res['message']
    return ret


def namespace_absent(name, **kwargs):
    '''
    Ensures that the named namespace is absent.

    name
        The name of the namespace
    '''

    ret = {'name': name,
           'changes': {},
           'result': False,
           'comment': ''}

    namespace = __salt__['kubernetes.show_namespace'](name, **kwargs)

    if namespace is None:
        ret['result'] = True if not __opts__['test'] else None
        ret['comment'] = 'The namespace does not exist'
        return ret

    if __opts__['test']:
        ret['comment'] = 'The namespace is going to be deleted'
        ret['result'] = None
        return ret

    res = __salt__['kubernetes.delete_namespace'](name, **kwargs)
    if (
            res['code'] == 200 or
            (
                isinstance(res['status'], str) and
                'Terminating' in res['status']
            ) or
            (
                isinstance(res['status'], dict) and
                res['status']['phase'] == 'Terminating'
            )):
        ret['result'] = True
        ret['changes'] = {
            'kubernetes.namespace': {
                'new': 'absent', 'old': 'present'}}
        if res['message']:
            ret['comment'] = res['message']
        else:
            ret['comment'] = 'Terminating'
    else:
        ret['comment'] = 'Unknown state: {0}'.format(res)

    return ret


def namespace_present(name, **kwargs):
    '''
    Ensures that the named namespace is present.

    name
        The name of the deployment.

    '''
    ret = {'name': name,
           'changes': {},
           'result': False,
           'comment': ''}

    namespace = __salt__['kubernetes.show_namespace'](name, **kwargs)

    if namespace is None:
        if __opts__['test']:
            ret['result'] = None
            ret['comment'] = 'The namespace is going to be created'
            return ret
        res = __salt__['kubernetes.create_namespace'](name, **kwargs)
        ret['changes']['namespace'] = {
            'old': {},
            'new': res}
    else:
        ret['result'] = True if not __opts__['test'] else None
        ret['comment'] = 'The namespace already exists'

    return ret


def secret_absent(name, namespace='default', **kwargs):
    '''
    Ensures that the named secret is absent from the given namespace.

    name
        The name of the secret

    namespace
        The name of the namespace
    '''

    ret = {'name': name,
           'changes': {},
           'result': False,
           'comment': ''}

    secret = __salt__['kubernetes.show_secret'](name, namespace, **kwargs)

    if secret is None:
        ret['result'] = True if not __opts__['test'] else None
        ret['comment'] = 'The secret does not exist'
        return ret

    if __opts__['test']:
        ret['comment'] = 'The secret is going to be deleted'
        ret['result'] = None
        return ret

    __salt__['kubernetes.delete_secret'](name, namespace, **kwargs)

    # As for kubernetes 1.6.4 doesn't set a code when deleting a secret
    # The kubernetes module will raise an exception if the kubernetes
    # server will return an error
    ret['result'] = True
    ret['changes'] = {
        'kubernetes.secret': {
            'new': 'absent', 'old': 'present'}}
    ret['comment'] = 'Secret deleted'
    return ret


def secret_present(
        name,
        namespace='default',
        data=None,
        source='',
        template='',
        **kwargs):
    '''
    Ensures that the named secret is present inside of the specified namespace
    with the given data.
    If the secret exists it will be replaced.

    name
        The name of the secret.

    namespace
        The namespace holding the secret. The 'default' one is going to be
        used unless a different one is specified.

    data
        The dictionary holding the secrets.

    source
        A file containing the data of the secret in plain format.

    template
        Template engine to be used to render the source file.
    '''
    ret = {'name': name,
           'changes': {},
           'result': False,
           'comment': ''}

    if data and source:
        return _error(
            ret,
            '\'source\' cannot be used in combination with \'data\''
        )

    secret = __salt__['kubernetes.show_secret'](name, namespace, **kwargs)

    if secret is None:
        if data is None:
            data = {}

        if __opts__['test']:
            ret['result'] = None
            ret['comment'] = 'The secret is going to be created'
            return ret
        res = __salt__['kubernetes.create_secret'](name=name,
                                                   namespace=namespace,
                                                   data=data,
                                                   source=source,
                                                   template=template,
                                                   saltenv=__env__,
                                                   **kwargs)
        ret['changes']['{0}.{1}'.format(namespace, name)] = {
            'old': {},
            'new': res}
    else:
        if __opts__['test']:
            ret['result'] = None
            return ret

        # TODO: improve checks  # pylint: disable=fixme
        log.info('Forcing the recreation of the service')
        ret['comment'] = 'The secret is already present. Forcing recreation'
        res = __salt__['kubernetes.replace_secret'](
            name=name,
            namespace=namespace,
            data=data,
            source=source,
            template=template,
            saltenv=__env__,
            **kwargs)

    ret['changes'] = {
        # Omit values from the return. They are unencrypted
        # and can contain sensitive data.
        'data': res['data'].keys()
    }
    ret['result'] = True
    return ret

