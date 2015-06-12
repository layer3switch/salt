# -*- coding: utf-8 -*-
'''
GoGrid Cloud Module
====================

The GoGrid cloud module. This module interfaces with the gogrid public cloud
service. To use Salt Cloud with GoGrid log into the GoGrid web interface and
create an api key. Do this by clicking on "My Account" and then going to the
API Keys tab.

Set up the cloud configuration at ``/etc/salt/cloud.providers`` or
``/etc/salt/cloud.providers.d/gogrid.conf``:

.. code-block:: yaml

    my-gogrid-config:
      # The generated api key to use
      apikey: asdff7896asdh789
      # The apikey's shared secret
      sharedsecret: saltybacon
      provider: gogrid

'''
from __future__ import absolute_import

# Import python libs
import copy
import pprint
import logging
import time
import hashlib

# Import salt cloud libs
import salt.config as config
import salt.utils.cloud
from salt.exceptions import SaltCloudSystemExit, SaltCloudException

# Get logging started
log = logging.getLogger(__name__)

__virtualname__ = 'gogrid'


# Only load in this module if the GoGrid configurations are in place
def __virtual__():
    '''
    Check for GoGrid configs
    '''
    if get_configured_provider() is False:
        return False

    return __virtualname__


def get_configured_provider():
    '''
    Return the first configured instance.
    '''
    return config.is_provider_configured(
        __opts__,
        __active_provider_name__ or __virtualname__,
        ('apikey', 'sharedsecret')
    )


def create(vm_):
    '''
    Create a single VM from a data dict
    '''
    salt.utils.cloud.fire_event(
        'event',
        'starting create',
        'salt/cloud/{0}/creating'.format(vm_['name']),
        {
            'name': vm_['name'],
            'profile': vm_['profile'],
            'provider': vm_['provider'],
        },
        transport=__opts__['transport']
    )

    if len(vm_['name']) > 20:
        raise SaltCloudException('VM names must not be longer than 20 characters')

    log.info('Creating Cloud VM {0}'.format(vm_['name']))
    image_id = avail_images()[vm_['image']]['id']
    public_ips = list_public_ips()
    if len(public_ips.keys()) < 1:
        raise SaltCloudException('No more IPs available')
    host_ip = public_ips.keys()[0]

    create_kwargs = {
        'name': vm_['name'],
        'image': image_id,
        'ram': vm_['size'],
        'ip': host_ip,
    }

    salt.utils.cloud.fire_event(
        'event',
        'requesting instance',
        'salt/cloud/{0}/requesting'.format(vm_['name']),
        {'kwargs': create_kwargs},
        transport=__opts__['transport']
    )

    try:
        data = _query('grid', 'server/add', args=create_kwargs)
    except Exception:
        log.error(
            'Error creating {0} on GOGRID\n\n'
            'The following exception was thrown when trying to '
            'run the initial deployment:\n'.format(
                vm_['name']
            ),
            # Show the traceback if the debug logging level is enabled
            exc_info_on_loglevel=logging.DEBUG
        )
        return False

    ssh_username = config.get_cloud_config_value(
        'ssh_username', vm_, __opts__, default='root'
    )

    def wait_for_apipass():
        '''
        Wait for the password to become available, via the API
        '''
        try:
            passwords = list_passwords()
            return passwords[vm_['name']][0]['password']
        except Exception as exc:
            log.debug(str(exc))
            pass
        time.sleep(5)
        return False

    vm_['password'] = salt.utils.cloud.wait_for_fun(
        wait_for_apipass,
        timeout=config.get_cloud_config_value(
            'wait_for_fun_timeout', vm_, __opts__, default=15 * 60),
    )

    vm_['ssh_host'] = host_ip
    ret = salt.utils.cloud.bootstrap(vm_, __opts__)
    ret.update(data)

    log.info('Created Cloud VM {0[name]!r}'.format(vm_))
    log.debug(
        '{0[name]!r} VM creation details:\n{1}'.format(
            vm_, pprint.pformat(data)
        )
    )

    salt.utils.cloud.fire_event(
        'event',
        'created instance',
        'salt/cloud/{0}/created'.format(vm_['name']),
        {
            'name': vm_['name'],
            'profile': vm_['profile'],
            'provider': vm_['provider'],
        },
        transport=__opts__['transport']
    )

    return ret


def list_nodes(full=False, call=None):
    '''
    List of nodes, keeping only a brief listing

    CLI Example:

    .. code-block:: bash

        salt-cloud -Q
    '''
    if call == 'action':
        raise SaltCloudSystemExit(
            'The list_nodes function must be called with -f or --function.'
        )

    ret = {}
    nodes = list_nodes_full('function')
    if full:
        return nodes

    for node in nodes:
        ret[node] = {}
        for item in ('id', 'image', 'size', 'public_ips', 'private_ips', 'state'):
            ret[node][item] = nodes[node][item]

    return ret


def list_nodes_full(call=None):
    '''
    List nodes, with all available information

    CLI Example:

    .. code-block:: bash

        salt-cloud -F
    '''
    response = _query('grid', 'server/list')

    ret = {}
    for item in response['list']:
        name = item['name']
        ret[name] = item

        ret[name]['image_info'] = item['image']
        ret[name]['image'] = item['image']['friendlyName']
        ret[name]['size'] = item['ram']['name']
        ret[name]['public_ips'] = [item['ip']['ip']]
        ret[name]['private_ips'] = []
        ret[name]['state_info'] = item['state']
        if 'active' in item['state']['description']:
            ret[name]['state'] = 'RUNNING'

    return ret


def list_nodes_select(call=None):
    '''
    Return a list of the VMs that are on the provider, with select fields

    CLI Example:

    .. code-block:: bash

        salt-cloud -S
    '''
    return salt.utils.cloud.list_nodes_select(
        list_nodes_full('function'), __opts__['query.selection'], call,
    )


def avail_locations():
    '''
    Available locations
    '''
    response = list_common_lookups(kwargs={'lookup': 'ip.datacenter'})

    ret = {}
    for item in response['list']:
        name = item['name']
        ret[name] = item

    return ret


def avail_sizes():
    '''
    Available sizes
    '''
    response = list_common_lookups(kwargs={'lookup': 'server.ram'})

    ret = {}
    for item in response['list']:
        name = item['name']
        ret[name] = item

    return ret


def avail_images():
    '''
    Available images
    '''
    response = _query('grid', 'image/list')

    ret = {}
    for item in response['list']:
        name = item['friendlyName']
        ret[name] = item

    return ret


def list_passwords(kwargs=None, call=None):
    '''
    Available images
    '''
    response = _query('support', 'password/list')

    ret = {}
    for item in response['list']:
        server = item['server']['name']
        if server not in ret:
            ret[server] = []
        ret[server].append(item)

    return ret


def list_public_ips(kwargs=None, call=None):
    '''
    List all available public IPs.

    CLI Example:
    .. code-block:: bash

        salt-cloud -f list_public_ips <provider>

    To list unavailable (assigned) IPs, use:

    CLI Example:
    .. code-block:: bash

        salt-cloud -f list_public_ips <provider> state=assigned
    '''
    if kwargs is None:
        kwargs = {}

    args = {}
    if 'state' in kwargs:
        if kwargs['state'] == 'assigned':
            args['ip.state'] = 'Assigned'
        else:
            args['ip.state'] = 'Unassigned'
    else:
        args['ip.state'] = 'Unassigned'

    args['ip.type'] = 'Public'

    response = _query('grid', 'ip/list', args=args)

    ret = {}
    for item in response['list']:
        name = item['ip']
        ret[name] = item

    return ret


def list_common_lookups(kwargs=None, call=None):
    '''
    List common lookups for a particular type of item
    '''
    if kwargs is None:
        kwargs = {}

    args = {}
    if 'lookup' in kwargs:
        args['lookup'] = kwargs['lookup']

    response = _query('common', 'lookup/list', args=args)

    return response
    ret = {}
    for item in response['list']:
        if item.get('public', False) is False:
            continue 
        name = item['ip']
        ret[name] = item

    return ret


def destroy(name, call=None):
    '''
    Destroy a machine by name

    CLI Example:

    .. code-block:: bash

        salt-cloud -d vm_name

    '''
    if call == 'function':
        raise SaltCloudSystemExit(
            'The destroy action must be called with -d, --destroy, '
            '-a or --action.'
        )

    salt.utils.cloud.fire_event(
        'event',
        'destroying instance',
        'salt/cloud/{0}/destroying'.format(name),
        {'name': name},
        transport=__opts__['transport']
    )

    response = _query('grid', 'server/delete', args={'name': name})

    salt.utils.cloud.fire_event(
        'event',
        'destroyed instance',
        'salt/cloud/{0}/destroyed'.format(name),
        {'name': name},
        transport=__opts__['transport']
    )

    if __opts__.get('update_cachedir', False) is True:
        salt.utils.cloud.delete_minion_cachedir(name, __active_provider_name__.split(':')[0], __opts__)

    return response


def reboot(name, call=None):
    '''
    Reboot a machine by name

    CLI Example:

    .. code-block:: bash

        salt-cloud -a reboot vm_name
    '''
    return _query('grid', 'server/power', args={'name': name, 'power': 'restart'})


def stop(name, call=None):
    '''
    Stop a machine by name

    CLI Example:

    .. code-block:: bash

        salt-cloud -a stop vm_name
    '''
    return _query('grid', 'server/power', args={'name': name, 'power': 'stop'})


def start(name, call=None):
    '''
    Start a machine by name

    CLI Example:

    .. code-block:: bash

        salt-cloud -a start vm_name
    '''
    return _query('grid', 'server/power', args={'name': name, 'power': 'start'})


def show_instance(name, call=None):
    '''
    Start a machine by name

    CLI Example:

    .. code-block:: bash

        salt-cloud -a start vm_name
    '''
    response = _query('grid', 'server/get', args={'name': name})
    ret = {}
    for item in response['list']:
        name = item['name']
        ret[name] = item

        ret[name]['image_info'] = item['image']
        ret[name]['image'] = item['image']['friendlyName']
        ret[name]['size'] = item['ram']['name']
        ret[name]['public_ips'] = [item['ip']['ip']]
        ret[name]['private_ips'] = []
        ret[name]['state_info'] = item['state']
        if 'active' in item['state']['description']:
            ret[name]['state'] = 'RUNNING'
    return ret


def _query(action=None,
           command=None,
           args=None,
           method='GET',
           header_dict=None,
           data=None):
    '''
    Make a web call to GoGrid

    .. versionadded:: Beryllium
    '''
    vm_ = get_configured_provider()
    apikey = config.get_cloud_config_value(
        'apikey', vm_, __opts__, search_global=False
    )
    sharedsecret = config.get_cloud_config_value(
        'sharedsecret', vm_, __opts__, search_global=False
    )

    path = 'https://api.gogrid.com/api/'

    if action:
        path += action

    if command:
        path += '/{0}'.format(command)

    log.debug('GoGrid URL: {0}'.format(path))

    if not isinstance(args, dict):
        args = {}

    epoch = str(int(time.time()))
    hashtext = ''.join((apikey, sharedsecret, epoch))
    args['sig'] = hashlib.md5(hashtext).hexdigest()   
    args['format'] = 'json'
    args['v'] = '1.0'
    args['api_key'] = apikey

    if header_dict is None:
        header_dict = {}

    if method != 'POST':
        header_dict['Accept'] = 'application/json'

    decode = True
    if method == 'DELETE':
        decode = False

    return_content = None
    result = salt.utils.http.query(
        path,
        method,
        params=args,
        data=data,
        header_dict=header_dict,
        decode=decode,
        decode_type='json',
        text=True,
        status=True,
        opts=__opts__,
    )
    log.debug(
        'GoGrid Response Status Code: {0}'.format(
            result['status']
        )
    )

    return result['dict']
