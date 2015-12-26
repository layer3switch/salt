"""
A salt cloud provider that lets you use virtualbox on your machine
and act as a cloud.

For now this will only clone existing VMs. It's best to create a template
from which we will clone.

Followed
https://docs.saltstack.com/en/latest/topics/cloud/cloud.html#non-libcloud-based-modules
to create this.

Dicts provided by salt:
    __opts__ : contains the options used to run Salt Cloud,
        as well as a set of configuration and environment variables
"""

# Import python libs
import logging

# Import salt libs
from salt.exceptions import SaltCloudSystemExit
import salt.config as config
import salt.utils.cloud as cloud
from utils.virtualbox import vb_list_machines, vb_clone_vm, HAS_LIBS

log = logging.getLogger(__name__)

"""
The name salt will identify the lib by
"""
__virtualname__ = 'virtualbox'


def __virtual__():
    """
    This function determines whether or not
    to make this cloud module available upon execution.
    Most often, it uses get_configured_provider() to determine
     if the necessary configuration has been set up.
    It may also check for necessary imports decide whether to load the module.
    In most cases, it will return a True or False value.
    If the name of the driver used does not match the filename,
     then that name should be returned instead of True.

    @return True|False|str
    """

    if not HAS_LIBS:
        return False

    if get_configured_provider() is False:
        return False

    # If the name of the driver used does not match the filename,
    #  then that name should be returned instead of True.
    # return __virtualname__
    return True


def get_configured_provider():
    """
    Return the first configured instance.
    """
    configured = config.is_provider_configured(
        __opts__,
        __active_provider_name__ or __virtualname__,
        ()  # keys we need from the provider configuration
    )
    log.debug("First virtualbox configuration %s" % configured)
    return configured


def create(vm_info):
    """
    Creates a virtual machine from the given VM information.
    This is what is used to request a virtual machine to be created by the
    cloud provider, wait for it to become available,
    and then (optionally) log in and install Salt on it.

    Fires:
        "starting create" : This event is tagged salt/cloud/<vm name>/creating.
        The payload contains the names of the VM, profile and provider.

    @param vm_info {dict}
            {
                name: <str>
                profile: <dict>
                driver: <provider>:<profile>
                clonefrom: <vm_name>
            }
    @return dict of resulting vm. !!!Passwords can and should be included!!!
    """
    log.debug("Creating virtualbox with %s" % vm_info)
    try:
        # Check for required profile parameters before sending any API calls.
        # TODO should this be a call to config.is_provider_configured ?
        if vm_info['profile'] and config.is_profile_configured(
            __opts__,
                __active_provider_name__ or 'virtualbox',
            vm_info['profile']
        ) is False:
            return False
    except AttributeError:
        pass

    log.debug("Going to fire event: starting create")
    cloud.fire_event(
        'event',
        'starting create',
        'salt/cloud/{0}/creating'.format(vm_info['name']),
        {
            'name': vm_info['name'],
            'profile': vm_info['profile'],
            'driver': vm_info['driver'],
        },
        transport=__opts__['transport']
    )

    # TODO Calculate kwargs with parameters required by virtualbox
    # to create the virtual machine.
    request_kwargs = {
        'name': vm_info['name'],
        'clone_from': vm_info['clonefrom']
    }

    cloud.fire_event(
        'event',
        'requesting instance',
        'salt/cloud/{0}/requesting'.format(vm_info['name']),
        request_kwargs,
        transport=__opts__['transport']
    )
    # TODO request a new VM!
    vm_result = vb_clone_vm(**request_kwargs)

    # TODO Prepare deployment of salt on the vm
    # Any private data, including passwords and keys (including public keys)
    # should be stripped from the deploy kwargs before the event is fired.
    deploy_kwargs = {
    }

    cloud.fire_event(
        'event',
        'deploying salt',
        'salt/cloud/{0}/deploying'.format(vm_info['name']),
        deploy_kwargs,
        transport=__opts__['transport']
    )

    deploy_kwargs.update({
        # TODO Add private data
    })

    # TODO wait for target machine to become available
    # TODO deploy!
    # Do we have to call this?
    # cloud.deploy_script(None, **deploy_kwargs)

    cloud.fire_event(
        'event',
        'created machine',
        'salt/cloud/{0}/created'.format(vm_info['name']),
        vm_result,
        transport=__opts__['transport']
    )

    # Passwords should be included in this object!!
    return vm_result


def avail_images(call=None):
    '''
    Return a list of all the images in the virtualbox hypervisor

    TODO: Does virtualbox support templates?

    CLI Example:

    .. code-block:: bash

        salt-cloud --list-images my-vmware-config
    '''
    if call == 'action':
        raise SaltCloudSystemExit(
            'The avail_images function must be called with '
            '-f or --function, or with the --list-images option.'
        )

    machines = {}

    for machine in vb_list_machines():
        name = machine.get("name")
        if name:
            machines[name] = machine

    return machines
