# -*- coding: utf-8 -*-
'''
This state manages JBoss 7 AS via management interface.
It uses jboss-cli.sh script from JBoss installation and parses its output to determine execution result.

In order to run each state, jboss_config dict with the following properties must be passed:

 jboss:
  cli_path: '/opt/jboss/jboss-7.0/bin/jboss-cli.sh'
  controller: 10.11.12.13:9999
  cli_user: 'jbossadm'
  cli_password: 'jbossadm'

 If controller doesn't require password, then passing cli_user and cli_password parameters is not obligatory.

Example of application deployment:

 application_deployed:
  jboss7.deployed:
   - artifact:
       artifactory_url: http://artifactory.intranet.company.com/artifactory
       repository: 'ext-release-local'
       artifact_id: 'webcomponent'
       group_id: 'com.company.application'
       packaging: 'war'
       version: '0.1'
       target_dir: '/tmp'
    - jboss_config:
       cli_path: '/opt/jboss/jboss-7.0/bin/jboss-cli.sh'
       controller: 10.11.12.13:9999
       cli_user: 'jbossadm'
       cli_password: 'jbossadm'

 Since same dictionary with configuration will be used in all the states, it is much more convenient to move jboss configuration and other properties
 to pillar. For example, configuration for application deployment could be moved to pillars:

 application_deployed:
  jboss7.deployed:
   - artifact:
       artifactory_url: {{ pillar['artifactory']['url'] }}
       repository: {{ pillar['artifactory']['repository'] }}
       artifact_id: 'webcomponent'
       group_id: 'com.company.application'
       packaging: 'war'
       version: {{ pillar['webcomponent-artifact']['version'] }}
       latest_snapshot: {{ pillar['webcomponent-artifact']['latest_snapshot'] }}
       repository: {{ pillar['webcomponent-artifact']['repository'] }}
   - jboss_config: {{ pillar['jboss'] }}


Configuration in pillars:
   artifactory:
      url: 'http://artifactory.intranet.company.com/artifactory'
      repository: 'libs-snapshots-local'

   webcomponent-artifact:
      repository: 'libs-snapshots-local'
      latest_snapshot: True
      version: -1 #If latest_snapshot then version is ignored

'''

import time
import logging
import re
import traceback
from salt.utils import dictdiffer

from salt.exceptions import CommandExecutionError

log = logging.getLogger(__name__)


def datasource_exists(name, jboss_config, datasource_properties, recreate=False):
    '''
    Ensures that a datasource with given properties exist on the jboss instance.
    If datasource doesn't exist, it is created, otherwise only the properties that are different will be updated.

    name
        Datasource property name
    jboss_config
        Dict with connection properties (see state description)
    datasource_properties
        Dict with datasource properties
    recreate : False
        If set to true and datasource exists it will be removed and created again. However, if there are deployments that depend on the datasource, it will not me possible to remove it.

    Example::

    sampleDS:
      jboss7.datasource_exists:
       - recreate: False
       - datasource_properties:
           driver-name: mysql
           connection-url: 'jdbc:mysql://localhost:3306/sampleDatabase'
           jndi-name: 'java:jboss/datasources/sampleDS'
           user-name: sampleuser
           password: secret
           min-pool-size: 3
           use-java-context: True
       - jboss_config: {{ pillar['jboss'] }}

    '''
    log.debug(" ======================== STATE: jboss7.datasource_exists (name: %s) ", name)
    ret = {'name': name,
           'result': True,
           'changes': {},
           'comment': ''}

    has_changed = False
    ds_current_properties = {}
    ds_result = __salt__['jboss7.read_datasource'](jboss_config=jboss_config, name=name)
    if ds_result['success']:
        ds_current_properties = ds_result['result']
        if recreate:
            remove_result = __salt__['jboss7.remove_datasource'](jboss_config=jboss_config, name=name)
            if remove_result['success']:
                ret['changes']['removed'] = name
            else:
                ret['result'] = False
                ret['comment'] = 'Could not remove datasource. Stdout: '+remove_result['stdout']
                return ret

            has_changed = True # if we are here, we have already made a change

            create_result = __salt__['jboss7.create_datasource'](jboss_config=jboss_config, name=name, datasource_properties=datasource_properties)
            if create_result['success']:
                ret['changes']['created'] = name
            else:
                ret['result'] = False
                ret['comment'] = 'Could not create datasource. Stdout: '+create_result['stdout']
                return ret

            read_result  = __salt__['jboss7.read_datasource'](jboss_config=jboss_config, name=name)
            if read_result['success']:
                ds_new_properties = read_result['result']
            else:
                ret['result'] = False
                ret['comment'] = 'Could not read datasource. Stdout: '+read_result['stdout']
                return ret

        else:
            update_result = __salt__['jboss7.update_datasource'](jboss_config=jboss_config, name=name, new_properties=datasource_properties)
            if not update_result['success']:
                ret['result'] = False
                ret['comment'] = 'Could not update datasource. '+update_result['comment']
                # some changes to the datasource may have already been made, therefore we don't quit here
            else:
                ret['comment'] = 'Datasource updated.'

            read_result = __salt__['jboss7.read_datasource'](jboss_config=jboss_config, name=name)
            ds_new_properties = read_result['result']
    else:
        if ds_result['err_code'] == 'JBAS014807': #ok, resource not exists:
            create_result = __salt__['jboss7.create_datasource'](jboss_config=jboss_config, name=name, datasource_properties=datasource_properties)
            if create_result['success']:
                read_result = __salt__['jboss7.read_datasource'](jboss_config=jboss_config, name=name)
                ds_new_properties = read_result['result']
                ret['comment'] = 'Datasource created.'
            else:
                ret['result'] = False
                ret['comment'] = 'Could not create datasource. Stdout: '+create_result['stdout']
        else:
            raise CommandExecutionError('Unable to handle error', ds_result['failure-description'])

    if ret['result']:
        log.debug("ds_new_properties=%s", str(ds_new_properties))
        log.debug("ds_current_properties=%s", str(ds_current_properties))
        diff = dictdiffer.diff(ds_new_properties, ds_current_properties)

        added = diff.added()
        if(len(added) > 0):
            has_changed = True
            ret['changes']['added'] = __format_ds_changes(added, ds_current_properties, ds_new_properties)

        removed = diff.removed()
        if(len(removed) > 0):
           has_changed = True
           ret['changes']['removed'] = __format_ds_changes(removed, ds_current_properties, ds_new_properties)

        changed = diff.changed()
        if(len(changed) > 0):
            has_changed = True
            ret['changes']['changed'] = __format_ds_changes(changed, ds_current_properties, ds_new_properties)

        if not has_changed:
            ret['comment'] = 'Datasource not changed.'

    return ret


def __format_ds_changes(keys, old_dict, new_dict):
    log.debug("__format_ds_changes(keys=%s, old_dict=%s, new_dict=%s)", str(keys), str(old_dict), str(new_dict))
    changes = ''
    for key in keys:
        log.debug("key=%s", str(key))
        if key in old_dict and key in new_dict:
            changes+=key+':'+__get_ds_value(old_dict,key)+'->'+__get_ds_value(new_dict,key)+'\n'
        elif key in old_dict:
            changes+=key+'\n'
        elif key in new_dict:
            changes+=key+':'+__get_ds_value(new_dict,key)+'\n'
    return changes

def __get_ds_value(dict, key):
    log.debug("__get_value(dict,%s)", key)
    if key == "password":
        return "***"
    elif dict[key] is None:
        return 'undefined'
    else:
        return str(dict[key])

def bindings_exist(name, jboss_config, bindings):
    '''
    Ensures that given JNDI binding are present on the server.
    If a binding doesn't exist on the server it will be created.
    If it already exists its value will be changed.

    jboss_config:
        Dict with connection properties (see state description)
    bindings:
        Dict with bindings to set.

    Example::
        jndi_entries_created:
          jboss7.bindings_exist:
           - bindings:
              'java:global/sampleapp/environment': 'DEV'
              'java:global/sampleapp/configurationFile': '/var/opt/sampleapp/config.properties'
           - jboss_config: {{ pillar['jboss'] }}

    '''
    log.debug(" ======================== STATE: jboss7.bindings_exist (name: %s) ", name)
    log.debug('bindings='+str(bindings))
    ret = {'name': name,
           'result': True,
           'changes': {},
           'comment': 'Bindings not changed.'}

    has_changed = False
    for key in bindings:
        value = str(bindings[key])
        query_result = __salt__['jboss7.read_simple_binding'](binding_name=key, jboss_config=jboss_config)
        if query_result['success']:
            current_value = query_result['result']['value']
            if current_value != value:
                update_result = __salt__['jboss7.update_simple_binding'](binding_name=key, value=value, jboss_config=jboss_config)
                if update_result['success']:
                    has_changed = True
                    __log_binding_change(ret['changes'], 'changed', key, value, current_value)
                else:
                    raise CommandExecutionError( update_result['failure-description'])
        else:
            if query_result['err_code'] == 'JBAS014807': #ok, resource not exists:
                create_result = __salt__['jboss7.create_simple_binding'](binding_name=key, value=value, jboss_config=jboss_config)
                if create_result['success']:
                    has_changed = True
                    __log_binding_change(ret['changes'], 'added', key, value)
                else:
                    raise CommandExecutionError(create_result['failure-description'])
            else:
                raise CommandExecutionError(query_result['failure-description'])

    if has_changed:
        ret['comment'] = 'Bindings changed.'
    return ret

def __log_binding_change(changes, type, key, new, old=None):
    if not type in changes:
        changes[type] = ''
    if old is None:
        changes[type]+=key + ':' + new + '\n'
    else:
        changes[type]+=key + ':' + old + '->' + new + '\n'



def deployed(name, jboss_config, artifact=None, salt_source=None):
    '''
    Ensures that the given application is deployed on server.

    jboss_config:
        Dict with connection properties (see state description)
    artifact:
        If set, the artifact to be deployed will be fetched from artifactory. This is a Dict object with the following properties:
           - artifactory_url: Full url to artifactory instance, for example: http://artifactory.intranet.company.com/artifactory
           - repository: One of the repositories, for example: libs-snapshots, ext-release-local, etc..
           - artifact_id: Artifact ID of the artifact
           - group_id: Group ID of the artifact
           - packaging: war/jar/ear, etc...
           - version: Artifact version. If latest_snapshot is set to True, the value of this attribute will be ignored, and newest snapshot will be taken instead.
           - latest_snapshot: If set to True and repository is a snapshot repository it will automatically select the newest snapshot.
           - target_dir: Temporary directory on minion where artifacts will be downloaded
    salt_source:
        If set, the artifact to be deployed will be fetched from salt master. This is a Dict object with the following properties:
           - source: File on salt master (eg. salt://application-web-0.39.war)
           - target_file: Temporary file on minion to save file to (eg. '/tmp/application-web-0.39.war')
           - undeploy: Regular expression to match against existing deployments. If any deployment matches the regular expression then it will be undeployed.

    The deployment consists of the following steps:
    1) Fetch artifact (salt filesystem, artifact or filesystem on minion)
    2) Check if same artifact is not deployed yet (perhaps with different version)
    3) Undeploy the artifact if it is already deployed
    4) Deploy the new artifact

    Example ::

    Deployment of a file from Salt file system:

    application_deployed:
      jboss7.deployed:
       - salt_source:
            source: salt://application-web-0.39.war
            target_file: '/tmp/application-web-0.39.war'
            undeploy: 'application-web-*'
       - jboss_config: {{ pillar['jboss'] }}

    Here, application-web-0.39.war file is downloaded from Salt file system to /tmp/application-web-0.39.war file on minion.
    Existing deployments are checked if any of them matches 'application-web-*' regular expression, and if so then it
    is undeployed before deploying the application. This is useful to automate deployment of new application versions.

    JBoss state is capable of deploying artifacts directly from Artifactory repository. Here are some examples of deployments:

    1) Deployment of specific version of artifact from Artifactory.

        application_deployed:
          jboss7.deployed:
           - artifact:
               artifactory_url: http://artifactory.intranet.company.com/artifactory
               repository: 'ext-release-local'
               artifact_id: 'webcomponent'
               group_id: 'com.company.application'
               packaging: 'war'
               version: '0.1'
               target_dir: '/tmp'
            - jboss_config: {{ pillar['jboss'] }}

    This performs the following operations:
    - Download artifact from artifactory. For released version the artifact will be downloaded from:
      '%(artifactory_url)s/%(repository)s/%(group_url)s/%(artifact_id)s/%(version)s/%(artifact_id)s-%(version)s.%(packaging)s'
      This follows artifactory convention for artifact resolution. By default the artifact will be downloaded to /tmp directory on minion.
    - Connect to JBoss via controller (defined in jboss_config dict) and check if the artifact is not deployed already. In case of artifactory
      it will check if any deployment's name starts with artifact_id value. If deployment already exists it will be undeployed
    - Deploy the downloaded artifact to JBoss via cli interface.

    2) Deployment of SNAPSHOT version of artifact from Artifactory:

        application_deployed:
          jboss7.deployed:
           - artifact:
               artifactory_url: http://artifactory.intranet.company.com/artifactory
               repository: 'ext-snapshot-local'
               artifact_id: 'webcomponent'
               group_id: 'com.company.application'
               packaging: 'war'
               version: '0.1-SNAPSHOT'
            - jboss_config: {{ pillar['jboss'] }}

    Note that snapshot deployment is detected by convention - when version ends with "SNAPSHOT" string, then it is treated so.
    Deploying snapshot version involves an additional step of resolving the exact name of the artifact (including the timestamp), which
    is not necessary when deploying a release. Remember that in order to perform a snapshot deployment you have to set repository to a
    snapshot repository.

    3) Deployment of latest snapshot of artifact from Artifactory.

        application_deployed:
          jboss7.deployed:
           - artifact:
               artifactory_url: http://artifactory.intranet.company.com/artifactory
               repository: 'ext-snapshot-local'
               artifact_id: 'webcomponent'
               group_id: 'com.company.application'
               packaging: 'war'
               latest_snapshot: True
            - jboss_config: {{ pillar['jboss'] }}

    Instead of providing an exact version of a snapshot it is sometimes more convenient to get the newest version. If artifact.latest_snapshot
     is set to True, then the newest snapshot will be downloaded from Artifactory. In this case it is not necessary to specify version.
     This is particulary useful when integrating with CI tools that will deploy the current snapshot to the Artifactory.

    '''
    log.debug(" ======================== STATE: jboss7.deployed (name: %s) ", name)
    ret = {'name': name,
           'result': True,
           'changes': {},
           'comment': ''}

    comment = ''

    validate_success, validate_comment = __validate_arguments(jboss_config, artifact, salt_source)
    if not validate_success:
        return _error(ret, validate_comment)

    log.debug('artifact=%s', str(artifact))
    resolved_source, get_artifact_comment = __get_artifact(artifact, salt_source)
    log.debug('resolved_source=%s', resolved_source)
    log.debug('get_artifact_comment=%s', get_artifact_comment)

    comment = __append_comment(new_comment=get_artifact_comment, current_comment=comment)
    if resolved_source is None:
        return _error(ret, get_artifact_comment)

    find_success, deployment, find_comment = __find_deployment(jboss_config, artifact, salt_source)
    if not find_success:
        return _error(ret, find_comment)

    log.debug('deployment=%s', deployment)
    if deployment is not None:
        __salt__['jboss7.undeploy'](jboss_config, deployment)
        ret['changes']['undeployed'] = deployment

    deploy_result = __salt__['jboss7.deploy'](jboss_config=jboss_config, source_file=resolved_source)
    log.debug('deploy_result=%s', str(deploy_result))
    if deploy_result['success']:
        comment =  __append_comment(new_comment='Deployment completed.', current_comment=comment)
        ret['comment'] = comment
        ret['changes']['deployed'] = resolved_source
    else:
        comment =  __append_comment(new_comment=('''Deployment failed\nreturn code=%(retcode)d\nstdout='%(stdout)s'\nstderr='%(stderr)s''' % deploy_result), current_comment=comment)
        return _error(ret, comment)

    return ret

def __validate_arguments(jboss_config, artifact, salt_source):
    result, comment = __check_dict_contains(jboss_config, 'jboss_config', ['cli_path', 'controller'])
    if artifact is None and salt_source is None:
        result = False
        comment = __append_comment('No salt_source or artifact defined', comment)
    if artifact:
        result, comment = __check_dict_contains(artifact, 'artifact', ['artifactory_url', 'repository', 'artifact_id', 'group_id', 'packaging'],  comment, result)
        if 'latest_snapshot' in artifact and isinstance(artifact['latest_snapshot'], str):
            if artifact['latest_snapshot'] == 'True':
                artifact['latest_snapshot'] = True
            elif artifact['latest_snapshot'] == 'False':
                artifact['latest_snapshot'] = False
            else:
                result = False
                comment = __append_comment('Cannot convert jboss_config.latest_snapshot=%s to boolean' % artifact['latest_snapshot'], comment)
        if not 'version' in artifact and (not 'latest_snapshot' in artifact or artifact['latest_snapshot'] == False):
            result = False
            comment = __append_comment('No version or latest_snapshot=True in artifact')
    if salt_source:
        result, comment = __check_dict_contains(salt_source, 'salt_source', ['source', 'target_file'], comment, result)

    return result, comment

def __find_deployment(jboss_config, artifact=None, salt_source=None):
    result = None
    success = True
    comment = ''
    deployments = __salt__['jboss7.list_deployments'](jboss_config)
    if artifact is not None:
        for deployment in deployments:
            if deployment.startswith(artifact['artifact_id']):
                if result is not None:
                    success = False
                    comment = "More than one deployment's name starts with %s. \n" \
                              "For deployments from artifactory existing deployments on JBoss are searched to find one that starts with artifact_id.\n"\
                              "Existing deployments: %s" % (artifact['artifact_id'], ",".join(deployments))
                else:
                    result = deployment
    elif salt_source is not None and salt_source['undeploy']:
        deployment_re = re.compile(salt_source['undeploy'])
        for deployment in deployments:
            if deployment_re.match(deployment):
                if result is not None:
                    success = False
                    comment = "More than one deployment matches regular expression: %s. \n" \
                              "For deployments from Salt file system deployments on JBoss are searched to find one that matches regular expression in 'undeploy' parameter.\n" \
                              "Existing deployments: %s" % (salt_source['undeploy'], ",".join(deployments))
                else:
                    result = deployment

    return success, result, comment


def __get_artifact(artifact, salt_source):
    resolved_source = None
    comment = None

    if artifact is None and salt_source is None:
        log.debug('artifact == None and salt_source == None')
        comment  = 'No salt_source or artifact defined'
    elif isinstance(artifact, dict):
        log.debug('artifact from artifactory')
        try:
            fetch_result = __fetch_from_artifactory(artifact)
            log.debug('fetch_result=%s',str(fetch_result))
        except Exception as e:
            log.debug(traceback.format_exc())
            return None, e.message

        if fetch_result['status']:
            resolved_source = fetch_result['target_file']
            comment = fetch_result['comment']
        else:
            comment = 'Cannot fetch artifact (artifactory comment:%s) ' %  fetch_result['comment']
    elif isinstance(salt_source, dict):
        log.debug('file from salt master')

        try:
            sfn, source_sum, comment_ = __salt__['file.get_managed'](
                name=salt_source['target_file'],
                template=None,
                source=salt_source['source'],
                source_hash=None,
                user=None,
                group=None,
                mode=None,
                saltenv=__env__,
                context=None,
                defaults=None,
                kwargs=None)

            manage_result = __salt__['file.manage_file'](
                name=salt_source['target_file'],
                sfn=sfn,
                ret=None,
                source=salt_source['source'],
                source_sum=source_sum,
                user=None,
                group=None,
                mode=None,
                saltenv=__env__,
                backup=None,
                makedirs=False,
                template=None,
                show_diff=True,
                contents=None,
                dir_mode=None)
            if manage_result['result']:
                resolved_source = salt_source['target_file']
            else:
                comment = manage_result['comment']

        except Exception as e:
            log.debug(traceback.format_exc())
            comment = 'Unable to manage file: {0}'.format(e)

    return resolved_source, comment


def __fetch_from_artifactory(artifact):
    target_dir='/tmp'
    if 'temp_dir' in artifact:
        target_dir=artifact['temp_dir']

    if 'latest_snapshot' in artifact and artifact['latest_snapshot']:
        fetch_result = __salt__['artifactory.get_latest_snapshot'](artifactory_url=artifact['artifactory_url'],
                                                                      repository=artifact['repository'],
                                                                      group_id=artifact['group_id'],
                                                                      artifact_id=artifact['artifact_id'],
                                                                      packaging=artifact['packaging'],
                                                                      target_dir=target_dir)
    elif str(artifact['version']).endswith('SNAPSHOT'):
        if 'snapshot_version' in artifact:
            fetch_result = __salt__['artifactory.get_snapshot'](artifactory_url=artifact['artifactory_url'],
                                                                       repository=artifact['repository'],
                                                                       group_id=artifact['group_id'],
                                                                       artifact_id=artifact['artifact_id'],
                                                                       packaging=artifact['packaging'],
                                                                       version=artifact['version'],
                                                                       snapshot_version=artifact['snapshot_version'],
                                                                       target_dir=target_dir)
        else:
            fetch_result = __salt__['artifactory.get_snapshot'](artifactory_url=artifact['artifactory_url'],
                                                                repository=artifact['repository'],
                                                                group_id=artifact['group_id'],
                                                                artifact_id=artifact['artifact_id'],
                                                                packaging=artifact['packaging'],
                                                                version=artifact['version'],
                                                                target_dir=target_dir)
    else:
        fetch_result = __salt__['artifactory.get_release'](artifactory_url=artifact['artifactory_url'],
                                                              repository=artifact['repository'],
                                                              group_id=artifact['group_id'],
                                                              artifact_id=artifact['artifact_id'],
                                                              packaging=artifact['packaging'],
                                                              version=artifact['version'],
                                                              target_dir=target_dir)
    return fetch_result


def reloaded(name, jboss_config, timeout=60, interval=5):
    '''
    Reloads configuration of jboss server. This step performs the following operations:
    - Ensures that server is in running or reload-required state (by reading server-state attribute)
    - Reloads configuration
    - Waits for server to reload and be in running state

    jboss_config:
        Dict with connection properties (see state description)
    timeout:
        Time to wait until jboss is back in running state. Default timeout is 60s.
    interval:
        Interval between state checks. Default interval is 5s. Decreasing the interval may slightly decrease waiting time
        but be aware that every status check is a call to jboss-cli which is a java process. If interval is smaller than
        process cleanup time it may easily lead to excessive resource consumption.

    Example::
    configuration_reloaded:
       jboss7.reloaded:
        - jboss_config: {{ pillar['jboss'] }}
    '''
    log.debug(" ======================== STATE: jboss7.reloaded (name: %s) ", name)
    ret = {'name': name,
           'result': True,
           'changes': {},
           'comment': ''}

    status = __salt__['jboss7.status'](jboss_config)
    if status['success'] == False or status['result'] not in ('running','reload-required'):
        ret['result'] = False
        ret['comment'] = "Cannot reload server configuration, it should be up and in 'running' or 'reload-required' state."
        return ret

    result = __salt__['jboss7.reload'](jboss_config)
    if result['success'] or \
                    'Operation failed: Channel closed' in result['stdout'] or \
                    'Communication error: java.util.concurrent.ExecutionException: Operation failed' in result['stdout']:
        wait_time = 0
        status = None
        while (status is None or status['success'] == False or status['result'] != 'running') and wait_time < timeout:
            time.sleep(interval)
            wait_time += interval
            status = __salt__['jboss7.status'](jboss_config)

        if status['success'] and status['result'] == 'running':
            ret['result'] = True
            ret['comment'] = 'Configuration reloaded'
            ret['changes']['reloaded'] = 'configuration'
        else:
            ret['result'] = False
            ret['comment'] = 'Could not reload the configuration. Timeout (%(timeout)d s) exceeded. ' %  timeout
            if not status['success']:
                ret['comment'] = __append_comment('Could not connect to JBoss controller.', ret['comment'])
            else:
                ret['comment'] = __append_comment( ('Server is in %s state' % status['result'] ), ret['comment'])
    else:
        ret['result'] = False
        ret['comment'] = 'Could not reload the configuration, stdout:'+result['stdout']

    return ret


def __check_dict_contains(dict, dict_name, keys, comment='', result=True):
    for key in keys:
        if key not in dict.keys():
            result = False
            comment = __append_comment("Missing %s in %s" % (key, dict_name), comment)
    return result, comment

def __append_comment(new_comment, current_comment=''):
    return current_comment+'\n'+new_comment

def _error(ret, err_msg):
    ret['result'] = False
    ret['comment'] = err_msg
    return ret
