# -*- coding: utf-8 -*-
'''
Module for handling kubernetes calls.

:optdepends:    - kubernetes Python client
:configuration: The k8s API settings are provided either in a pillar, in
    the minion's config file, or in master's config file::

        kubernetes.kubeconfig: '/path/to/kubeconfig'
        kubernetes.kubeconfig-data: '<base64 encoded kubeconfig content'
        kubernetes.context: 'context'

These settings can be also overrided by adding `context and `kubeconfig` or
`kubeconfig_data` parameters when calling a function.

The data format for `kubernetes.kubeconfig-data` value is the content of
`kubeconfig` base64 encoded in one line.

Only `kubeconfig` or `kubeconfig-data` should be provided. In case both are
provided `kubeconfig` entry is prefered.

.. code-block:: bash

    salt '*' kubernetes.nodes kubeconfig=/etc/salt/k8s/kubeconfig context=minikube

.. versionadded: 2017.7.0
'''

# Import Python Futures
from __future__ import absolute_import, unicode_literals, print_function
import sys
import os.path
import base64
import logging
import tempfile
import signal
from time import sleep
from contextlib import contextmanager

from salt.exceptions import CommandExecutionError
from salt.ext.six import iteritems
from salt.ext import six
import salt.utils.files
import salt.utils.templates
import salt.utils.yaml
from salt.exceptions import TimeoutError
from salt.ext.six.moves import range  # pylint: disable=import-error

try:
    import kubernetes  # pylint: disable=import-self
    import kubernetes.client
    from kubernetes.client.rest import ApiException
    from urllib3.exceptions import HTTPError
    try:
        # There is an API change in Kubernetes >= 2.0.0.
        from kubernetes.client import V1beta1Deployment as AppsV1beta1Deployment
        from kubernetes.client import V1beta1DeploymentSpec as AppsV1beta1DeploymentSpec
    except ImportError:
        from kubernetes.client import AppsV1beta1Deployment
        from kubernetes.client import AppsV1beta1DeploymentSpec

    HAS_LIBS = True
except ImportError:
    HAS_LIBS = False

log = logging.getLogger(__name__)

__virtualname__ = 'kubernetes'


def __virtual__():
    '''
    Check dependencies
    '''
    if HAS_LIBS:
        return __virtualname__

    return False, 'python kubernetes library not found'


if not salt.utils.platform.is_windows():
    @contextmanager
    def _time_limit(seconds):
        def signal_handler(signum, frame):
            raise TimeoutError
        signal.signal(signal.SIGALRM, signal_handler)
        signal.alarm(seconds)
        try:
            yield
        finally:
            signal.alarm(0)

    POLLING_TIME_LIMIT = 30


# pylint: disable=no-member
def _setup_conn(**kwargs):
    '''
    Setup kubernetes API connection singleton
    '''
    kubeconfig = __salt__['config.option']('kubernetes.kubeconfig')
    kubeconfig_data = __salt__['config.option']('kubernetes.kubeconfig-data')
    context = __salt__['config.option']('kubernetes.context')

    kubeconfig_data_overwrite = False
    # Override default API settings when settings are provided
    if 'kubeconfig' in kwargs:
        kubeconfig = kwargs.get('kubeconfig')
    elif 'kubeconfig_data' in kwargs:
        kubeconfig_data = kwargs.get('kubeconfig_data')
        kubeconfig_data_overwrite = True

    if 'context' in kwargs:
        context = kwargs.get('context')

    if (kubeconfig_data and not kubeconfig) or (kubeconfig_data and kubeconfig_data_overwrite):
        with tempfile.NamedTemporaryFile(prefix='salt-kubeconfig-', delete=False) as kcfg:
            kcfg.write(base64.b64decode(kubeconfig_data))
            kubeconfig = kcfg.name
    kubernetes.config.load_kube_config(config_file=kubeconfig, context=context)

    # The return makes unit testing easier
    return {'kubeconfig': kubeconfig, 'context': context}


def _cleanup(**kwargs):
    if 'kubeconfig' in kwargs:
        kubeconfig = kwargs.get('kubeconfig')
        if os.path.exists(kubeconfig) and os.path.basename(kubeconfig).startswith('salt-kubeconfig-'):
            salt.utils.files.safe_rm(kubeconfig)


def ping(**kwargs):
    '''
    Checks connections with the kubernetes API server.
    Returns True if the connection can be established, False otherwise.

    CLI Example:
        salt '*' kubernetes.ping
    '''
    status = True
    try:
        nodes(**kwargs)
    except CommandExecutionError:
        status = False

    return status


def nodes(**kwargs):
    '''
    Return the names of the nodes composing the kubernetes cluster

    CLI Examples::

        salt '*' kubernetes.nodes
        salt '*' kubernetes.nodes kubeconfig=/etc/salt/k8s/kubeconfig context=minikube
    '''
    cfg = _setup_conn(**kwargs)
    try:
        api_instance = kubernetes.client.CoreV1Api()
        api_response = api_instance.list_node()

        return [k8s_node['metadata']['name'] for k8s_node in api_response.to_dict().get('items')]
    except (ApiException, HTTPError) as exc:
        if isinstance(exc, ApiException) and exc.status == 404:
            return None
        else:
            log.exception('Exception when calling CoreV1Api->list_node')
            raise CommandExecutionError(exc)
    finally:
        _cleanup(**cfg)


def node(name, **kwargs):
    '''
    Return the details of the node identified by the specified name

    CLI Examples::

        salt '*' kubernetes.node name='minikube'
    '''
    cfg = _setup_conn(**kwargs)
    try:
        api_instance = kubernetes.client.CoreV1Api()
        api_response = api_instance.list_node()
    except (ApiException, HTTPError) as exc:
        if isinstance(exc, ApiException) and exc.status == 404:
            return None
        else:
            log.exception('Exception when calling CoreV1Api->list_node')
            raise CommandExecutionError(exc)
    finally:
        _cleanup(**cfg)

    for k8s_node in api_response.items:
        if k8s_node.metadata.name == name:
            return k8s_node.to_dict()

    return None


def node_labels(name, **kwargs):
    '''
    Return the labels of the node identified by the specified name

    CLI Examples::

        salt '*' kubernetes.node_labels name="minikube"
    '''
    match = node(name, **kwargs)

    if match is not None:
        return match['metadata']['labels']

    return {}


def node_add_label(node_name, label_name, label_value, **kwargs):
    '''
    Set the value of the label identified by `label_name` to `label_value` on
    the node identified by the name `node_name`.
    Creates the lable if not present.

    CLI Examples::

        salt '*' kubernetes.node_add_label node_name="minikube" \
            label_name="foo" label_value="bar"
    '''
    cfg = _setup_conn(**kwargs)
    try:
        api_instance = kubernetes.client.CoreV1Api()
        body = {
            'metadata': {
                'labels': {
                    label_name: label_value}
                }
        }
        api_response = api_instance.patch_node(node_name, body)
        return api_response
    except (ApiException, HTTPError) as exc:
        if isinstance(exc, ApiException) and exc.status == 404:
            return None
        else:
            log.exception('Exception when calling CoreV1Api->patch_node')
            raise CommandExecutionError(exc)
    finally:
        _cleanup(**cfg)

    return None


def node_remove_label(node_name, label_name, **kwargs):
    '''
    Removes the label identified by `label_name` from
    the node identified by the name `node_name`.

    CLI Examples::

        salt '*' kubernetes.node_remove_label node_name="minikube" \
            label_name="foo"
    '''
    cfg = _setup_conn(**kwargs)
    try:
        api_instance = kubernetes.client.CoreV1Api()
        body = {
            'metadata': {
                'labels': {
                    label_name: None}
                }
        }
        api_response = api_instance.patch_node(node_name, body)
        return api_response
    except (ApiException, HTTPError) as exc:
        if isinstance(exc, ApiException) and exc.status == 404:
            return None
        else:
            log.exception('Exception when calling CoreV1Api->patch_node')
            raise CommandExecutionError(exc)
    finally:
        _cleanup(**cfg)

    return None


def namespaces(**kwargs):
    '''
    Return the names of the available namespaces

    CLI Examples::

        salt '*' kubernetes.namespaces
        salt '*' kubernetes.namespaces kubeconfig=/etc/salt/k8s/kubeconfig context=minikube
    '''
    cfg = _setup_conn(**kwargs)
    try:
        api_instance = kubernetes.client.CoreV1Api()
        api_response = api_instance.list_namespace()

        return [nms['metadata']['name'] for nms in api_response.to_dict().get('items')]
    except (ApiException, HTTPError) as exc:
        if isinstance(exc, ApiException) and exc.status == 404:
            return None
        else:
            log.exception('Exception when calling CoreV1Api->list_namespace')
            raise CommandExecutionError(exc)
    finally:
        _cleanup(**cfg)


def deployments(namespace='default', **kwargs):
    '''
    Return a list of kubernetes deployments defined in the namespace

    CLI Examples::

        salt '*' kubernetes.deployments
        salt '*' kubernetes.deployments namespace=default
    '''
    cfg = _setup_conn(**kwargs)
    try:
        api_instance = kubernetes.client.ExtensionsV1beta1Api()
        api_response = api_instance.list_namespaced_deployment(namespace)

        return [dep['metadata']['name'] for dep in api_response.to_dict().get('items')]
    except (ApiException, HTTPError) as exc:
        if isinstance(exc, ApiException) and exc.status == 404:
            return None
        else:
            log.exception(
                'Exception when calling '
                'ExtensionsV1beta1Api->list_namespaced_deployment'
            )
            raise CommandExecutionError(exc)
    finally:
        _cleanup(**cfg)


def services(namespace='default', **kwargs):
    '''
    Return a list of kubernetes services defined in the namespace

    CLI Examples::

        salt '*' kubernetes.services
        salt '*' kubernetes.services namespace=default
    '''
    cfg = _setup_conn(**kwargs)
    try:
        api_instance = kubernetes.client.CoreV1Api()
        api_response = api_instance.list_namespaced_service(namespace)

        return [srv['metadata']['name'] for srv in api_response.to_dict().get('items')]
    except (ApiException, HTTPError) as exc:
        if isinstance(exc, ApiException) and exc.status == 404:
            return None
        else:
            log.exception(
                'Exception when calling '
                'CoreV1Api->list_namespaced_service'
            )
            raise CommandExecutionError(exc)
    finally:
        _cleanup(**cfg)


def pods(namespace='default', **kwargs):
    '''
    Return a list of kubernetes pods defined in the namespace

    CLI Examples::

        salt '*' kubernetes.pods
        salt '*' kubernetes.pods namespace=default
    '''
    cfg = _setup_conn(**kwargs)
    try:
        api_instance = kubernetes.client.CoreV1Api()
        api_response = api_instance.list_namespaced_pod(namespace)

        return [pod['metadata']['name'] for pod in api_response.to_dict().get('items')]
    except (ApiException, HTTPError) as exc:
        if isinstance(exc, ApiException) and exc.status == 404:
            return None
        else:
            log.exception(
                'Exception when calling '
                'CoreV1Api->list_namespaced_pod'
            )
            raise CommandExecutionError(exc)
    finally:
        _cleanup(**cfg)


def secrets(namespace='default', **kwargs):
    '''
    Return a list of kubernetes secrets defined in the namespace

    CLI Examples::

        salt '*' kubernetes.secrets
        salt '*' kubernetes.secrets namespace=default
    '''
    cfg = _setup_conn(**kwargs)
    try:
        api_instance = kubernetes.client.CoreV1Api()
        api_response = api_instance.list_namespaced_secret(namespace)

        return [secret['metadata']['name'] for secret in api_response.to_dict().get('items')]
    except (ApiException, HTTPError) as exc:
        if isinstance(exc, ApiException) and exc.status == 404:
            return None
        else:
            log.exception(
                'Exception when calling '
                'CoreV1Api->list_namespaced_secret'
            )
            raise CommandExecutionError(exc)
    finally:
        _cleanup(**cfg)


def configmaps(namespace='default', **kwargs):
    '''
    Return a list of kubernetes configmaps defined in the namespace

    CLI Examples::

        salt '*' kubernetes.configmaps
        salt '*' kubernetes.configmaps namespace=default
    '''
    cfg = _setup_conn(**kwargs)
    try:
        api_instance = kubernetes.client.CoreV1Api()
        api_response = api_instance.list_namespaced_config_map(namespace)

        return [secret['metadata']['name'] for secret in api_response.to_dict().get('items')]
    except (ApiException, HTTPError) as exc:
        if isinstance(exc, ApiException) and exc.status == 404:
            return None
        else:
            log.exception(
                'Exception when calling '
                'CoreV1Api->list_namespaced_config_map'
            )
            raise CommandExecutionError(exc)
    finally:
        _cleanup(**cfg)


def show_deployment(name, namespace='default', **kwargs):
    '''
    Return the kubernetes deployment defined by name and namespace

    CLI Examples::

        salt '*' kubernetes.show_deployment my-nginx default
        salt '*' kubernetes.show_deployment name=my-nginx namespace=default
    '''
    cfg = _setup_conn(**kwargs)
    try:
        api_instance = kubernetes.client.ExtensionsV1beta1Api()
        api_response = api_instance.read_namespaced_deployment(name, namespace)

        return api_response.to_dict()
    except (ApiException, HTTPError) as exc:
        if isinstance(exc, ApiException) and exc.status == 404:
            return None
        else:
            log.exception(
                'Exception when calling '
                'ExtensionsV1beta1Api->read_namespaced_deployment'
            )
            raise CommandExecutionError(exc)
    finally:
        _cleanup(**cfg)


def show_service(name, namespace='default', **kwargs):
    '''
    Return the kubernetes service defined by name and namespace

    CLI Examples::

        salt '*' kubernetes.show_service my-nginx default
        salt '*' kubernetes.show_service name=my-nginx namespace=default
    '''
    cfg = _setup_conn(**kwargs)
    try:
        api_instance = kubernetes.client.CoreV1Api()
        api_response = api_instance.read_namespaced_service(name, namespace)

        return api_response.to_dict()
    except (ApiException, HTTPError) as exc:
        if isinstance(exc, ApiException) and exc.status == 404:
            return None
        else:
            log.exception(
                'Exception when calling '
                'CoreV1Api->read_namespaced_service'
            )
            raise CommandExecutionError(exc)
    finally:
        _cleanup(**cfg)


def show_pod(name, namespace='default', **kwargs):
    '''
    Return POD information for a given pod name defined in the namespace

    CLI Examples::

        salt '*' kubernetes.show_pod guestbook-708336848-fqr2x
        salt '*' kubernetes.show_pod guestbook-708336848-fqr2x namespace=default
    '''
    cfg = _setup_conn(**kwargs)
    try:
        api_instance = kubernetes.client.CoreV1Api()
        api_response = api_instance.read_namespaced_pod(name, namespace)

        return api_response.to_dict()
    except (ApiException, HTTPError) as exc:
        if isinstance(exc, ApiException) and exc.status == 404:
            return None
        else:
            log.exception(
                'Exception when calling '
                'CoreV1Api->read_namespaced_pod'
            )
            raise CommandExecutionError(exc)
    finally:
        _cleanup(**cfg)


def show_namespace(name, **kwargs):
    '''
    Return information for a given namespace defined by the specified name

    CLI Examples::

        salt '*' kubernetes.show_namespace kube-system
    '''
    cfg = _setup_conn(**kwargs)
    try:
        api_instance = kubernetes.client.CoreV1Api()
        api_response = api_instance.read_namespace(name)

        return api_response.to_dict()
    except (ApiException, HTTPError) as exc:
        if isinstance(exc, ApiException) and exc.status == 404:
            return None
        else:
            log.exception(
                'Exception when calling '
                'CoreV1Api->read_namespace'
            )
            raise CommandExecutionError(exc)
    finally:
        _cleanup(**cfg)


def show_secret(name, namespace='default', decode=False, **kwargs):
    '''
    Return the kubernetes secret defined by name and namespace.
    The secrets can be decoded if specified by the user. Warning: this has
    security implications.

    CLI Examples::

        salt '*' kubernetes.show_secret confidential default
        salt '*' kubernetes.show_secret name=confidential namespace=default
        salt '*' kubernetes.show_secret name=confidential decode=True
    '''
    cfg = _setup_conn(**kwargs)
    try:
        api_instance = kubernetes.client.CoreV1Api()
        api_response = api_instance.read_namespaced_secret(name, namespace)

        if api_response.data and (decode or decode == 'True'):
            for key in api_response.data:
                value = api_response.data[key]
                api_response.data[key] = base64.b64decode(value)

        return api_response.to_dict()
    except (ApiException, HTTPError) as exc:
        if isinstance(exc, ApiException) and exc.status == 404:
            return None
        else:
            log.exception(
                'Exception when calling '
                'CoreV1Api->read_namespaced_secret'
            )
            raise CommandExecutionError(exc)
    finally:
        _cleanup(**cfg)


def show_configmap(name, namespace='default', **kwargs):
    '''
    Return the kubernetes configmap defined by name and namespace.

    CLI Examples::

        salt '*' kubernetes.show_configmap game-config default
        salt '*' kubernetes.show_configmap name=game-config namespace=default
    '''
    cfg = _setup_conn(**kwargs)
    try:
        api_instance = kubernetes.client.CoreV1Api()
        api_response = api_instance.read_namespaced_config_map(
            name,
            namespace)

        return api_response.to_dict()
    except (ApiException, HTTPError) as exc:
        if isinstance(exc, ApiException) and exc.status == 404:
            return None
        else:
            log.exception(
                'Exception when calling '
                'CoreV1Api->read_namespaced_config_map'
            )
            raise CommandExecutionError(exc)
    finally:
        _cleanup(**cfg)


def delete_deployment(name, namespace='default', **kwargs):
    '''
    Deletes the kubernetes deployment defined by name and namespace

    CLI Examples::

        salt '*' kubernetes.delete_deployment my-nginx
        salt '*' kubernetes.delete_deployment name=my-nginx namespace=default
    '''
    cfg = _setup_conn(**kwargs)
    body = kubernetes.client.V1DeleteOptions(orphan_dependents=True)

    try:
        api_instance = kubernetes.client.ExtensionsV1beta1Api()
        api_response = api_instance.delete_namespaced_deployment(
            name=name,
            namespace=namespace,
            body=body)
        mutable_api_response = api_response.to_dict()
        if not salt.utils.platform.is_windows():
            try:
                with _time_limit(POLLING_TIME_LIMIT):
                    while show_deployment(name, namespace) is not None:
                        sleep(1)
                    else:  # pylint: disable=useless-else-on-loop
                        mutable_api_response['code'] = 200
            except TimeoutError:
                pass
        else:
            # Windows has not signal.alarm implementation, so we are just falling
            # back to loop-counting.
            for i in range(60):
                if show_deployment(name, namespace) is None:
                    mutable_api_response['code'] = 200
                    break
                else:
                    sleep(1)
        if mutable_api_response['code'] != 200:
            log.warning('Reached polling time limit. Deployment is not yet '
                        'deleted, but we are backing off. Sorry, but you\'ll '
                        'have to check manually.')
        return mutable_api_response
    except (ApiException, HTTPError) as exc:
        if isinstance(exc, ApiException) and exc.status == 404:
            return None
        else:
            log.exception(
                'Exception when calling '
                'ExtensionsV1beta1Api->delete_namespaced_deployment'
            )
            raise CommandExecutionError(exc)
    finally:
        _cleanup(**cfg)


def delete_service(name, namespace='default', **kwargs):
    '''
    Deletes the kubernetes service defined by name and namespace

    CLI Examples::

        salt '*' kubernetes.delete_service my-nginx default
        salt '*' kubernetes.delete_service name=my-nginx namespace=default
    '''
    cfg = _setup_conn(**kwargs)

    try:
        api_instance = kubernetes.client.CoreV1Api()
        api_response = api_instance.delete_namespaced_service(
            name=name,
            namespace=namespace)

        return api_response.to_dict()
    except (ApiException, HTTPError) as exc:
        if isinstance(exc, ApiException) and exc.status == 404:
            return None
        else:
            log.exception(
                'Exception when calling CoreV1Api->delete_namespaced_service'
            )
            raise CommandExecutionError(exc)
    finally:
        _cleanup(**cfg)


def delete_pod(name, namespace='default', **kwargs):
    '''
    Deletes the kubernetes pod defined by name and namespace

    CLI Examples::

        salt '*' kubernetes.delete_pod guestbook-708336848-5nl8c default
        salt '*' kubernetes.delete_pod name=guestbook-708336848-5nl8c namespace=default
    '''
    cfg = _setup_conn(**kwargs)
    body = kubernetes.client.V1DeleteOptions(orphan_dependents=True)

    try:
        api_instance = kubernetes.client.CoreV1Api()
        api_response = api_instance.delete_namespaced_pod(
            name=name,
            namespace=namespace,
            body=body)

        return api_response.to_dict()
    except (ApiException, HTTPError) as exc:
        if isinstance(exc, ApiException) and exc.status == 404:
            return None
        else:
            log.exception(
                'Exception when calling '
                'CoreV1Api->delete_namespaced_pod'
            )
            raise CommandExecutionError(exc)
    finally:
        _cleanup(**cfg)


def delete_namespace(name, **kwargs):
    '''
    Deletes the kubernetes namespace defined by name

    CLI Examples::

        salt '*' kubernetes.delete_namespace salt
        salt '*' kubernetes.delete_namespace name=salt
    '''
    cfg = _setup_conn(**kwargs)
    body = kubernetes.client.V1DeleteOptions(orphan_dependents=True)

    try:
        api_instance = kubernetes.client.CoreV1Api()
        api_response = api_instance.delete_namespace(name=name, body=body)
        return api_response.to_dict()
    except (ApiException, HTTPError) as exc:
        if isinstance(exc, ApiException) and exc.status == 404:
            return None
        else:
            log.exception(
                'Exception when calling '
                'CoreV1Api->delete_namespace'
            )
            raise CommandExecutionError(exc)
    finally:
        _cleanup(**cfg)


def delete_secret(name, namespace='default', **kwargs):
    '''
    Deletes the kubernetes secret defined by name and namespace

    CLI Examples::

        salt '*' kubernetes.delete_secret confidential default
        salt '*' kubernetes.delete_secret name=confidential namespace=default
    '''
    cfg = _setup_conn(**kwargs)
    body = kubernetes.client.V1DeleteOptions(orphan_dependents=True)

    try:
        api_instance = kubernetes.client.CoreV1Api()
        api_response = api_instance.delete_namespaced_secret(
            name=name,
            namespace=namespace,
            body=body)

        return api_response.to_dict()
    except (ApiException, HTTPError) as exc:
        if isinstance(exc, ApiException) and exc.status == 404:
            return None
        else:
            log.exception(
                'Exception when calling CoreV1Api->delete_namespaced_secret'
            )
            raise CommandExecutionError(exc)
    finally:
        _cleanup(**cfg)


def delete_configmap(name, namespace='default', **kwargs):
    '''
    Deletes the kubernetes configmap defined by name and namespace

    CLI Examples::

        salt '*' kubernetes.delete_configmap settings default
        salt '*' kubernetes.delete_configmap name=settings namespace=default
    '''
    cfg = _setup_conn(**kwargs)
    body = kubernetes.client.V1DeleteOptions(orphan_dependents=True)

    try:
        api_instance = kubernetes.client.CoreV1Api()
        api_response = api_instance.delete_namespaced_config_map(
            name=name,
            namespace=namespace,
            body=body)

        return api_response.to_dict()
    except (ApiException, HTTPError) as exc:
        if isinstance(exc, ApiException) and exc.status == 404:
            return None
        else:
            log.exception(
                'Exception when calling '
                'CoreV1Api->delete_namespaced_config_map'
            )
            raise CommandExecutionError(exc)
    finally:
        _cleanup(**cfg)


def create_deployment(
        name,
        namespace,
        metadata,
        spec,
        source,
        template,
        saltenv,
        **kwargs):
    '''
    Creates the kubernetes deployment as defined by the user.
    '''
    body = __create_object_body(
        kind='Deployment',
        obj_class=AppsV1beta1Deployment,
        spec_creator=__dict_to_deployment_spec,
        name=name,
        namespace=namespace,
        metadata=metadata,
        spec=spec,
        source=source,
        template=template,
        saltenv=saltenv)

    cfg = _setup_conn(**kwargs)

    try:
        api_instance = kubernetes.client.ExtensionsV1beta1Api()
        api_response = api_instance.create_namespaced_deployment(
            namespace, body)

        return api_response.to_dict()
    except (ApiException, HTTPError) as exc:
        if isinstance(exc, ApiException) and exc.status == 404:
            return None
        else:
            log.exception(
                'Exception when calling '
                'ExtensionsV1beta1Api->create_namespaced_deployment'
            )
            raise CommandExecutionError(exc)
    finally:
        _cleanup(**cfg)


def create_pod(
        name,
        namespace,
        metadata,
        spec,
        source,
        template,
        saltenv,
        **kwargs):
    '''
    Creates the kubernetes deployment as defined by the user.
    '''
    body = __create_object_body(
        kind='Pod',
        obj_class=kubernetes.client.V1Pod,
        spec_creator=__dict_to_pod_spec,
        name=name,
        namespace=namespace,
        metadata=metadata,
        spec=spec,
        source=source,
        template=template,
        saltenv=saltenv)

    cfg = _setup_conn(**kwargs)

    try:
        api_instance = kubernetes.client.CoreV1Api()
        api_response = api_instance.create_namespaced_pod(
            namespace, body)

        return api_response.to_dict()
    except (ApiException, HTTPError) as exc:
        if isinstance(exc, ApiException) and exc.status == 404:
            return None
        else:
            log.exception(
                'Exception when calling '
                'CoreV1Api->create_namespaced_pod'
            )
            raise CommandExecutionError(exc)
    finally:
        _cleanup(**cfg)


def create_service(
        name,
        namespace,
        metadata,
        spec,
        source,
        template,
        saltenv,
        **kwargs):
    '''
    Creates the kubernetes service as defined by the user.
    '''
    body = __create_object_body(
        kind='Service',
        obj_class=kubernetes.client.V1Service,
        spec_creator=__dict_to_service_spec,
        name=name,
        namespace=namespace,
        metadata=metadata,
        spec=spec,
        source=source,
        template=template,
        saltenv=saltenv)

    cfg = _setup_conn(**kwargs)

    try:
        api_instance = kubernetes.client.CoreV1Api()
        api_response = api_instance.create_namespaced_service(
            namespace, body)

        return api_response.to_dict()
    except (ApiException, HTTPError) as exc:
        if isinstance(exc, ApiException) and exc.status == 404:
            return None
        else:
            log.exception(
                'Exception when calling '
                'CoreV1Api->create_namespaced_service'
            )
            raise CommandExecutionError(exc)
    finally:
        _cleanup(**cfg)


def create_secret(
        name,
        namespace='default',
        data=None,
        source=None,
        template=None,
        saltenv='base',
        **kwargs):
    '''
    Creates the kubernetes secret as defined by the user.

    CLI Examples::

        salt 'minion1' kubernetes.create_secret \
            passwords default '{"db": "letmein"}'

        salt 'minion2' kubernetes.create_secret \
            name=passwords namespace=default data='{"db": "letmein"}'
    '''
    if source:
        data = __read_and_render_yaml_file(source, template, saltenv)
    elif data is None:
        data = {}

    data = __enforce_only_strings_dict(data)

    # encode the secrets using base64 as required by kubernetes
    for key in data:
        data[key] = base64.b64encode(data[key])

    body = kubernetes.client.V1Secret(
        metadata=__dict_to_object_meta(name, namespace, {}),
        data=data)

    cfg = _setup_conn(**kwargs)

    try:
        api_instance = kubernetes.client.CoreV1Api()
        api_response = api_instance.create_namespaced_secret(
            namespace, body)

        return api_response.to_dict()
    except (ApiException, HTTPError) as exc:
        if isinstance(exc, ApiException) and exc.status == 404:
            return None
        else:
            log.exception(
                'Exception when calling '
                'CoreV1Api->create_namespaced_secret'
            )
            raise CommandExecutionError(exc)
    finally:
        _cleanup(**cfg)


def create_configmap(
        name,
        namespace,
        data,
        source=None,
        template=None,
        saltenv='base',
        **kwargs):
    '''
    Creates the kubernetes configmap as defined by the user.

    CLI Examples::

        salt 'minion1' kubernetes.create_configmap \
            settings default '{"example.conf": "# example file"}'

        salt 'minion2' kubernetes.create_configmap \
            name=settings namespace=default data='{"example.conf": "# example file"}'
    '''
    if source:
        data = __read_and_render_yaml_file(source, template, saltenv)
    elif data is None:
        data = {}

    data = __enforce_only_strings_dict(data)

    body = kubernetes.client.V1ConfigMap(
        metadata=__dict_to_object_meta(name, namespace, {}),
        data=data)

    cfg = _setup_conn(**kwargs)

    try:
        api_instance = kubernetes.client.CoreV1Api()
        api_response = api_instance.create_namespaced_config_map(
            namespace, body)

        return api_response.to_dict()
    except (ApiException, HTTPError) as exc:
        if isinstance(exc, ApiException) and exc.status == 404:
            return None
        else:
            log.exception(
                'Exception when calling '
                'CoreV1Api->create_namespaced_config_map'
            )
            raise CommandExecutionError(exc)
    finally:
        _cleanup(**cfg)


def create_namespace(
        name,
        **kwargs):
    '''
    Creates a namespace with the specified name.

    CLI Example:
        salt '*' kubernetes.create_namespace salt
        salt '*' kubernetes.create_namespace name=salt
    '''

    meta_obj = kubernetes.client.V1ObjectMeta(name=name)
    body = kubernetes.client.V1Namespace(metadata=meta_obj)
    body.metadata.name = name

    cfg = _setup_conn(**kwargs)

    try:
        api_instance = kubernetes.client.CoreV1Api()
        api_response = api_instance.create_namespace(body)

        return api_response.to_dict()
    except (ApiException, HTTPError) as exc:
        if isinstance(exc, ApiException) and exc.status == 404:
            return None
        else:
            log.exception(
                'Exception when calling '
                'CoreV1Api->create_namespace'
            )
            raise CommandExecutionError(exc)
    finally:
        _cleanup(**cfg)


def replace_deployment(name,
                       metadata,
                       spec,
                       source,
                       template,
                       saltenv,
                       namespace='default',
                       **kwargs):
    '''
    Replaces an existing deployment with a new one defined by name and
    namespace, having the specificed metadata and spec.
    '''
    body = __create_object_body(
        kind='Deployment',
        obj_class=AppsV1beta1Deployment,
        spec_creator=__dict_to_deployment_spec,
        name=name,
        namespace=namespace,
        metadata=metadata,
        spec=spec,
        source=source,
        template=template,
        saltenv=saltenv)

    cfg = _setup_conn(**kwargs)

    try:
        api_instance = kubernetes.client.ExtensionsV1beta1Api()
        api_response = api_instance.replace_namespaced_deployment(
            name, namespace, body)

        return api_response.to_dict()
    except (ApiException, HTTPError) as exc:
        if isinstance(exc, ApiException) and exc.status == 404:
            return None
        else:
            log.exception(
                'Exception when calling '
                'ExtensionsV1beta1Api->replace_namespaced_deployment'
            )
            raise CommandExecutionError(exc)
    finally:
        _cleanup(**cfg)


def replace_service(name,
                    metadata,
                    spec,
                    source,
                    template,
                    old_service,
                    saltenv,
                    namespace='default',
                    **kwargs):
    '''
    Replaces an existing service with a new one defined by name and namespace,
    having the specificed metadata and spec.
    '''
    body = __create_object_body(
        kind='Service',
        obj_class=kubernetes.client.V1Service,
        spec_creator=__dict_to_service_spec,
        name=name,
        namespace=namespace,
        metadata=metadata,
        spec=spec,
        source=source,
        template=template,
        saltenv=saltenv)

    # Some attributes have to be preserved
    # otherwise exceptions will be thrown
    body.spec.cluster_ip = old_service['spec']['cluster_ip']
    body.metadata.resource_version = old_service['metadata']['resource_version']

    cfg = _setup_conn(**kwargs)

    try:
        api_instance = kubernetes.client.CoreV1Api()
        api_response = api_instance.replace_namespaced_service(
            name, namespace, body)

        return api_response.to_dict()
    except (ApiException, HTTPError) as exc:
        if isinstance(exc, ApiException) and exc.status == 404:
            return None
        else:
            log.exception(
                'Exception when calling '
                'CoreV1Api->replace_namespaced_service'
            )
            raise CommandExecutionError(exc)
    finally:
        _cleanup(**cfg)


def replace_secret(name,
                   data,
                   source=None,
                   template=None,
                   saltenv='base',
                   namespace='default',
                   **kwargs):
    '''
    Replaces an existing secret with a new one defined by name and namespace,
    having the specificed data.

    CLI Examples::

        salt 'minion1' kubernetes.replace_secret \
            name=passwords data='{"db": "letmein"}'

        salt 'minion2' kubernetes.replace_secret \
            name=passwords namespace=saltstack data='{"db": "passw0rd"}'
    '''
    if source:
        data = __read_and_render_yaml_file(source, template, saltenv)
    elif data is None:
        data = {}

    data = __enforce_only_strings_dict(data)

    # encode the secrets using base64 as required by kubernetes
    for key in data:
        data[key] = base64.b64encode(data[key])

    body = kubernetes.client.V1Secret(
        metadata=__dict_to_object_meta(name, namespace, {}),
        data=data)

    cfg = _setup_conn(**kwargs)

    try:
        api_instance = kubernetes.client.CoreV1Api()
        api_response = api_instance.replace_namespaced_secret(
            name, namespace, body)

        return api_response.to_dict()
    except (ApiException, HTTPError) as exc:
        if isinstance(exc, ApiException) and exc.status == 404:
            return None
        else:
            log.exception(
                'Exception when calling '
                'CoreV1Api->replace_namespaced_secret'
            )
            raise CommandExecutionError(exc)
    finally:
        _cleanup(**cfg)


def replace_configmap(name,
                      data,
                      source=None,
                      template=None,
                      saltenv='base',
                      namespace='default',
                      **kwargs):
    '''
    Replaces an existing configmap with a new one defined by name and
    namespace with the specified data.

    CLI Examples::

        salt 'minion1' kubernetes.replace_configmap \
            settings default '{"example.conf": "# example file"}'

        salt 'minion2' kubernetes.replace_configmap \
            name=settings namespace=default data='{"example.conf": "# example file"}'
    '''
    if source:
        data = __read_and_render_yaml_file(source, template, saltenv)

    data = __enforce_only_strings_dict(data)

    body = kubernetes.client.V1ConfigMap(
        metadata=__dict_to_object_meta(name, namespace, {}),
        data=data)

    cfg = _setup_conn(**kwargs)

    try:
        api_instance = kubernetes.client.CoreV1Api()
        api_response = api_instance.replace_namespaced_config_map(
            name, namespace, body)

        return api_response.to_dict()
    except (ApiException, HTTPError) as exc:
        if isinstance(exc, ApiException) and exc.status == 404:
            return None
        else:
            log.exception(
                'Exception when calling '
                'CoreV1Api->replace_namespaced_configmap'
            )
            raise CommandExecutionError(exc)
    finally:
        _cleanup(**cfg)


def __create_object_body(kind,
                         obj_class,
                         spec_creator,
                         name,
                         namespace,
                         metadata,
                         spec,
                         source,
                         template,
                         saltenv):
    '''
    Create a Kubernetes Object body instance.
    '''
    if source:
        src_obj = __read_and_render_yaml_file(source, template, saltenv)
        if (
                not isinstance(src_obj, dict) or
                'kind' not in src_obj or
                src_obj['kind'] != kind):
            raise CommandExecutionError(
                'The source file should define only '
                'a {0} object'.format(kind))

        if 'metadata' in src_obj:
            metadata = src_obj['metadata']
        if 'spec' in src_obj:
            spec = src_obj['spec']

    return obj_class(
        metadata=__dict_to_object_meta(name, namespace, metadata),
        spec=spec_creator(spec))


def __read_and_render_yaml_file(source,
                                template,
                                saltenv):
    '''
    Read a yaml file and, if needed, renders that using the specifieds
    templating. Returns the python objects defined inside of the file.
    '''
    sfn = __salt__['cp.cache_file'](source, saltenv)
    if not sfn:
        raise CommandExecutionError(
            'Source file \'{0}\' not found'.format(source))

    with salt.utils.files.fopen(sfn, 'r') as src:
        contents = src.read()

        if template:
            if template in salt.utils.templates.TEMPLATE_REGISTRY:
                # TODO: should we allow user to set also `context` like  # pylint: disable=fixme
                # `file.managed` does?
                # Apply templating
                data = salt.utils.templates.TEMPLATE_REGISTRY[template](
                    contents,
                    from_str=True,
                    to_str=True,
                    saltenv=saltenv,
                    grains=__grains__,
                    pillar=__pillar__,
                    salt=__salt__,
                    opts=__opts__)

                if not data['result']:
                    # Failed to render the template
                    raise CommandExecutionError(
                        'Failed to render file path with error: '
                        '{0}'.format(data['data'])
                    )

                contents = data['data'].encode('utf-8')
            else:
                raise CommandExecutionError(
                    'Unknown template specified: {0}'.format(
                        template))

        return salt.utils.yaml.safe_load(contents)


def __dict_to_object_meta(name, namespace, metadata):
    '''
    Converts a dictionary into kubernetes ObjectMetaV1 instance.
    '''
    meta_obj = kubernetes.client.V1ObjectMeta()
    meta_obj.namespace = namespace

    # Replicate `kubectl [create|replace|apply] --record`
    if 'annotations' not in metadata:
        metadata['annotations'] = {}
    if 'kubernetes.io/change-cause' not in metadata['annotations']:
        metadata['annotations']['kubernetes.io/change-cause'] = ' '.join(sys.argv)

    for key, value in iteritems(metadata):
        if hasattr(meta_obj, key):
            setattr(meta_obj, key, value)

    if meta_obj.name != name:
        log.warning(
            'The object already has a name attribute, overwriting it with '
            'the one defined inside of salt')
        meta_obj.name = name

    return meta_obj


def __dict_to_deployment_spec(spec):
    '''
    Converts a dictionary into kubernetes AppsV1beta1DeploymentSpec instance.
    '''
    spec_obj = AppsV1beta1DeploymentSpec()
    for key, value in iteritems(spec):
        if hasattr(spec_obj, key):
            setattr(spec_obj, key, value)

    return spec_obj


def __dict_to_pod_spec(spec):
    '''
    Converts a dictionary into kubernetes V1PodSpec instance.
    '''
    spec_obj = kubernetes.client.V1PodSpec()
    for key, value in iteritems(spec):
        if hasattr(spec_obj, key):
            setattr(spec_obj, key, value)

    return spec_obj


def __dict_to_service_spec(spec):
    '''
    Converts a dictionary into kubernetes V1ServiceSpec instance.
    '''
    spec_obj = kubernetes.client.V1ServiceSpec()
    for key, value in iteritems(spec):  # pylint: disable=too-many-nested-blocks
        if key == 'ports':
            spec_obj.ports = []
            for port in value:
                kube_port = kubernetes.client.V1ServicePort()
                if isinstance(port, dict):
                    for port_key, port_value in iteritems(port):
                        if hasattr(kube_port, port_key):
                            setattr(kube_port, port_key, port_value)
                else:
                    kube_port.port = port
                spec_obj.ports.append(kube_port)
        elif hasattr(spec_obj, key):
            setattr(spec_obj, key, value)

    return spec_obj


def __enforce_only_strings_dict(dictionary):
    '''
    Returns a dictionary that has string keys and values.
    '''
    ret = {}

    for key, value in iteritems(dictionary):
        ret[six.text_type(key)] = six.text_type(value)

    return ret
