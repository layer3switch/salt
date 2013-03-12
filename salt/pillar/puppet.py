'''
Execute an unmodified puppet_node_classifier and read the output as YAML.
The YAML data is then directly overlaid onto the minion's pillar data.
'''

# Import python libs
import logging

# Import third party libs
import yaml

# Set up logging
log = logging.getLogger(__name__)

def ext_pillar(pillar, command):
    '''
    Execute an unmodified puppet_node_classifier and read the output as YAML
    '''
    try:
        data = yaml.safe_load(__salt__['cmd.run']('{0}'.format(command + ' ' + __grains__.get('nodename'))))
        data = data['parameters']
        return data
    except Exception:
        log.critical(
                'YAML data from {0} failed to parse'.format(command)
                )
        return {}
