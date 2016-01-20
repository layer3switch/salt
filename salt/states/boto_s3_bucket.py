# -*- coding: utf-8 -*-
'''
Manage S3 Buckets
=================

.. versionadded:: Boron

Create and destroy S3 buckets. Be aware that this interacts with Amazon's services,
and so may incur charges.

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

    Ensure bucket exists:
        boto_s3_bucket.present:
            - Bucket: mybucket
            - LocationConstraint: EU
            - ACL: 
              - ACL: private
                GrantRead: "uri=http://acs.amazonaws.com/groups/global/AllUsers"
            - CORSRules:
              - AllowedHeaders: []
                AllowedMethods: ["GET"]
                AllowedOrigins: ["*"]
                ExposeHeaders: []
                MaxAgeSeconds: 123
            - LifecycleConfiguration:
              - Expiration:
                  Days: 123
                ID: "idstring"
                Prefix: "prefixstring"
                Status: "enabled",
                Transitions:
                  - Days: 123
                    StorageClass: "GLACIER"
                NoncurrentVersionTransitions:
                  - NoncurrentDays: 123
                    StorageClass: "GLACIER"
                NoncurrentVersionExpiration:
                  NoncurrentDays: 123
            - Logging:
                TargetBucket: log_bucket
                TargetPrefix: prefix
                TargetGrants:
                  - Grantee:
                      DisplayName: "string"
                      EmailAddress: "string"
                      ID: "string"
                      Type: "AmazonCustomerByEmail"
                      URI: "string"
                    Permission: "READ"
            - NotificationConfiguration:
                LambdaFunctionConfiguration:
                  - Id: "string"
                    LambdaFunctionArn: "string"
                    Events:
                      - "s3:ObjectCreated:*"
                    Filter:
                      Key:
                        FilterRules:
                          - Name: "prefix"
                            Value: "string"
            - Policy:
                Version: "2012-10-17"
                Statement:
                  - Effect: "Allow"
                    Principal:
                      AWS:
                        - "arn:aws:iam::133434421342:root"
                    Action:
                      - "s3:PutObject"
                    Resource:
                      - "arn:aws:s3:::my-bucket/*"
            - Replication:
                Role: myrole
                Rules:
                  - ID: "string"
                    Prefix: "string"
                    Status: "Enabled"
                    Destination:
                      Bucket: "arn:aws:s3:::my-bucket"
            - RequestPayment:
                Payer: Requester
            - Tagging:
                tag_name: tag_value
                tag_name_2: tag_value
            - Versioning:
                Status: "Enabled"
            - Website:
                ErrorDocument:
                  Key: "error.html"
                IndexDocument:
                  Suffix: "index.html"
                RedirectAllRequestsTo:
                  Hostname: "string"
                  Protocol: "http"
                RoutingRules:
                  - Condition:
                      HttpErrorCodeReturnedEquals: "string"
                      KeyPrefixEquals: "string"
                    Redirect:
                      HostName: "string"
                      HttpRedirectCode: "string"
                      Protocol: "http"
                      ReplaceKeyPrefixWith: "string"
                      ReplaceKeyWith: "string"
            - region: us-east-1
            - keyid: GKTADJGHEIQSXMKKRBJ08H
            - key: askdjghsdfjkghWupUjasdflkdfklgjsdfjajkghs

'''

# Import Python Libs
from __future__ import absolute_import
import logging
import os
import os.path
from copy import deepcopy

# Import Salt Libs
import salt.utils

log = logging.getLogger(__name__)


def __virtual__():
    '''
    Only load if boto is available.
    '''
    return 'boto_s3_bucket' if 'boto_s3_bucket.exists' in __salt__ else False


def _get_canonical_id(region, key, keyid, profile):
    return __salt__['boto_s3_bucket.list'](
        region=region, key=key, keyid=keyid, profile=profile
    ).get('Owner')


def _acl_to_grant(ACL, owner_canonical_id):
    if 'AccessControlPolicy' in ACL:
       ret = deepcopy(ACL['AccessControlPolicy'])
       # Type is required as input, but is not returned as output
       for item in ret.get('Grants'):
           if 'Type' in item.get('Grantee',()):
               del item['Grantee']['Type']
       return ret
    ret = {
        'Grants': [{
            'Grantee': owner_canonical_id,
            'Permission': 'FULL_CONTROL'
        }],
        'Owner': owner_canonical_id
    }
    if 'ACL' in ACL:
        # This is syntactic sugar; expand it out
        acl = ACL['ACL']
        if acl in ('public-read', 'public-read-write'):
            ret['Grants'].append({
                'Grantee': {
                    'URI': 'http://acs.amazonaws.com/groups/global/AllUsers'
                },
                'Permission': 'READ'
            })
        if  acl == 'public-read-write':
            ret['Grants'].append({
                'Grantee': {
                    'URI': 'http://acs.amazonaws.com/groups/global/AllUsers'
                },
                'Permission': 'WRITE'
            })
        if acl == 'aws-exec-read':
            ret['Grants'].append({
                'Grantee': {
                    'DisplayName': 'za-team',
                    'ID': '6aa5a366c34c1cbe25dc49211496e913e0351eb0e8c37aa3477e40942ec6b97c'
                },
                'Permission': 'READ'
            })
        if acl == 'authenticated-read':
            ret['Grants'].append({
                'Grantee': {
                    'URI': 'http://acs.amazonaws.com/groups/global/AuthenticatedUsers'
                },
                'Permission': 'READ'
            })
        if acl == 'log-delivery-write':
            for permission in ('WRITE', 'READ_ACP'):
                ret['Grants'].append({
                    'Grantee': {
                        'URI': 'http://acs.amazonaws.com/groups/s3/LogDelivery'
                    },
                    'Permission': permission
                })
    for key, permission in (
        ('GrantFullControl', 'FULL_CONTROL'),
        ('GrantRead', 'READ'),
        ('GrantReadACP', 'READ_ACP'),
        ('GrantWrite', 'WRITE'),
        ('GrantWriteACP', 'WRITE_ACP'),
    ):
        if key in ACL:
            for item in ACL[key].split(','):
                kind, val = item.split('=')
                if kind == 'uri':
                    grantee = {
                        'URI': val,
                    }
                elif kind == 'id':
                    grantee = {
                        # 'DisplayName': ???,
                        'ID': val
                    }
                else:
                    grantee = {
                        # 'DisplayName': ???,
                        # 'ID': ???
                    }
                ret['Grants'].append({
                    'Grantee': grantee,
                    'Permission': permission
                })
    return ret


def present(name, Bucket,
            LocationConstraint=None,
            ACL=None,
            CORSRules=None,
            LifecycleConfiguration=None,
            Logging=None,
            NotificationConfiguration=None,
            Policy=None,
            Replication=None,
            RequestPayment=None,
            Tagging=None,
            Versioning=None,
            Website=None,
            region=None, key=None, keyid=None, profile=None):
    '''
    Ensure bucket exists.

    name
        The name of the state definition

    Bucket
        Name of the bucket.

    LocationConstraint
        'EU'|'eu-west-1'|'us-west-1'|'us-west-2'|'ap-southeast-1'|'ap-southeast-2'|'ap-northeast-1'|'sa-east-1'|'cn-north-1'|'eu-central-1'

    ACL
        The permissions on a bucket using access control lists (ACL).

    CORSRules
        The cors configuration for a bucket.

    LifecycleConfiguration
        Lifecycle configuration for your bucket

    Logging
        The logging parameters for a bucket and to specify permissions for who
        can view and modify the logging parameters.

    NotificationConfiguration
        notifications of specified events for a bucket

    Policy
        Policy on the bucket

    Replication
        Replication rules. You can add as many as 1,000 rules.
        Total replication configuration size can be up to 2 MB

    RequestPayment
        The request payment configuration for a bucket. By default, the bucket
        owner pays for downloads from the bucket. This configuration parameter
        enables the bucket owner (only) to specify that the person requesting
        the download will be charged for the download

    Tagging
        A dictionary of tags that should be set on the bucket

    Versioning
        The versioning state of the bucket

    Website
        The website configuration of the bucket

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
    ret = {'name': Bucket,
           'result': True,
           'comment': '',
           'changes': {}
           }

    if ACL is None:
        ACL = {'ACL': 'private'}
    if Logging is None:
        Logging = {}
    if NotificationConfiguration is None:
        NotificationConfiguration = {}
    if RequestPayment is None:
        RequestPayment={'Payer': 'BucketOwner'}

    r = __salt__['boto_s3_bucket.exists'](Bucket=Bucket,
           region=region, key=key, keyid=keyid, profile=profile)

    if 'error' in r:
        ret['result'] = False
        ret['comment'] = 'Failed to create bucket: {0}.'.format(r['error']['message'])
        return ret

    if not r.get('exists'):
        if __opts__['test']:
            ret['comment'] = 'S3 bucket {0} is set to be created.'.format(Bucket)
            ret['result'] = None
            return ret
        r = __salt__['boto_s3_bucket.create'](Bucket=Bucket,
                   LocationConstraint=LocationConstraint,
                   region=region, key=key, keyid=keyid, profile=profile)
        if not r.get('created'):
            ret['result'] = False
            ret['comment'] = 'Failed to create bucket: {0}.'.format(r['error']['message'])
            return ret

        for func, testval, funcargs in (
                ('put_acl', ACL, ACL),
                ('put_cors', CORSRules, {"CORSRules": CORSRules}),
                ('put_lifecycle_configuration', LifecycleConfiguration, {"Rules":LifecycleConfiguration}),
                ('put_logging', Logging, Logging),
                ('put_notification_configuration', NotificationConfiguration, NotificationConfiguration),
                ('put_policy', Policy, {"Policy": Policy}),
                # versioning must be set before replication
                ('put_versioning', Versioning, Versioning),
                ('put_replication', Replication, Replication),
                ('put_request_payment', RequestPayment, RequestPayment),
                ('put_tagging', Tagging, Tagging),
                ('put_website', Website, Website),
        ):
            if testval is not None:
                log.info("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
                log.info(func)
                log.info(funcargs)
                r = __salt__['boto_s3_bucket.{0}'.format(func)](Bucket=Bucket,
                                   region=region, key=key, keyid=keyid, profile=profile,
                                   **funcargs)
                if not r.get('updated'):
                    ret['result'] = False
                    ret['comment'] = 'Failed to create bucket: {0}.'.format(r['error']['message'])
                    return ret

        _describe = __salt__['boto_s3_bucket.describe'](Bucket,
                                   region=region, key=key, keyid=keyid, profile=profile)
        ret['changes']['old'] = {'bucket': None}
        ret['changes']['new'] = _describe
        ret['comment'] = 'S3 bucket {0} created.'.format(Bucket)

        return ret

    ret['comment'] = os.linesep.join([ret['comment'], 'S3 bucket {0} is present.'.format(Bucket)])
    ret['changes'] = {}
    # bucket exists, ensure config matches
    _describe = __salt__['boto_s3_bucket.describe'](Bucket=Bucket,
                                 region=region, key=key, keyid=keyid, profile=profile)
    if 'error' in _describe:
        ret['result'] = False
        ret['comment'] = 'Failed to update bucket: {0}.'.format(_describe['error']['message'])
        ret['changes'] = {}
        return ret
    _describe = _describe['bucket']

    # Once versioning has been enabled, it can't completely go away, it can
    # only be suspended
    if not bool(Versioning) and _describe.get('Versioning') is not None:
        Versioning = {'Status': 'Suspended'}

    ocid = _get_canonical_id(region, key, keyid, profile)
    for varname, func, current, compare, desired, deleter in (
            ('ACL', 'put_acl', _describe.get('ACL'), _acl_to_grant(ACL, ocid), ACL, None),
            ('CORS', 'put_cors', _describe.get('CORS'), None, {"CORSRules": CORSRules} if CORSRules else None,
                                                'delete_cors'),
            ('LifecycleConfiguration', 'put_lifecycle_configuration', _describe.get('LifecycleConfiguration'), 
                                            None,
                                            {"Rules": LifecycleConfiguration} if LifecycleConfiguration else None,
                                            'delete_lifecycle_configuration'),
            ('Logging', 'put_logging', _describe.get('Logging',{}).get('LoggingEnabled'), None, Logging, None),
            ('NotificationConfiguration', 'put_notification_configuration', _describe.get('NotificationConfiguration'), None, NotificationConfiguration, None),
            ('Policy', 'put_policy', _describe.get('Policy',{}).get('Policy'), None, Policy, 'delete_policy'),
            # versioning must be set before replication
            ('Versioning', 'put_versioning', _describe.get('Versioning'), None, Versioning, None),
            ('Replication', 'put_replication',
            _describe.get('Replication',{}).get('ReplicationConfiguration'), None, Replication, 'delete_replication'),
            ('RequestPayment', 'put_request_payment', _describe.get('RequestPayment'), None, RequestPayment, None),
            ('Tagging', 'put_tagging', Tagging, None, Tagging, 'delete_tagging'),
            ('Website', 'put_website', Website, None, Website, 'delete_website'),
    ):
        diffs = salt.utils.compare_dicts(current or {}, compare or desired or {})
        if bool(diffs):
            if __opts__['test']:
                msg = 'S3 bucket {0} set to be modified.'.format(Bucket)
                ret['comment'] = msg
                ret['result'] = None
                return ret
            ret['changes'].setdefault('new', {})[varname] = compare or desired
            ret['changes'].setdefault('old', {})[varname] = current

            log.info("#####!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
            log.info(current)
            log.info(func)
            log.info(desired)
            if deleter and desired is None:
                r = __salt__['boto_s3_bucket.{0}'.format(deleter)](Bucket=Bucket,
                   region=region, key=key, keyid=keyid, profile=profile)
                if not r.get('deleted'):
                    ret['result'] = False
                    ret['comment'] = 'Failed to update bucket: {0}.'.format(r['error']['message'])
                    ret['changes'] = {}
                    return ret
            else:
                r = __salt__['boto_s3_bucket.{0}'.format(func)](Bucket=Bucket,
                   region=region, key=key, keyid=keyid, profile=profile,
                   **(desired or {}))
                if not r.get('updated'):
                    ret['result'] = False
                    ret['comment'] = 'Failed to update bucket: {0}.'.format(r['error']['message'])
                    ret['changes'] = {}
                    return ret

    if _describe.get('Location',{}).get('LocationConstraint') != LocationConstraint:
        msg = 'Bucket {0} location does not match desired configuration, but cannot be changed'.format(LocationConstraint)
        log.warn(msg)
        ret['result'] = False
        ret['comment'] = 'Failed to update bucket: {0}.'.format(msg)
        return ret

    return ret


def absent(name, Bucket,
                  region=None, key=None, keyid=None, profile=None):
    '''
    Ensure bucket with passed properties is absent.

    name
        The name of the state definition.

    Bucket
        Name of the bucket.

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

    ret = {'name': Bucket,
           'result': True,
           'comment': '',
           'changes': {}
           }

    r = __salt__['boto_s3_bucket.exists'](Bucket,
                       region=region, key=key, keyid=keyid, profile=profile)
    if 'error' in r:
        ret['result'] = False
        ret['comment'] = 'Failed to delete bucket: {0}.'.format(r['error']['message'])
        return ret

    if r and not r['exists']:
        ret['comment'] = 'S3 bucket {0} does not exist.'.format(Bucket)
        return ret

    if __opts__['test']:
        ret['comment'] = 'S3 bucket {0} is set to be removed.'.format(Bucket)
        ret['result'] = None
        return ret
    r = __salt__['boto_s3_bucket.delete'](Bucket,
                                    region=region, key=key,
                                    keyid=keyid, profile=profile)
    if not r['deleted']:
        ret['result'] = False
        ret['comment'] = 'Failed to delete bucket: {0}.'.format(r['error']['message'])
        return ret
    ret['changes']['old'] = {'bucket': Bucket}
    ret['changes']['new'] = {'bucket': None}
    ret['comment'] = 'S3 bucket {0} deleted.'.format(Bucket)
    return ret
