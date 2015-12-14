# -*- coding: utf-8 -*-
'''
Connection module for Amazon APIGateway

.. versionadded::

:configuration: This module accepts explicit Lambda credentials but can also
    utilize IAM roles assigned to the instance trough Instance Profiles.
    Dynamic credentials are then automatically obtained from AWS API and no
    further configuration is necessary. More Information available at:

    .. code-block:: text

        http://docs.aws.amazon.com/AWSEC2/latest/UserGuide/iam-roles-for-amazon-ec2.html

    If IAM roles are not used you need to specify them either in a pillar or
    in the minion's config file:

    .. code-block:: yaml

        apigateway.keyid: GKTADJGHEIQSXMKKRBJ08H
        apigateway.key: askdjghsdfjkghWupUjasdflkdfklgjsdfjajkghs

    A region may also be specified in the configuration:

    .. code-block:: yaml

        apigateway.region: us-west-2

    If a region is not specified, the default is us-east-1.

    It's also possible to specify key, keyid and region via a profile, either
    as a passed in dict, or as a string to pull from pillars or minion config:

    .. code-block:: yaml

        myprofile:
            keyid: GKTADJGHEIQSXMKKRBJ08H
            key: askdjghsdfjkghWupUjasdflkdfklgjsdfjajkghs
            region: us-west-2

.. versionchanged:: 2015.8.0
    All methods now return a dictionary. Create and delete methods return:

    .. code-block:: yaml

        created: true

    or

    .. code-block:: yaml

        created: false
        error:
          message: error message

    Request methods (e.g., `describe_apigateway`) return:

    .. code-block:: yaml

        apigateway:
          - {...}
          - {...}

    or

    .. code-block:: yaml

        error:
          message: error message

:depends: boto3

'''
# keep lint from choking on _get_conn and _cache_id
#pylint: disable=E0602

# Import Python libs
from __future__ import absolute_import
import logging
import string
import json
import datetime
from distutils.version import LooseVersion as _LooseVersion  # pylint: disable=import-error,no-name-in-module

# Import Salt libs
import salt.utils.boto3
import salt.utils.compat
from salt.exceptions import SaltInvocationError, CommandExecutionError

log = logging.getLogger(__name__)

# Import third party libs
import salt.ext.six as six
#pylint: disable=import-error
try:
    #pylint: disable=unused-import
    import boto
    import boto3
    #pylint: enable=unused-import
    from botocore.exceptions import ClientError
    logging.getLogger('boto').setLevel(logging.CRITICAL)
    logging.getLogger('boto3').setLevel(logging.CRITICAL)
    HAS_BOTO = True
except ImportError:
    HAS_BOTO = False
# pylint: enable=import-error

def __virtual__():
    '''
    Only load if boto libraries exist and if boto libraries are greater than
    a given version.
    '''
    required_boto_version = '2.8.0'
    required_boto3_version = '1.2.1'
    # the boto_apigateway execution module relies on the connect_to_region() method
    # which was added in boto 2.8.0
    # https://github.com/boto/boto/commit/33ac26b416fbb48a60602542b4ce15dcc7029f12
    if not HAS_BOTO:
        return False
    elif _LooseVersion(boto.__version__) < _LooseVersion(required_boto_version):
        return False
    elif _LooseVersion(boto3.__version__) < _LooseVersion(required_boto3_version):
        return False
    else:
        return True


def __init__(opts):
    salt.utils.compat.pack_dunder(__name__)
    if HAS_BOTO:
        __utils__['boto3.assign_funcs'](__name__, 'apigateway')


def _convert_datetime_str(response):
    '''
    modify any key-value pair where value is a datetime object to a string.
    '''
    if response:
        return dict([(k, '{0}'.format(v)) if isinstance(v, datetime.date) else (k, v) for k, v in response.iteritems()])
    return None

def _filter_apis(name, apis):
    '''
    Return list of api items matching the given name.
    '''
    return [api for api in apis if api['name'] == name]

def _filter_apis_desc(desc, apis):
    '''
    Return list of api items matching the given description.
    '''
    return [api for api in apis if api['description'] == desc]

def _multi_call(function, contentkey, *args, **kwargs):
    '''
    Retrieve full list of values for the contentkey from a boto3 ApiGateway
    client function that may be paged via 'position'
    '''
    ret = function(*args, **kwargs)
    position = ret.get('position')

    while position:
        more = function(*args, position=position, **kwargs)
        ret[contentkey].extend(more[contentkey])
        position = more.get('position')
    return ret.get(contentkey)

def _find_apis_by_name(name, description=None,
                       region=None, key=None, keyid=None, profile=None):

    '''
    get and return list of matching rest api information by the given name and desc.
    If rest api name evaluates to False, return all apis w/o filtering the name.
    '''
    try:
        conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
        apis = _multi_call(conn.get_rest_apis, 'items')
        if name:
            apis = _filter_apis(name, apis)
        if description != None:
            apis = _filter_apis_desc(description, apis)
        return {'restapi': [_convert_datetime_str(api) for api in apis]}
    except ClientError as e:
        return {'error': salt.utils.boto3.get_error(e)}

def describe_apis(name=None, description=None, region=None, key=None, keyid=None, profile=None):

    '''
    Returns all rest apis in the defined region.  If optional parameter name is included,
    returns all rest apis matching the name in the defined region.

    CLI Example:

    .. code-block:: bash

        salt myminion boto_apigateway.describe_apis

        salt myminion boto_apigateway.describe_apis name='api name'

        salt myminion boto_apigateway.describe_apis name='api name' description='desc str'

    '''

    if name:
        return _find_apis_by_name(name, description=description,
                                  region=region, key=key, keyid=keyid, profile=profile)
    else:
        return _find_apis_by_name('', description=description,
                                  region=region, key=key, keyid=keyid, profile=profile)

def api_exists(name, description=None, region=None, key=None, keyid=None, profile=None):
    '''
    Check to see if the given Rest API Name and optionlly description exists.

    CLI Example:

    .. code-block:: bash

        salt myminion boto_apigateway.exists myapi_name

    '''
    apis = _find_apis_by_name(name, description=description,
                              region=region, key=key, keyid=keyid, profile=profile)
    return {'exists': bool(apis.get('restapi'))}


def create_api(name, description, cloneFrom=None,
               region=None, key=None, keyid=None, profile=None):
    '''
    Create a new REST API Service with the given name

    Returns {created: True} if the rest api was created and returns
    {created: False} if the rest api was not created.

    CLI Example:

    .. code-block:: bash

        salt myminion boto_apigateway.create_api myapi_name api_description

    '''
    try:
        conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
        if cloneFrom:
            api = conn.create_rest_api(name=name, description=description, cloneFrom=cloneFrom)
        else:
            api = conn.create_rest_api(name=name, description=description)
        api = _convert_datetime_str(api)
        return {'created': True, 'restapi': api} if api else {'created': False}
    except ClientError as e:
        return {'created': False, 'error': salt.utils.boto3.get_error(e)}


def delete_api(name, description=None, region=None, key=None, keyid=None, profile=None):
    '''
    Delete all REST API Service with the given name and an optional API description

    Returns {deleted: True, count: deleted_count} if apis were deleted, and
    returns {deleted: False} if error or not found.

    CLI Example:

    .. code-block:: bash

        salt myminion boto_apigateway.delete_api myapi_name

        salt myminion boto_apigateway.delete_api myapi_name description='api description'

    '''
    try:
        r = _find_apis_by_name(name, description=description,
                              region=region, key=key, keyid=keyid, profile=profile)
        apis = r.get('restapi')
        if apis:
            conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
            for api in apis:
                conn.delete_rest_api(restApiId=api['id'])
            return {'deleted': True, 'count': len(apis)}
        else:
            return {'deleted': False}
    except ClientError as e:
        return {'deleted': False, 'error': salt.utils.boto3.get_error(e)}

# rest api resource
def describe_api_resources(restApiId, region=None, key=None, keyid=None, profile=None):
    '''
    Given rest api id, return all resources for this api.

    CLI Example:

    .. code-block:: bash

        salt myminion boto_apigateway.describe_api_resources myapi_id

    '''
    try:
        conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
        resources = sorted(_multi_call(conn.get_resources, 'items', restApiId=restApiId),
                           key=lambda k: k['path'])

        return {'resources': resources}
    except ClientError as e:
        return {'error': salt.utils.boto3.get_error(e)}

def describe_api_resource(restApiId, path,
                          region=None, key=None, keyid=None, profile=None):
    '''
    Given rest api id, and an absolute resource path, returns the resource id for
    the given path.

    CLI Example:

    .. code-block:: bash

        salt myminion boto_apigateway.describe_api_resource myapi_id resource_path

    '''
    r = describe_api_resources(restApiId, region=region, key=key, keyid=keyid, profile=profile)
    resources = r.get('resources')
    if not resources:
        return r
    for resource in resources:
        if resource['path'] == path:
            return {'resource': resource}
    return {'resource': None}

def create_api_resources(restApiId, path,
                         region=None, key=None, keyid=None, profile=None):
    '''
    Given rest api id, and an absolute resource path, create all the resources and
    return all resources in the resourcepath, returns False on failure.

    CLI Example:

    .. code-block:: bash

        salt myminion boto_apigateway.create_api_resources myapi_id resource_path

    '''
    path_parts = string.split(path, '/')
    created = []
    current_path = ''
    try:
        conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
        for path_part in path_parts:
            current_path = '{0}/{1}'.format(current_path, path_part)
            r = describe_api_resource(restApiId, current_path,
                                      region=region, key=key, keyid=keyid, profile=profile)
            resource = r.get('resource')
            if not resource:
                resource = conn.create_resource(restApiId=restApiId, parentId=created[-1]['id'], pathPart=path_part)
            created.append(resource)

        if created:
            return {'created': True, 'restApiId': restApiId, 'resources': created}
        else:
            return {'created': False, 'error': 'unexpected error.'}
    except ClientError as e:
        return {'created': False, 'error': salt.utils.boto3.get_error(e)}


def delete_api_resources(restApiId, path,
                         region=None, key=None, keyid=None, profile=None):
    '''
    Given restApiId and an absolute resource path, delete the resources starting
    from the absoluate resource path.  If resourcepath is the root resource '/',
    the function will return False.  Returns False on failure.

    CLI Example:

    .. code-block:: bash

        salt myminion boto_apigateway.delete_api_resources myapi_id, resource_path

    '''
    if path == '/':
        return {'deleted': False, 'error': 'use delete_api to remove the root resource'}
    try:
        conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
        r = describe_api_resource(restApiId, path, region=region, key=key, keyid=keyid, profile=profile)
        resource = r.get('resource')
        if resource:
            conn.delete_resource(restApiId=restApiId, resourceId=resource['id'])
            return {'deleted': True}
        else:
            return {'deleted': False, 'error': 'no resource found by {0}'.format(path)}
    except ClientError as e:
        return {'created': False, 'error': salt.utils.boto3.get_error(e)}


# resource method
def describe_api_resource_method(restApiId, resourcepath, httpMethod,
                                 region=None, key=None, keyid=None, profile=None):
    '''
    Given rest api id, resource path, and http method (must be one of DELETE,
    GET, HEAD, OPTIONS, PATCH, POST, PUT), return the method for the
    api/resource path if defined.  Return False if method is not defined.

    CLI Example:

    .. code-block:: bash

        salt myminion boto_apigateway.describe_api_resource_method myapi_id resource_path httpmethod

    '''
    r = describe_api_resource(restApiId, resourcepath,
                              region=region, key=key, keyid=keyid, profile=profile)
    resource = r.get('resource')
    if not resource:
        return {'error': 'no such resource'}

    try:
        conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
        method = conn.get_method(restApiId=restApiId, resourceId=resource['id'], httpMethod=httpMethod)
        return {'method': method}
    except ClientError as e:
        return {'error': salt.utils.boto3.get_error(e)}


# API Keys
def describe_api_key(apiKey, region=None, key=None, keyid=None, profile=None):
    '''
    Gets info about the given api key

    CLI Example:

    .. code-block:: bash

        salt myminion boto_apigateway.describe_api_key apigw_api_key

    '''
    try:
        conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
        response = conn.get_api_key(apiKey=apiKey)
        return {'apiKey': _convert_datetime_str(response)}
    except ClientError as e:
        return {'error': salt.utils.boto3.get_error(e)}

def describe_api_keys(region=None, key=None, keyid=None, profile=None):
    '''
    Gets information about the defined API Keys.  Return list of apiKeys.

    CLI Example:

    .. code-block:: bash

        salt myminion boto_apigateway.describe_api_keys

    '''
    try:
        conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
        apikeys = _multi_call(conn.get_api_keys, 'items')

        return {'apiKeys': [_convert_datetime_str(apikey) for apikey in apikeys]}
    except ClientError as e:
        return {'error': salt.utils.boto3.get_error(e)}


def create_api_key(name, description, enabled=True, stageKeys=None,
                   region=None, key=None, keyid=None, profile=None):
    '''
    Create an API key given name and description.

    An optional enabled argument can be provided.  If provided, the
    valid values are True|False.  This argument defaults to True.

    An optional stageKeys argument can be provided in the form of
    list of dictionary with 'restApiId' and 'stageName' as keys.

    CLI Example:

    .. code-block:: bash

        salt myminion boto_apigateway.create_api_key name description

        salt myminion boto_apigateway.create_api_key name description enabled=False

        salt myminion boto_apigateway.create_api_key name description \
             stageKeys='[{"restApiId": "id", "stageName": "stagename"}]'

    '''

    try:
        stageKeys = list() if stageKeys is None else stageKeys

        conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
        response = conn.create_api_key(name=name, description=description,
                                       enabled=enabled, stageKeys=stageKeys)
        if not response:
            return {'created': False}

        return {'created': True, 'apiKey': _convert_datetime_str(response)}
    except ClientError as e:
        return {'created': False, 'error': salt.utils.boto3.get_error(e)}

def delete_api_key(apiKey, region=None, key=None, keyid=None, profile=None):
    '''
    Deletes a given apiKey

    CLI Example:

    .. code_block:: bash

        salt myminion boto_apigateway.delete_api_key apikeystring

    '''
    try:
        conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
        conn.delete_api_key(apiKey=apiKey)
        return {'deleted': True}
    except ClientError as e:
        return {'deleted': False, 'error': salt.utils.boto3.get_error(e)}

def _api_key_patch_replace(conn, apiKey, path, value):
    '''
    the replace patch operation on an ApiKey resource
    '''
    response = conn.update_api_key(apiKey=apiKey,
                                   patchOperations=[{'op': 'replace', 'path': path, 'value': value}])
    return response

def _api_key_patchops(op, pvlist):
    '''
    helper function to return patchOperations object
    '''
    return [{'op': op, 'path': p, 'value': v} for (p, v) in pvlist]

def _api_key_patch_add(conn, apiKey, pvlist):
    '''
    the add patch operation for a list of (path, value) tuples on an ApiKey resource list path
    '''
    response = conn.update_api_key(apiKey=apiKey,
                                   patchOperations=_api_key_patchops('add', pvlist))
    return response

def _api_key_patch_remove(conn, apiKey, pvlist):
    '''
    the remove patch operation for a list of (path, value) tuples on an ApiKey resource list path
    '''
    response = conn.update_api_key(apiKey=apiKey,
                                   patchOperations=_api_key_patchops('remove', pvlist))
    return response


def update_api_key_description(apiKey, description, region=None, key=None, keyid=None, profile=None):
    '''
    update the given apiKey with the given description.

    CLI Example:

    .. code_block:: bash

        salt myminion boto_apigateway.update_api_key_description api_key description

    '''
    try:
        conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
        response = _api_key_patch_replace(conn, apiKey, '/description', description)
        return {'updated': True, 'apiKey': _convert_datetime_str(response)}
    except ClientError as e:
        return {'updated': False, 'error': salt.utils.boto3.get_error(e)}

def enable_api_key(apiKey, region=None, key=None, keyid=None, profile=None):
    '''
    enable the given apiKey.

    CLI Example:

    .. code_block:: bash

        salt myminion boto_apigateway.enable_api_key api_key

    '''
    try:
        conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
        response = _api_key_patch_replace(conn, apiKey, '/enabled', 'True')
        return {'apiKey': _convert_datetime_str(response)}
    except ClientError as e:
        return {'error': salt.utils.boto3.get_error(e)}

def disable_api_key(apiKey, region=None, key=None, keyid=None, profile=None):
    '''
    disable the given apiKey.

    CLI Example:

    .. code_block:: bash

        salt myminion boto_apigateway.enable_api_key api_key

    '''
    try:
        conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
        response = _api_key_patch_replace(conn, apiKey, '/enabled', 'False')
        return {'apiKey': _convert_datetime_str(response)}
    except ClientError as e:
        return {'error': salt.utils.boto3.get_error(e)}


def associate_api_key_stagekeys(apiKey, stagekeyslist, region=None, key=None, keyid=None, profile=None):
    '''
    associate the given stagekeyslist to the given apiKey.

    CLI Example:

    .. code_block:: bash

        salt myminion boto_apigateway.associate_stagekeys_api_key api_key '["restapi id/stage name", ...]'

    '''
    try:
        conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
        pvlist = [('/stages', stagekey) for stagekey in stagekeyslist]
        response = _api_key_patch_add(conn, apiKey, pvlist)
        return {'associated': True, 'apiKey': _convert_datetime_str(response)}
    except ClientError as e:
        return {'associated': False, 'error': salt.utils.boto3.get_error(e)}

def disassociate_api_key_stagekeys(apiKey, stagekeyslist, region=None, key=None, keyid=None, profile=None):
    '''
    disassociate the given stagekeyslist to the given apiKey.

    CLI Example:

    .. code_block:: bash

        salt myminion boto_apigateway.disassociate_stagekeys_api_key api_key '["restapi id/stage name", ...]'

    '''
    try:
        conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
        pvlist = [('/stages', stagekey) for stagekey in stagekeyslist]
        response = _api_key_patch_remove(conn, apiKey, pvlist)
        return {'disassociated': True}
    except ClientError as e:
        return {'disassociated': False, 'error': salt.utils.boto3.get_error(e)}



# API Deployments

def describe_api_deployments(apiId, region=None, key=None, keyid=None, profile=None):
    '''
    Gets information about the defined API Deployments.  Return list of api deployments.

    CLI Example:

    .. code-block:: bash

        salt myminion boto_apigateway.describe_api_deployments apiId

    '''
    try:
        conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
        deployments = []
        _deployments = conn.get_deployments(restApiId=apiId)

        while True:
            if _deployments:
                deployments = deployments + _deployments['items']
                if not _deployments.has_key('position'):
                    break
                _deployments = conn.get_deployments(restApiId=apiId, position=_deployments['position'])

        return {'deployments': [_convert_datetime_str(deployment) for deployment in deployments]}
    except ClientError as e:
        return {'error': salt.utils.boto3.get_error(e)}

def describe_api_deployment(apiId, deploymentId, region=None, key=None, keyid=None, profile=None):
    '''
    Get API deployment for a given apiId and deploymentId.

    CLI Example:

    .. code-block:: bash

        salt myminion boto_apigateway.describe_api_deployent apiId deploymentId

    '''
    try:
        conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
        deployment = conn.get_deployment(restApiId=apiId, deploymentId=deploymentId)
        return {'deployment': _convert_datetime_str(deployment)}
    except ClientError as e:
        return {'error': salt.utils.boto3.get_error(e)}


def create_api_deployment(apiId, stageName, stageDescription='', description='', cacheClusterEnabled=False,
                          cacheClusterSize='0.5', variables=None,
                          region=None, key=None, keyid=None, profile=None):
    '''
    Creates a new API deployment.

    CLI Example:

    .. code-block:: bash

        salt myminion boto_apigateway.create_api_deployent apiId stagename stageDescription='' \
             description='' cacheClusterEnabled=True|False cacheClusterSize=0.5 variables='{"name": "value"}'

    '''
    try:
        variables = dict() if variables is None else variables

        conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
        deployment = conn.create_deployment(restApiId=apiId, stageName=stageName,
                                            stageDescription=stageDescription, description=description,
                                            cacheClusterEnabled=cacheClusterEnabled, cacheClusterSize=cacheClusterSize,
                                            variables=variables)
        return {'created': True, 'deployment': _convert_datetime_str(deployment)}
    except ClientError as e:
        return {'created': False, 'error': salt.utils.boto3.get_error(e)}

def delete_api_deployment(apiId, deploymentId, region=None, key=None, keyid=None, profile=None):
    '''
    Deletes API deployment for a given apiID and deploymentID

    CLI Example:

    .. code-block:: bash

        salt myminion boto_apigateway.delete_api_deployent apiId deploymentId

    '''
    try:
        conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
        response = conn.delete_deployment(restApiId=apiId, deploymentId=deploymentId)
        return {'deleted': True}
    except ClientError as e:
        return {'deleted': False, 'error': salt.utils.boto3.get_error(e)}

# API Stages

def describe_api_stage(apiId, stageName, region=None, key=None, keyid=None, profile=None):
    '''
    Get API stage for a given apiID and stage name

    CLI Example:

    .. code-block:: bash

        salt myminion boto_apigateway.describe_api_stage apiId stageName

    '''
    try:
        conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
        stage = conn.get_stage(restApiId=apiId, stageName=stageName)
        return {'stage': stage}
    except ClientError as e:
        return {'error': salt.utils.boto3.get_error(e)}

def describe_api_stages(apiId, deploymentId, region=None, key=None, keyid=None, profile=None):
    '''
    Get all API stages for a given apiID and deploymentID

    CLI Example:

    .. code-block:: bash

        salt myminion boto_apigateway.describe_api_stages apiId deploymentId

    '''
    try:
        conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
        stages = conn.get_stages(restApiId=apiId, deploymentId=deploymentId)
        return {'stages': [_convert_datetime_str(stage) for stage in stages['item']]}
    except ClientError as e:
        return {'error': salt.utils.boto3.get_error(e)}

def create_api_stage(apiId, stageName, deploymentId, description='',
                     cacheClusterEnabled=False, cacheClusterSize='0.5', variables=None,
                     region=None, key=None, keyid=None, profile=None):
    '''
    Creates a new API stage for a given apiId and deploymentId.

    CLI Example:

    .. code-block:: bash

        salt myminion boto_apigateway.create_api_stage apiId stagename deploymentId \
            description='' cacheClusterEnabled=True|False cacheClusterSize='0.5' variables='{"name": "value"}'

    '''
    try:
        variables = dict() if variables is None else variables

        conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
        stage = conn.create_stage(restApiId=apiId, stageName=stageName, deploymentId=deploymentId,
                                  description=description, cacheClusterEnabled=cacheClusterEnabled,
                                  cacheClusterSize=cacheClusterSize, variables=variables)
        return {'created': True, 'stage': _convert_datetime_str(stage)}
    except ClientError as e:
        return {'created': False, 'error': salt.utils.boto3.get_error(e)}

def delete_api_stage(apiId, stageName, region=None, key=None, keyid=None, profile=None):
    '''
    Deletes stage identified by stageName from API identified by apiId

    CLI Example:

    .. code-block:: bash

        salt myminion boto_apigateway.delete_api_stage apiId stageName

    '''
    try:
        conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
        conn.delete_stage(restApiId=apiId, stageName=stageName)
        return {'deleted': True}
    except ClientError as e:
        return {'deleted': False, 'error': salt.utils.boto3.get_error(e)}

def flush_api_stage_cache(apiId, stageName, region=None, key=None, keyid=None, profile=None):
    '''
    Flushes cache for the stage identified by stageName from API identified by apiId

    CLI Example:

    .. code-block:: bash

        salt myminion boto_apigateway.flush_api_stage_cache apiId stageName

    '''
    try:
        conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
        conn.flush_stage_cache(restApiId=apiId, stageName=stageName)
        return {'flushed': True}
    except ClientError as e:
        return {'flushed': False, 'error': salt.utils.boto3.get_error(e)}


# API Methods

def create_api_method(apiId, resourcePath, httpMethod, authorizationType,
                      apiKeyRequired=False, requestParameters=None, requestModels=None,
                      region=None, key=None, keyid=None, profile=None):
    '''
    Creates API method for a resource in the given API

    CLI Example:

    .. code-block:: bash

        salt myminion boto_apigateway.create_api_method apiId resourcePath, httpMethod, authorizationType, \
            apiKeyRequired=False, requestParameters='{"name", "value"}', requestModels='{"content-type", "value"}'

    '''
    try:
        resource = describe_api_resource(apiId, resourcePath, region=region,
                                         key=key, keyid=keyid, profile=profile).get('resource')
        if resource:
            requestParameters = dict() if requestParameters is None else requestParameters
            requestModels = dict() if requestModels is None else requestModels

            conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
            method = conn.put_method(restApiId=apiId, resourceId=resource['id'], httpMethod=httpMethod,
                                     authorizationType=str(authorizationType), apiKeyRequired=apiKeyRequired,
                                     requestParameters=requestParameters, requestModels=requestModels)
            return {'created': True, 'method': method}
        return {'created': False, 'error': 'Failed to create method'}

    except ClientError as e:
        return {'created': False, 'error': salt.utils.boto3.get_error(e)}

def describe_api_method(apiId, resourcePath, httpMethod, region=None, key=None, keyid=None, profile=None):
    '''
    Get API method for a resource in the given API

    CLI Example:

    .. code-block:: bash

        salt myminion boto_apigateway.describe_api_method apiId resourcePath httpMethod

    '''
    try:
        resource = describe_api_resource(apiId, resourcePath, region=region,
                                         key=key, keyid=keyid, profile=profile).get('resource')
        if resource:
            conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
            method = conn.get_method(restApiId=apiId, resourceId=resource['id'], httpMethod=httpMethod)
            return {'method': _convert_datetime_str(method)}
        return {'error': 'get API method failed: no such resource'}
    except ClientError as e:
        return {'error': salt.utils.boto3.get_error(e)}

def delete_api_method(apiId, resourcePath, httpMethod, region=None, key=None, keyid=None, profile=None):
    '''
    Delete API method for a resource in the given API

    CLI Example:

    .. code-block:: bash

        salt myminion boto_apigateway.delete_api_method apiId resourcePath httpMethod

    '''
    try:
        resource = describe_api_resource(apiId, resourcePath, region=region,
                                         key=key, keyid=keyid, profile=profile).get('resource')
        if resource:
            conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
            method = conn.delete_method(restApiId=apiId, resourceId=resource['id'], httpMethod=httpMethod)
            return {'deleted': True}
        return {'deleted': False, 'error': 'get API method failed: no such resource'}
    except ClientError as e:
        return {'deleted': False, 'error': salt.utils.boto3.get_error(e)}

def create_api_method_response(apiId, resourcePath, httpMethod, statusCode, responseParameters=None,
                               responseModels=None, region=None, key=None, keyid=None, profile=None):
    '''
    Create API method response for a method on a given resource in the given API

    CLI Example:

    .. code-block:: bash

        salt myminion boto_apigateway.create_api_method_response apiId resourcePath httpMethod \
               statusCode responseParameters='{"name", "True|False"}' responseModels='{"content-type", "model"}'

    '''
    try:
        resource = describe_api_resource(apiId, resourcePath, region=region,
                                         key=key, keyid=keyid, profile=profile).get('resource')
        if resource:
            responseParameters = dict() if responseParameters is None else responseParameters
            responseModels = dict() if responseModels is None else responseModels

            conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
            response = conn.put_method_response(restApiId=apiId, resourceId=resource['id'],
                                                httpMethod=httpMethod, statusCode=str(statusCode),
                                                responseParameters=responseParameters, responseModels=responseModels)
            return {'created': True, 'response': response}
        return {'created': False, 'error': 'no such resource'}
    except ClientError as e:
        return {'created': False, 'error': salt.utils.boto3.get_error(e)}


def delete_api_method_response(apiId, resourcePath, httpMethod, statusCode,
                               region=None, key=None, keyid=None, profile=None):
    '''
    Delete API method response for a resource in the given API

    CLI Example:

    .. code-block:: bash

        salt myminion boto_apigateway.delete_api_method_response apiId resourcePath httpMethod statusCode

    '''
    try:
        resource = describe_api_resource(apiId, resourcePath, region=region,
                                         key=key, keyid=keyid, profile=profile).get('resource')
        if resource:
            conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
            conn.delete_method_response(restApiId=apiId, resourceId=resource['id'],
                                        httpMethod=httpMethod, statusCode=str(statusCode))
            return {'deleted': True}
        return {'deleted': False, 'error': 'no such resource'}
    except ClientError as e:
        return {'deleted': False, 'error': salt.utils.boto3.get_error(e)}

def describe_api_method_response(apiId, resourcePath, httpMethod, statusCode,
                                 region=None, key=None, keyid=None, profile=None):
    '''
    Get API method response for a resource in the given API

    CLI Example:

    .. code-block:: bash

        salt myminion boto_apigateway.describe_api_method_response apiId resourcePath httpMethod statusCode

    '''
    try:
        resource = describe_api_resource(apiId, resourcePath, region=region,
                                         key=key, keyid=keyid, profile=profile).get('resource')
        if resource:
            conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
            response = conn.get_method_response(restApiId=apiId, resourceId=resource['id'],
                                                httpMethod=httpMethod, statusCode=str(statusCode))
            return {'response': _convert_datetime_str(response)}
        return {'error': 'no such resource'}
    except ClientError as e:
        return {'error': salt.utils.boto3.get_error(e)}


# API Model

def describe_api_models(restApiId, region=None, key=None, keyid=None, profile=None):
    '''
    Get all models for a given API

    CLI Example:

    .. code-block:: bash

        salt myminion boto_apigateway.describe_api_models apiId

    '''
    try:
        conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
        models = _multi_call(conn.get_models, 'items', restApiId=restApiId)
        return {'models': [_convert_datetime_str(model) for model in models]}
    except ClientError as e:
        return {'error': salt.utils.boto3.get_error(e)}


def describe_api_model(restApiId, modelName, flatten=True, region=None, key=None, keyid=None, profile=None):
    '''
    Get a model by name for a given API

    CLI Example:

    .. code-block:: bash

        salt myminion boto_apigateway.describe_api_model apiId modelName [True]

    '''
    try:
        conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
        model = conn.get_model(restApiId=restApiId, modelName=modelName, flatten=flatten)
        return {'model': _convert_datetime_str(model)}
    except ClientError as e:
        return {'error': salt.utils.boto3.get_error(e)}

def api_model_exists(restApiId, modelName, region=None, key=None, keyid=None, profile=None):
    '''
    Check to see if the given modelName exists in the given apiId

    CLI Example:

    .. code-block:: bash

        salt myminion boto_apigateway.api_model_exists apiId modelName
    '''
    r = describe_api_model(restApiId, modelName, region=region, key=key, keyid=keyid, profile=profile)

    return {'exists': bool(r.get('model'))}

def _api_model_patch_replace(conn, restApiId, modelName, path, value):
    '''
    the replace patch operation on a Model resource
    '''
    response = conn.update_model(restApiId=restApiId, modelName=modelName,
                                 patchOperations=[{'op': 'replace', 'path': path, 'value': value}])
    return response

def update_api_model_schema(restApiId, modelName, schema, region=None, key=None, keyid=None, profile=None):
    '''
    update the schema (in python dictionary format) for the given model in the given restApiId

    CLI Example:

    .. code_block:: bash

        salt myminion boto_apigateway.update_api_model_schema restApiId modelName schema

    '''
    try:
        conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
        response = _api_model_patch_replace(conn, restApiId, modelName, '/schema', json.dumps(schema))
        return {'updated': True, 'model': _convert_datetime_str(response)}
    except ClientError as e:
        return {'updated': False, 'error': salt.utils.boto3.get_error(e)}


def delete_api_model(restApiId, modelName, region=None, key=None, keyid=None, profile=None):
    '''
    Delete a model identified by name in a given API

    CLI Example:

    .. code-block:: bash

        salt myminion boto_apigateway.delete_api_model apiId modelName

    '''
    try:
        conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
        conn.delete_model(restApiId=restApiId, modelName=modelName)
        return {'deleted': True}
    except ClientError as e:
        return {'deleted': False, 'error': salt.utils.boto3.get_error(e)}

def create_api_model(restApiId, modelName, modelDescription, schema, contentType='application/json',
                     region=None, key=None, keyid=None, profile=None):
    '''
    Create a new model in a given API with a given schema, currently only contentType supported is
    'application/json'

    CLI Example:

    .. code-block:: bash

        salt myminion boto_apigateway.create_api_model apiId modelName modelDescription '<schema>' 'content-type'

    '''
    try:
        conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
        model = conn.create_model(restApiId=restApiId, name=modelName, description=modelDescription,
                                  schema=json.dumps(schema), contentType=contentType)
        return {'created': True, 'model': _convert_datetime_str(model)}
    except ClientError as e:
        return {'created': False, 'error': salt.utils.boto3.get_error(e)}

# API Integrations

def describe_api_integration(apiId, resourcePath, httpMethod, region=None, key=None, keyid=None, profile=None):
    '''
    Get an integration for a given method in a given API

    CLI Example:

    .. code-block:: bash

        salt myminion boto_apigateway.describe_api_integration apiId resourcePath httpMethod

    '''
    try:
        resource = describe_api_resource(apiId, resourcePath, region=region,
                                         key=key, keyid=keyid, profile=profile).get('resource')
        if resource:
            conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
            integration = conn.get_integration(restApiId=apiId, resourceId=resource['id'], httpMethod=httpMethod)
            return {'integration': _convert_datetime_str(integration)}
        return {'error': 'no such resource'}
    except ClientError as e:
        return {'error': salt.utils.boto3.get_error(e)}


def describe_api_integration_response(apiId, resourcePath, httpMethod, statusCode,
                                      region=None, key=None, keyid=None, profile=None):
    '''
    Get an integration response for a given method in a given API

    CLI Example:

    .. code-block:: bash

        salt myminion boto_apigateway.describe_api_integration_response apiId resourcePath httpMethod statusCode

    '''
    try:
        resource = describe_api_resource(apiId, resourcePath, region=region,
                                         key=key, keyid=keyid, profile=profile).get('resource')
        if resource:
            conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
            response = conn.get_integration_response(restApiId=apiId, resourceId=resource['id'],
                                                     httpMethod=httpMethod, statusCode=statusCode)
            return {'response': _convert_datetime_str(response)}
        return {'error': 'no such resource'}
    except ClientError as e:
        return {'error': salt.utils.boto3.get_error(e)}

def delete_api_integration(apiId, resourcePath, httpMethod, region=None, key=None, keyid=None, profile=None):
    '''
    Deletes an integration for a given method in a given API

    CLI Example:

    .. code-block:: bash

        salt myminion boto_apigateway.delete_api_integration apiId resourcePath httpMethod

    '''
    try:
        resource = describe_api_resource(apiId, resourcePath, region=region,
                                         key=key, keyid=keyid, profile=profile).get('resource')
        if resource:
            conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
            conn.delete_integration(restApiId=apiId, resourceId=resource['id'], httpMethod=httpMethod)
            return {'deleted': True}
        return {'deleted': False, 'error': 'no such resource'}
    except ClientError as e:
        return {'deleted': False, 'error': salt.utils.boto3.get_error(e)}

def delete_api_integration_response(apiId, resourcePath, httpMethod, statusCode,
                                    region=None, key=None, keyid=None, profile=None):
    '''
    Deletes an integration response for a given method in a given API

    CLI Example:

    .. code-block:: bash

        salt myminion boto_apigateway.delete_api_integration_response apiId resourcePath httpMethod statusCode

    '''
    try:
        resource = describe_api_resource(apiId, resourcePath, region=region,
                                         key=key, keyid=keyid, profile=profile).get('resource')
        if resource:
            conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
            conn.delete_integration_response(restApiId=apiId, resourceId=resource['id'],
                                             httpMethod=httpMethod, statusCode=statusCode)
            return {'deleted': True}
        return {'deleted': False, 'error': 'no such resource'}
    except ClientError as e:
        return {'deleted': False, 'error': salt.utils.boto3.get_error(e)}


def _get_role_arn(name, region=None, key=None, keyid=None, profile=None):
    if name.startswith('arn:aws:iam:'):
        return name

    account_id = __salt__['boto_iam.get_account_id'](
        region=region, key=key, keyid=keyid, profile=profile
    )

    return 'arn:aws:iam::{0}:role/{1}'.format(account_id, name)


def create_api_integration(apiId, resourcePath, httpMethod, integrationType, integrationHttpMethod,
                           uri, credentials, requestParameters=None, requestTemplates=None,
                           region=None, key=None, keyid=None, profile=None):
    '''
    Creates an integration for a given method in a given API.
    If integrationType is MOCK, uri and credential parameters will be ignored.

    uri is in the form of (substitute APIGATEWAY_REGION and LAMBDA_FUNC_ARN)
    "arn:aws:apigateway:APIGATEWAY_REGION:lambda:path/2015-03-31/functions/LAMBDA_FUNC_ARN/invocations"

    credentials is in the form of an iam role name or role arn.

    CLI Example:

    .. code-block:: bash

        salt myminion boto_apigateway.create_api_integration apiId resourcePath httpMethod \
                             integrationType integrationHttpMethod uri credentials ['{}' ['{}']]

    '''
    try:
        credentials = _get_role_arn(credentials, region=region, key=key, keyid=keyid, profile=profile)
        resource = describe_api_resource(apiId, resourcePath, region=region,
                                         key=key, keyid=keyid, profile=profile).get('resource')
        if resource:
            requestParameters = dict() if requestParameters is None else requestParameters
            requestTemplates = dict() if requestTemplates is None else requestTemplates

            conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
            if httpMethod.lower() == 'options':
                uri = ""
                credentials = ""

            integration = conn.put_integration(restApiId=apiId, resourceId=resource['id'], httpMethod=httpMethod,
                                               type=integrationType, integrationHttpMethod=integrationHttpMethod,
                                               uri=uri, credentials=credentials, requestParameters=requestParameters,
                                               requestTemplates=requestTemplates)
            return {'created': True, 'integration': integration}
        return {'created': False, 'error': 'no such resource'}
    except ClientError as e:
        return {'created': False, 'error': salt.utils.boto3.get_error(e)}


def create_api_integration_response(apiId, resourcePath, httpMethod, statusCode, selectionPattern,
                                    responseParameters=None, responseTemplates=None,
                                    region=None, key=None, keyid=None, profile=None):
    '''
    Creates an integration response for a given method in a given API

    CLI Example:

    .. code-block:: bash

        salt myminion boto_apigateway.create_api_integration_response apiId resourcePath httpMethod \
                            statusCode selectionPattern ['{}' ['{}']]

    '''
    try:
        resource = describe_api_resource(apiId, resourcePath, region=region,
                                         key=key, keyid=keyid, profile=profile).get('resource')
        if resource:
            responseParameters = dict() if responseParameters is None else responseParameters
            responseTemplates = dict() if responseTemplates is None else responseTemplates

            conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
            response = conn.put_integration_response(restApiId=apiId, resourceId=resource['id'],
                                                     httpMethod=httpMethod, statusCode=statusCode,
                                                     selectionPattern=selectionPattern,
                                                     responseParameters=responseParameters,
                                                     responseTemplates=responseTemplates)
            return {'created': True, 'response': response}
        return {'created': False, 'error': 'no such resource'}
    except ClientError as e:
        return {'created': False, 'error': salt.utils.boto3.get_error(e)}
