# -*- coding: utf-8 -*-
'''
Module for running tasks specific for JBoss AS 7.

All module functions require a jboss_config dict object with the following properties set:
  cli_path: the path to jboss-cli script, for example: '/opt/jboss/jboss-7.0/bin/jboss-cli.sh'
  controller: the ip address and port of controller, for example: 10.11.12.13:9999
  cli_user: username to connect to jboss administration console if necessary
  cli_password: password to connect to jboss administration console if necessary

'''

import re
import logging
from salt.utils import dictdiffer


log = logging.getLogger(__name__)

def status(jboss_config, timeout=5):
    '''
       Get status of running jboss instance.

       jboss_config
           Configuration dictionary with properties specified above.

       '''
    log.debug("======================== MODULE FUNCTION: jboss7.status")
    operation = ':read-attribute(name=server-state)'
    return __salt__['jboss7_cli.run_operation'](jboss_config, operation, fail_on_error=False, retries=0)

def stop_server(jboss_config):
    '''
       Stop running jboss instance

       jboss_config
           Configuration dictionary with properties specified above.

       '''
    log.debug("======================== MODULE FUNCTION: jboss7.stop_server")
    operation = ':shutdown'
    shutdown_result = __salt__['jboss7_cli.run_operation'](jboss_config, operation, fail_on_error = False)
    # JBoss seems to occasionaly close the channel immediately when :shutdown is sent
    if shutdown_result['success'] or ( shutdown_result['success'] == False and 'Operation failed: Channel closed' in shutdown_result['stdout']):
        return shutdown_result
    else:
        raise Exception('''Cannot handle error, return code=%(retcode)s, stdout='%(stdout)s', stderr='%(stderr)s' ''' % shutdown_result)


def reload(jboss_config):
    '''
       Reload running jboss instance

       jboss_config
           Configuration dictionary with properties specified above.

       '''
    log.debug("======================== MODULE FUNCTION: jboss7.reload")
    operation = ':reload'
    reload_result = __salt__['jboss7_cli.run_operation'](jboss_config, operation, fail_on_error = False)
    # JBoss seems to occasionaly close the channel immediately when :reload is sent
    if reload_result['success'] or ( reload_result['success'] == False and
                                         ('Operation failed: Channel closed' in reload_result['stdout'] or
                                          'Communication error: java.util.concurrent.ExecutionException: Operation failed' in reload_result['stdout'])):
        return reload_result
    else:
        raise Exception('''Cannot handle error, return code=%(retcode)s, stdout='%(stdout)s', stderr='%(stderr)s' ''' % reload_result)


def create_datasource(jboss_config, name, datasource_properties):
    '''
       Create datasource in running jboss instance

       jboss_config
           Configuration dictionary with properties specified above.
       name
           Datasource name
       datasource_properties
           A dictionary of datasource properties to be created:
               driver-name: mysql
               connection-url: 'jdbc:mysql://localhost:3306/sampleDatabase'
               jndi-name: 'java:jboss/datasources/sampleDS'
               user-name: sampleuser
               password: secret
               min-pool-size: 3
               use-java-context: True

       '''
    log.debug("======================== MODULE FUNCTION: jboss7.create_datasource, name=%s", name)
    ds_resource_description = __get_datasource_resource_description(jboss_config, name)

    operation = '/subsystem=datasources/data-source="%(name)s":add(%(properties)s)' %{
                'name': name,
                'properties': __get_properties_assignment_string(datasource_properties, ds_resource_description)
    }

    return __salt__['jboss7_cli.run_operation'](jboss_config, operation, fail_on_error=False)

def __get_properties_assignment_string(datasource_properties, ds_resource_description):
    assignment_strings = []
    ds_attributes = ds_resource_description['attributes']
    for key,val in datasource_properties.iteritems():
        assignment_strings.append(__get_single_assignment_string(key,val, ds_attributes) )

    return ','.join(assignment_strings)

def __get_single_assignment_string(key,val,ds_attributes):
    return '%s=%s' % (key, __format_value(key, val, ds_attributes))

def __format_value(key, value, ds_attributes):
    type = ds_attributes[key]['type']
    if type == 'BOOLEAN':
        if value in ('true', 'false'):
            return value
        elif isinstance(value, bool):
            if value:
                return 'true'
            else:
                return 'false'
        else:
            raise Exception("Don't know how to convert %s to BOOLEAN type" % value)

    elif type == 'INT':
        return str(value)
    elif type == 'STRING':
        return '"%s"' % value
    else:
        raise Exception("Don't know how to format value %s of type %s" % (value, type))

def update_datasource(jboss_config, name, new_properties):
    '''
       Update an existing datasource in running jboss instance. 
       If the property doesn't exist if will be created, if it does, it will be updated with the new value

       jboss_config
           Configuration dictionary with properties specified above.
       name
           Datasource name
       new_properties
           A dictionary of datasource properties to be updated. For example:
               driver-name: mysql
               connection-url: 'jdbc:mysql://localhost:3306/sampleDatabase'
               jndi-name: 'java:jboss/datasources/sampleDS'
               user-name: sampleuser
               password: secret
               min-pool-size: 3
               use-java-context: True
               
       '''
    log.debug("======================== MODULE FUNCTION: jboss7.update_datasource, name=%s", name)
    ds_result = __read_datasource(jboss_config, name)
    current_properties = ds_result['result']
    diff = dictdiffer.DictDiffer(new_properties, current_properties)
    changed_properties = diff.changed()

    ret = {
        'success': True,
        'comment': ''
    }
    if(len(changed_properties) > 0):
        ds_resource_description = __get_datasource_resource_description(jboss_config, name)
        ds_attributes = ds_resource_description['attributes']
        for key in changed_properties:
            update_result = __update_datasource_property(jboss_config, name, key, new_properties[key], ds_attributes)
            if not update_result['success']:
                ret['result'] = False
                ret['comment'] = ret['comment'] + ('Could not update datasource property %s with value %s,\n stdout: %s\n' % (key, new_properties[key], update_result['stdout']))

    return ret

def __get_datasource_resource_description(jboss_config, name):
    log.debug("======================== MODULE FUNCTION: jboss7.__get_datasource_resource_description, name=%s", name)
    operation = '/subsystem=datasources/data-source="%(name)s":read-resource-description' % { 'name': name }
    operation_result = __salt__['jboss7_cli.run_operation'](jboss_config, operation)
    if operation_result['outcome']:
        return operation_result['result']


def read_datasource(jboss_config, name):
    '''
       Read datasource properties in the running jboss instance.

       jboss_config
           Configuration dictionary with properties specified above.
       name
           Datasource name
       '''
    log.debug("======================== MODULE FUNCTION: jboss7.read_datasource, name=%s", name)
    return __read_datasource(jboss_config, name)

def create_simple_binding(jboss_config, binding_name, value):
    '''
       Create a simple jndi binding in the running jboss instance

       jboss_config
           Configuration dictionary with properties specified above.
       binding_name
           Binding name to be created
       value
           Binding value
       '''
    log.debug("======================== MODULE FUNCTION: jboss7.create_simple_binding, binding_name=%s, value=%s", binding_name, value)
    operation = '/subsystem=naming/binding="%(binding_name)s":add(binding-type=simple, value="%(value)s")' % {
          'binding_name': binding_name,
          'value': __escape_binding_value(value)
    }
    return __salt__['jboss7_cli.run_operation'](jboss_config, operation)

def update_simple_binding(jboss_config, binding_name, value):
    '''
       Update the simple jndi binding in the running jboss instance

       jboss_config
           Configuration dictionary with properties specified above.
       binding_name
           Binding name to be updated
       value
           New binding value
       '''
    log.debug("======================== MODULE FUNCTION: jboss7.update_simple_binding, binding_name=%s, value=%s", binding_name, value)
    operation = '/subsystem=naming/binding="%(binding_name)s":write-attribute(name=value, value="%(value)s")' % {
        'binding_name': binding_name,
        'value': __escape_binding_value(value)
    }
    return __salt__['jboss7_cli.run_operation'](jboss_config, operation)

def read_simple_binding(jboss_config, binding_name):
    '''
       Read jndi binding in the running jboss instance

       jboss_config
           Configuration dictionary with properties specified above.
       binding_name
           Binding name to be created
       '''
    log.debug("======================== MODULE FUNCTION: jboss7.read_simple_binding, %s", binding_name)
    return __read_simple_binding(jboss_config, binding_name)

def __read_simple_binding(jboss_config, binding_name):
    operation = '/subsystem=naming/binding="%(binding_name)s":read-resource' % {
        'binding_name': binding_name
    }
    return __salt__['jboss7_cli.run_operation'](jboss_config, operation)

def __update_datasource_property(jboss_config, datasource_name, name, value, ds_attributes):
    log.debug("======================== MODULE FUNCTION: jboss7.__update_datasource_property, datasource_name=%s, name=%s, value=%s", datasource_name, name, value)
    operation = '/subsystem=datasources/data-source="%(datasource_name)s":write-attribute(name="%(name)s",value=%(value)s)' % {
                  'datasource_name': datasource_name,
                  'name': name,
                  'value': __format_value(name, value, ds_attributes)
              }
    return __salt__['jboss7_cli.run_operation'](jboss_config, operation, fail_on_error=False)


def __read_datasource(jboss_config, name):
    operation = '/subsystem=datasources/data-source="%(name)s":read-resource' % { 'name': name }
    operation_result = __salt__['jboss7_cli.run_operation'](jboss_config, operation)

    return operation_result

def __escape_binding_value(binding_name):
    result = binding_name.replace('\\', '\\\\\\\\') # replace \ -> \\\\

    return result

def remove_datasource(jboss_config, name):
    '''
       Remove an existing datasource from the running jboss instance.

       jboss_config
           Configuration dictionary with properties specified above.
       name
           Datasource name
       '''
    log.debug("======================== MODULE FUNCTION: jboss7.remove_datasource, name=%s", name)
    operation = '/subsystem=datasources/data-source=%(name)s:remove' % { 'name': name  }
    return __salt__['jboss7_cli.run_operation'](jboss_config, operation, fail_on_error=False)


def deploy(jboss_config, source_file):
    '''
       Deploy the application on the jboss instance from the local file system where minion is running.

       jboss_config
           Configuration dictionary with properties specified above.
       source_file
           Source file to deploy from
       '''
    log.debug("======================== MODULE FUNCTION: jboss7.deploy, source_file=%s", source_file)
    command = 'deploy %(source_file)s --force ' % { 'source_file': source_file }
    return __salt__['jboss7_cli.run_command'](jboss_config, command, fail_on_error=False)

def list_deployments(jboss_config):
    '''
       List all deployments on the jboss instance

       jboss_config
           Configuration dictionary with properties specified above.

       '''
    log.debug("======================== MODULE FUNCTION: jboss7.list_deployments")
    command_result = __salt__['jboss7_cli.run_command'](jboss_config, 'deploy')
    deployments = []
    if len(command_result['stdout']) > 0:
        deployments = re.split('\\s*', command_result['stdout'])
    log.debug('deployments=%s', str(deployments))
    return deployments

def undeploy(jboss_config, deployment):
    '''
       Undeploy the application from jboss instance

       jboss_config
           Configuration dictionary with properties specified above.
       deployment
           Deployment name to undeploy
       '''
    log.debug("======================== MODULE FUNCTION: jboss7.undeploy, deployment=%s", deployment)
    command = 'undeploy %(deployment)s ' % { 'deployment': deployment }
    return __salt__['jboss7_cli.run_command'](jboss_config, command)
