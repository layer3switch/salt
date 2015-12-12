# -*- coding: utf-8 -*-
'''
Manage Apigateway Rest APIs
=================

.. versionadded:: 

Create and destroy rest apis depending on a swagger version 2 definition file. 
Be aware that this interacts with Amazon's services, and so may incur charges.

This module uses ``boto3``, which can be installed via package, or pip.

This module accepts explicit vpc credentials but can also utilize
IAM roles assigned to the instance through Instance Profiles. Dynamic
credentials are then automatically obtained from AWS API and no further
configuration is necessary. More information available `here
<http://docs.aws.amazon.com/AWSEC2/latest/UserGuide/iam-roles-for-amazon-ec2.html>`_.

If IAM roles are not used you need to specify them either in a pillar file or
in the minion's config file:

.. code-block:: yaml

    vpc.keyid: GKTADJGHEIQSXMKKRBJ08H
    vpc.key: askdjghsdfjkghWupUjasdflkdfklgjsdfjajkghs

It's also possible to specify ``key``, ``keyid`` and ``region`` via a profile,
either passed in as a dict, or as a string to pull from pillars or minion
config:

.. code-block:: yaml

    myprofile:
        keyid: GKTADJGHEIQSXMKKRBJ08H
        key: askdjghsdfjkghWupUjasdflkdfklgjsdfjajkghs
            region: us-east-1

.. code-block:: yaml

    Ensure Apigateway API exists:
        boto_apigateway.present:
            - name: myfunction
            - region: us-east-1
            - keyid: GKTADJGHEIQSXMKKRBJ08H
            - key: askdjghsdfjkghWupUjasdflkdfklgjsdfjajkghs

'''

# Import Python Libs
from __future__ import absolute_import
import logging
import os
import os.path
import hashlib
import re

# Import Salt Libs
import salt.utils.dictupdate as dictupdate

# Import 3rd Party Libs
import yaml
import json
import anyconfig


log = logging.getLogger(__name__)

# Helper Swagger Class for swagger version 2.0 API specification
def _gen_md5_filehash(fname):
    hash = hashlib.md5()
    with open(fname, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hash.update(chunk)
    return hash.hexdigest()

def _dict_to_json_pretty(d, sort_keys=True):
    return json.dumps(d, indent=4, separators=(',', ': '), sort_keys=sort_keys)

class ixSwagger(object):
    # SWAGGER_OBJECT_V2_FIELDS
    SWAGGER_OBJECT_V2_FIELDS = ['swagger', 'info', 'host', 'basePath', 'schemes', 'consumes', 'produces',
                                'paths', 'definitions', 'parameters', 'responses', 'securityDefinitions',
                                'security', 'tags', 'externalDocs']

    # SWAGGER OBJECT V2 Fields that are required by boto apigateway states.
    SWAGGER_OBJECT_V2_FIELDS_REQUIRED = ['swagger', 'info', 'basePath', 'schemes', 'paths', 'definitions',
                                         'x-salt-boto-apigateway-version']

    # SWAGGER OPERATION NAMES
    SWAGGER_OPERATION_NAMES = ['get', 'put', 'post', 'delete', 'options', 'head', 'patch']

    # the version we expect to handle for the values for x-salt-boto-apigateway-version
    SALT_BOTO_APIGATEWAY_VERSIONS_SUPPORTED = ['0.0']
    SWAGGER_VERSIONS_SUPPORTED = ['2.0']

    # VENDOR SPECIFIC FIELD PATTERNS
    VENDOR_EXT_PATTERN = re.compile('^x-')
    SALT_BOTO_APIGATEWAY_EXT_PATTERN = re.compile('^x-salt-boto-apigateway-')

    # JSON_SCHEMA_REF
    JSON_SCHEMA_DRAFT_4 = 'http://json-schema.org/draft-04/schema#'

    class ixParameter:
        LOCATIONS = ['body', 'query', 'header']

        def __init__(self, d):
            self._d = d

        @property
        def location(self):
            _location = self._d.get('in')
            if _location in self.LOCATIONS:
                return _location
            raise ValueError('Unsupported parameter location: {0}'.format(_location))

        @property
        def name(self):
            _name = self._d.get('name')
            if _name:
                if self.location == 'header':
                    return 'method.request.header.' + _name;
                elif self.location == 'query':
                    return 'method.request.querystring.' + _name;
                return None 
            raise ValueError('Parameter must have a name: {0}'.format(_dict_to_json_pretty(self._d)))

        @property
        def schema(self):
            if self.location == "body":
                _schema = self._d.get("schema")
                if _schema:
                    if '$ref' in _schema:
                        schema_name = _schema.get('$ref').split('/')[-1]
                        return schema_name
                    raise ValueError('Body parameter must have a JSON reference to the schema definition: {0}'.format(self.name))
                raise ValueError('Body parameter must have a schema: {0}'.format(self.name))
            return None

    class ixMethodResponse:
        def __init__(self, r):
            self._r = r

        @property
        def schema(self):
            _schema = self._r.get("schema")
            if _schema:
                if '$ref' in _schema:
                    return _schema.get('$ref').split('/')[-1]
                raise ValueError('Method response must have a JSON reference to the schema definition: {0}'.format(_schema))
            return None
            # raise ValueError('Method response must have a schema: {0}'.format(self))
            
        @property
        def headers(self):
            _headers = self._r.get('headers', {})
            return _headers

    def __init__(self, swagger_file_path):
        if os.path.exists(swagger_file_path) and os.path.isfile(swagger_file_path):
            self._swagger_file = swagger_file_path
            self._md5_filehash = _gen_md5_filehash(self._swagger_file)
            self._cfg = anyconfig.load(self._swagger_file)
            self._swagger_version = ''
            self._salt_boto_apigateway_version = ''
            # values from AWS APIGateway
            self._restApiId = ''
        else:
            raise IOError('Invalid swagger file path, {0}'.format(swagger_file_path))

        self._validate_swagger_file()

    def _validate_swagger_file(self):
        '''
        High level check/validation of the input swagger file based on
        https://github.com/swagger-api/swagger-spec/blob/master/versions/2.0.md

        This is not a full schema compliance check, but rather make sure that the input file (YAML or
        JSON) can be read into a dictionary, and we check for the content of the Swagger Object for version
        and info.
        '''
        swagger_fields = self._cfg.keys()

        # check for any invalid fields for Swagger Object V2
        for field in swagger_fields:
            if (field not in ixSwagger.SWAGGER_OBJECT_V2_FIELDS and
                not ixSwagger.VENDOR_EXT_PATTERN.match(field)):
                raise ValueError('Invalid Swagger Object Field: {0}'.format(field))

        # check for Required Swagger fields by Saltstack boto apigateway state
        for field in ixSwagger.SWAGGER_OBJECT_V2_FIELDS_REQUIRED:
            if (field not in swagger_fields):
                raise ValueError('Missing Swagger Object Field: {0}'.format(field))

        # check for Swagger Version
        self._swagger_version = self._cfg.get('swagger')
        if self._swagger_version not in ixSwagger.SWAGGER_VERSIONS_SUPPORTED:
            raise ValueError('Unsupported Swagger version: {0},'
                             'Supported versions are {1}'.format(self._swagger_version,
                                                                 ixSwagger.SWAGGER_VERSIONS_SUPPORTED))

        # check for salt boto apigateway extension tags version
        self._salt_boto_apigateway_version = self._cfg.get('x-salt-boto-apigateway-version')
        if self._salt_boto_apigateway_version not in ixSwagger.SALT_BOTO_APIGATEWAY_VERSIONS_SUPPORTED:
            raise ValueError('Unsupported Salt Boto ApiGateway Extension Version {0},'
                             'Supported versions are {1}'.format(self._salt_boto_apigateway_version,
                                                                 ixSwagger.SALT_BOTO_APIGATEWAY_VERSIONS_SUPPORTED))


    @property
    def md5_filehash(self):
        return self._md5_filehash

    @property
    def info(self):
        info = self._cfg.get('info')
        if not info:
            raise ValueError('Info Object has no values')
        return info

    @property
    def info_json(self):
        return _dict_to_json_pretty(self.info)

    @property
    def rest_api_name(self):
        api_name = self.info.get('title')
        if (not api_name):
            raise ValueError('Missing "title" attribute in Info Object')

        return api_name

    @property
    def rest_api_version(self):
        version = self.info.get('version')
        if (not version):
            raise ValueError('Missing "version" attribute in Info Object')

        return version

    @property
    def models(self):
        models = self._cfg.get('definitions')
        if not models:
            raise ValueError('Definitions Object has no values, You need to define them in your swagger file')
        return models.iteritems()

    @property
    def paths(self):
        paths = self._cfg.get('paths')
        if not paths:
            raise ValueError('Paths Object has no values, You need to define them in your swagger file')
        for path in paths.keys():
            if not path.startswith("/"):
                raise ValueError('Path object {0} should start with /. Please fix it'.format(path))
        return paths.iteritems()

    @property
    def basePath(self):
        basePath = self._cfg.get('basePath')
        if not basePath:
            return ""
        return basePath

    @property
    def restApiId(self):
        return self._restApiId

    @restApiId.setter
    def restApiId(self, restApiId):
        self._restApiId = restApiId

    # methods to interact with boto_apigateway execution modules
    def _log_changes(self, ret, changekey, changevalue):
        cl = ret['changes'].get('new', [])
        cl.append({changekey: changevalue})
        ret['changes']['new'] = cl
        return ret

    def deploy_api(self, ret, region=None, key=None, keyid=None, profile=None):
        # TODO: check to see if the service by this name and description exists, 
        # matches the content of swagger.info_json, may need more elaborate checks 
        # on the content of the json in description field of AWS ApiGateway Rest API Object.
        # 
        exists_response = __salt__['boto_apigateway.api_exists'](name=self.rest_api_name, description=self.info_json,
                                                                 region=region, key=key, keyid=keyid, profile=profile)
        if exists_response.get('exists'):
            ret['comment'] = 'rest api already exists'
            ret['abort'] = True
            return ret

        if __opts__['test']:
            ret['comment'] = 'Swagger API Spec {0} is set to be created.'.format(name)
            ret['result'] = None
            ret['abort'] = True
            return ret

        # call into boto_apigateway to create api, and
        create_api_response = __salt__['boto_apigateway.create_api'](name=self.rest_api_name, description=self.info_json,
                                                                     region=region, key=key, keyid=keyid, profile=profile)

        if not create_api_response.get('created'):
            ret['result'] = False
            ret['abort'] = True
            if 'error' in create_api_response:
                ret['comment'] = 'Failed to create rest api: {0}.'.format(create_api_response['error']['message'])
            return ret

        # store the rest api id
        self.restApiId = create_api_response.get('restapi', {}).get('id')

        # log changes on AWS
        return self._log_changes(ret, 'deploy_api', create_api_response.get('restapi'))

    def generate_template_from_schema(self, modelName, ret):
        for model, schema in self.models:
            if model == modelName:
                prefix = "#set($inputRoot = $input.path('#'))";
                params = {"statusCode": 200}
                for p in schema['properties']:
                    params[p] = "$input.params('{0}')".format(p)
                    
        return None

    def deploy_models(self, ret, region=None, key=None, keyid=None, profile=None):
        for model, schema  in self.models:
            # add in a few attributes into the model schema that AWS expects
            _schema = schema.copy()
            _schema.update({'$schema': ixSwagger.JSON_SCHEMA_DRAFT_4,
                            'title': '{0} Schema'.format(model), 
                            'type': 'object'})

            # check to see if model already exists, aws has 2 default models [Empty, Error] 
            # which may need upate with data from swagger file
            model_exists_response = __salt__['boto_apigateway.api_model_exists'](restApiId=self.restApiId,
                modelName=model, region=region, key=key, keyid=keyid, profile=profile)

            if model_exists_response.get('exists'):
                # TODO: still needs to also update model description (if there is a field we will
                # populate it with from swagger file)
                update_model_schema_response = __salt__['boto_apigateway.update_api_model_schema'](restApiId=self.restApiId,
                    modelName=model, schema=_schema, region=region, key=key, keyid=keyid, profile=profile)
                if not update_model_schema_response.get('updated'):
                    ret['result'] = False
                    ret['abort'] = True
                    if 'error' in update_model_schema_response:
                        ret['comment'] = 'Failed to update existing model {0} with schema {1}, error: {2}'.format(model,
                            _dict_to_json_pretty(schema), update_model_schema_response['error']['message'])
                    return ret

                ret = self._log_changes(ret, 'deploy_models', update_model_schema_response)
            else:    
                # call into boto_apigateway to create models
                create_model_response = __salt__['boto_apigateway.create_api_model'](restApiId=self.restApiId, 
                    modelName=model, modelDescription="test123", schema=_schema, 
                    contentType="application/json", region=region, key=key, keyid=keyid, profile=profile)

                if not create_model_response.get('created'):
                    ret['result'] = False
                    ret['abort'] = True
                    if 'error' in create_model_response:
                        ret['comment'] = 'Failed to create model {0}, schema {1}, error: {2}'.format(model, 
                                    _dict_to_json_pretty(schema), create_model_response['error']['message'])
                    return ret

                ret = self._log_changes(ret, 'deploy_models', create_model_response)

        return ret

    def construct_lambda_uri(self, ret, resourcePath, httpMethod, region=None, key=None, keyid=None, profile=None):
        lambda_name = "{0}{1}_{2}".format(self.rest_api_name.replace(" ", "_"), resourcePath.replace("/", "_"), httpMethod)
        lambda_region = __salt__['pillar.get']("lambda.region")
        if not lambda_region:
            raise ValueError('Region for lambda function {0} has not been specified'.format(lambda_name))        
        lambda_dsc = __salt__['boto_lambda.describe'](lambda_name, region=lambda_region, key=key, keyid=keyid, profile=profile)
        if not lambda_dsc.get('lambda'):
            raise ValueError('Could not find lambda function {0}'.format(lambda_name))
            
        lambda_arn = lambda_dsc.get('lambda').get('FunctionArn')
        apigateway_region = __salt__['pillar.get']("apigateway.region")
        lambda_uri = 'arn:aws:apigateway:{0}:lambda:path/2015-03-31/functions/{1}/invocations'.format(apigateway_region, lambda_arn)
        log.info(lambda_uri)
        return lambda_uri

    def deploy_resources(self, ret, region=None, key=None, keyid=None, profile=None):
        for path, pathData in self.paths:
            resource = __salt__['boto_apigateway.create_api_resources'](restApiId=self.restApiId,
                path=self.basePath+path, region=region, key=key, keyid=keyid, profile=profile)
            if not resource.get('created'):
                ret = report_error(ret, resource)
                return ret
            ret = self._log_changes(ret, 'deploy_resources', resource)
            for method, methodData in pathData.iteritems():
                if method in self.SWAGGER_OPERATION_NAMES:
                    method_params = {}
                    method_models = {}
                    log.info(methodData)
                    if 'parameters' in methodData:
                        for param in methodData['parameters']:
                            p = self.ixParameter(param)
                            if p.name:
                                method_params[p.name] = True
                            if p.schema:
                                method_models['application/json'] = p.schema 
                        
                    log.info(method_params)
                    log.info(method_models)

                    m = __salt__['boto_apigateway.create_api_method'](self.restApiId, self.basePath+path,
                        method.upper(), "NONE", requestParameters=method_params, requestModels=method_models, 
                        region=region, key=key, keyid=keyid, profile=profile)
                    if not m.get('created'):
                        ret = report_error(ret, m)
                        return ret

                    requestTemplates = {}
                    if len(method_params) > 0 or len(method_models) > 0:
                        requestTemplates = {"application/json": 
                                       """#set($inputRoot = $input.path('$')) 
                                       {
                                       \"header-params\" : {
                                       #set ($map = $input.params().header)
                                       #foreach( $param in $map.entrySet() )
                                       \"$param.key\" : \"$param.value\" #if( $foreach.hasNext ), #end
                                       #end
                                       },
                                       \"query-params\" : {
                                       #set ($map = $input.params().querystring)
                                       #foreach( $param in $map.entrySet() )
                                       \"$param.key\" : \"$param.value\" #if( $foreach.hasNext ), #end
                                       #end
                                       },
                                       \"body-params\" : $input.json('$')
                                       }"""}

                    lambda_uri = self.construct_lambda_uri(ret, self.basePath+path, method.upper(), 
                                                        region=region, key=key, keyid=keyid, profile=profile)
                    log.info("!!!!!")
                    log.info(region)
                    log.info(profile)
                    log.info("####")
                    integration = __salt__['boto_apigateway.create_api_integration'](self.restApiId, self.basePath+path,
                        method.upper(), "AWS", method.upper(), lambda_uri, "arn:aws:iam::999538448309:role/ApiGatewayTest", requestTemplates=requestTemplates,
                        region=region, key=key, keyid=keyid, profile=profile)
                    log.info(integration)
                    if not integration.get('created'):
                        ret = self.report_error(ret, integration)
                        return ret

                    if 'responses' in methodData:
                        for response, responseData in methodData['responses'].iteritems():
                            httpStatus = str(response)
                            methodResponse = self.ixMethodResponse(responseData)

                            method_response_models = {}
                            if methodResponse.schema:
                                method_response_models['application/json'] = methodResponse.schema
                            
                            method_response_params = {}
                            method_integration_response_params = {}
                            for header in methodResponse.headers:
                                method_response_params["method.response.header."+header] = False
                                method_integration_response_params["method.response.header."+header] = "'*'"

                            mr = __salt__['boto_apigateway.create_api_method_response'](self.restApiId, self.basePath+path,
                                  method.upper(), httpStatus, responseParameters=method_response_params, responseModels=method_response_models,
                                  region=region, key=key, keyid=keyid, profile=profile)
                            if not mr.get('created'):
                                ret = report_error(ret, mr)
                                return ret

                            mir = __salt__['boto_apigateway.create_api_integration_response'](self.restApiId, self.basePath+path,
                                  method.upper(), httpStatus, ".*", responseParameters=method_integration_response_params, 
                                  region=region, key=key, keyid=keyid, profile=profile)
                            if not mir.get('created'):
                                ret = report_error(ret, mir)
                                return ret
                    else:
                        raise ValueError('No responses specified for {0} {1}'.format(path,method)) 

                    ret = self._log_changes(ret, 'deploy_resources - methods', m)
        return ret

    def report_error(self, ret, obj):
        ret['result'] = False
        ret['abort'] = True
        if 'error' in obj:
            ret['comment'] = obj.get('error')
        return ret

def __virtual__():
    '''
    Only load if boto is available.
    '''
    return 'boto_apigateway' if 'boto_apigateway.get_apis' in __salt__ else False

def present(name,
            region=None, key=None, keyid=None, profile=None):
    '''
    Ensure the swagger_yaml_file specified is defined in AWS Api Gateway.

    name
        Name of the location of the swagger rest api definition file in YAML format.

    region
        Region to connect to.

    key
        Secret key to be used.

    keyid
        Access key to be used.

    profile
        A dict with region, key and keyid, or a pillar key (string) that
        contains a dict with region, key and keyid.
    '''
    ret = {'name': name,
           'result': True,
           'comment': '',
           'changes': {}
           }

    try:
        # try to open the swagger file and basic validation
        swagger = ixSwagger(name)

        # first deploy a Rest Api on AWS
        ret = swagger.deploy_api(ret, region=region, key=key, keyid=keyid, profile=profile)
        if ret.get('abort'):
            return ret

        # next, deploy models of to the AWS API
        ret = swagger.deploy_models(ret, region=region, key=key, keyid=keyid, profile=profile)
        if ret.get('abort'):
            return ret

        ret = swagger.deploy_resources(ret, region=region, key=key, keyid=keyid, profile=profile)
        if ret.get('abort'):
            return ret

    except Exception as e:
        ret['result'] = False
        ret['comment'] = e.message

    return ret

    '''    
    r = __salt__['boto_lambda.exists'](name=name, region=region,
                                    key=key, keyid=keyid, profile=profile)

    if 'error' in r:
        ret['result'] = False
        ret['comment'] = 'Failed to create Lambda function: {0}.'.format(r['error']['message'])
        return ret

    if not r.get('exists'):
        if __opts__['test']:
            ret['comment'] = 'Lambda function {0} is set to be created.'.format(name)
            ret['result'] = None
            return ret
        r = __salt__['boto_lambda.create'](name, runtime, role, handler, 
            zipfile, s3bucket, s3key, s3objectversion,
            description, timeout, memorysize, 
            region, key, keyid, profile)
        if not r.get('created'):
            ret['result'] = False
            ret['comment'] = 'Failed to create Lamda function: {0}.'.format(r['error']['message'])
            return ret
        _describe = __salt__['boto_lambda.describe'](name, region=region, key=key,
                                                  keyid=keyid, profile=profile)
        ret['changes']['old'] = {'lambda': None}
        ret['changes']['new'] = _describe
        ret['comment'] = 'Lambda function {0} created.'.format(name)
        return ret

    ret['comment'] = os.linesep.join([ret['comment'], 'Lambda function {0} is present.'.format(name)])
    ret['changes'] = {}
    # Lambda function exists, ensure config matches
    _ret = _lambda_config_present(name, role, handler, description, timeout,
                                  memorysize, region, key, keyid, profile)
    ret['changes'] = dictupdate.update(ret['changes'], _ret['changes'])
    ret['comment'] = ' '.join([ret['comment'], _ret['comment']])
    _ret = _lambda_code_present(name, zipfile, s3bucket, s3key, s3objectversion,
                                 region, key, keyid, profile)
    ret['changes'] = dictupdate.update(ret['changes'], _ret['changes'])
    ret['comment'] = ' '.join([ret['comment'], _ret['comment']])
    return ret
   

def _get_role_arn(name, region=None, key=None, keyid=None, profile=None):
    if name.startswith('arn:aws:iam:'):
        return name

    account_id = __salt__['boto_iam.get_account_id'](
        region=region, key=key, keyid=keyid, profile=profile
    )
    return 'arn:aws:iam::{0}:role/{1}'.format(account_id, name)


def _lambda_config_present(name, role, handler, description, timeout,
                           memorysize, region, key, keyid, profile):
    ret = {'result': True, 'comment': '', 'changes': {}}
    lmbda = __salt__['boto_lambda.describe'](name, 
           region=region, key=key, keyid=keyid, profile=profile)['lambda']
    role_arn = _get_role_arn(role, region, key, keyid, profile)
    need_update = False
    for val, var in {
        'Role': 'role_arn',
        'Handler': 'handler',
        'Description': 'description',
        'Timeout': 'timeout',
        'MemorySize': 'memorysize',
    }.iteritems():
        if lmbda[val] != locals()[var]:
            need_update = True
            ret['changes'].setdefault('new',{})[var] = locals()[var]
            ret['changes'].setdefault('old',{})[var] = lmbda[val]
    if need_update:
        ret['comment'] = os.linesep.join([ret['comment'], 'Lambda function config to be modified'])
        _r = __salt__['boto_lambda.update_config'](name, role, handler, description,
                                        timeout, memorysize, region=region, key=key,
                                        keyid=keyid, profile=profile)
    return ret


def _lambda_code_present(name, zipfile, s3bucket, s3key, s3objectversion,
                         region, key, keyid, profile):
    ret = {'result': True, 'comment': '', 'changes': {}}
    lmbda = __salt__['boto_lambda.describe'](name, 
           region=region, key=key, keyid=keyid, profile=profile)['lambda']
    update = False
    if zipfile:
        size = os.path.getsize(zipfile)
        if size == lmbda['CodeSize']:
            sha = hashlib.sha256()
            with open(zipfile, 'rb') as f:
                sha.update(f.read())
            hashed = sha.digest().encode('base64').strip()
            if hashed != lmbda['CodeSha256']:
                update = True
        else:
            update=True
    else:
       # No way to judge whether the item in the s3 bucket is current without
       # downloading it. Cheaper to just request an update every time, and still
       # idempotent
       update = True
    if update:
        ret['changes']['old'] = {
            'CodeSha256': lmbda['CodeSha256'],
            'CodeSize': lmbda['CodeSize'],
        }
        lmbda = __salt__['boto_lambda.update_code'](name, zipfile, s3bucket,
            s3key, s3objectversion, 
            region=region, key=key, keyid=keyid, profile=profile)['lambda']
        if lmbda['CodeSha256'] != ret['changes']['old']['CodeSha256'] or \
                lmbda['CodeSize'] != ret['changes']['old']['CodeSize']:
            ret['comment'] = os.linesep.join([ret['comment'], 'Lambda function code to be modified'])
            ret['changes']['new'] = {
                'CodeSha256': lmbda['CodeSha256'],
                'CodeSize': lmbda['CodeSize'],
            }
        else:
			del(ret['changes']['old'])
    return ret
'''


def absent(name, region=None, key=None, keyid=None, profile=None):
    '''
    Ensure Lamda function with passed properties is absent.

    name
        Name of the swagger file in YAML format

    region
        Region to connect to.

    key
        Secret key to be used.

    keyid
        Access key to be used.

    profile
        A dict with region, key and keyid, or a pillar key (string) that
        contains a dict with region, key and keyid.
    '''

    ret = {'name': name,
           'result': True,
           'comment': '',
           'changes': {}
           }

    try:
        swagger = ixSwagger(name)
    except Exception as e:
        ret['result'] = False
        ret['comment'] = e.message

    return ret

    '''
    r = __salt__['boto_lambda.exists'](name, region=region,
                                    key=key, keyid=keyid, profile=profile)
    if 'error' in r:
        ret['result'] = False
        ret['comment'] = 'Failed to delete Lambda function: {0}.'.format(r['error']['message'])
        return ret

    if not r:
        ret['comment'] = 'Lambda function {0} does not exist.'.format(name)
        return ret

    if __opts__['test']:
        ret['comment'] = 'Lambda function {0} is set to be removed.'.format(name)
        ret['result'] = None
        return ret
    r = __salt__['boto_lambda.delete'](name,
                                    region=region, key=key,
                                    keyid=keyid, profile=profile)
    if not r['deleted']:
        ret['result'] = False
        ret['comment'] = 'Failed to delete Lambda function: {0}.'.format(r['error']['message'])
        return ret
    ret['changes']['old'] = {'lambda': name}
    ret['changes']['new'] = {'lambda': None}
    ret['comment'] = 'Lambda function {0} deleted.'.format(name)
    return ret
    '''
