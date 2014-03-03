# -*- coding: utf-8 -*-
'''
'''

# Import third party libs
HAS_NOVA = False
try:
    from novaclient.v1_1 import client
    HAS_NOVA = True
except ImportError:
    pass

# Import python libs
import time
import logging

# Import salt libs
import salt.utils

# Get logging started
log = logging.getLogger(__name__)

# Function alias to not shadow built-ins

class SaltNova(object):
    def __init__(self, username, api_key, project_id, auth_url, region_name=None):
        '''
        Set up nova credentials
        '''
        if not HAS_NOVA:
            return None

        self.kwargs = {
            'username': username,
            'api_key': api_key,
            'project_id': project_id,
            'auth_url': auth_url,
            'region_name': region_name,
            'service_type': 'volume'
        }

        self.volume_conn = client.Client(**self.kwargs)

        self.kwargs['service_type'] = 'compute'

        self.compute_conn = client.Client(**self.kwargs)


    def boot(self, name, flavor_id=0, image_id=0, timeout=300):
        nt_ks = self.compute_conn
        response = nt_ks.servers.create(
            name=name, flavor=flavor_id, image=image_id
        )

        start = time.time()
        trycount = 0
        while True:
            trycount += 1
            try:
                return self.server_show(response.id)
            except Exception as exc:
                log.debug('Server information not yet available: {0}'.format(exc))
                time.sleep(1)
                if time.time() - start > timeout:
                    log.error('Timed out after {0} seconds '
                              'while waiting for data'.format(timeout))
                    return False

                log.debug(
                    'Retrying server_show() (try {0})'.format(trycount)
                )

    def server_by_name(self, name):
        return self.server_list().get(name, {})

    def _volume_get(self, volume_id):
        nt_ks = self.volume_conn
        volume = nt_ks.volumes.get(volume_id)
        response = {'name': volume.display_name,
                    'size': volume.size,
                    'id': volume.id,
                    'description': volume.display_description,
                    'attachments': volume.attachments,
                    'status': volume.status
                    }
        return response

    def volume_list(self, search_opts=None):
        nt_ks = self.volume_conn
        volume = nt_ks.volumes.list(search_opts=search_opts)
        return volume

    def volume_show(self, name):
        nt_ks = self.volume_conn
        volumes = self.volume_list(
            search_opts={'display_name': name},
        )
        try:
            volume = volumes[0]
        except IndexError:
            # volume doesn't exist
            return False

        response = {'name': volume.display_name,
                    'size': volume.size,
                    'id': volume.id,
                    'description': volume.display_description,
                    'attachments': volume.attachments,
                    'status': volume.status
                    }
        return response


    def volume_create(self, name, size=100, snapshot=None, voltype=None):
        nt_ks = self.volume_conn
        response = nt_ks.volumes.create(
            size=size,
            display_name=name,
            volume_type=voltype,
            snapshot_id=snapshot
        )

        return self._volume_get(response.id)


    def volume_delete(self, name):
        nt_ks = self.volume_conn
        volume = self.volume_show(name)
        response = nt_ks.volumes.delete(volume['id'])
        return response


    def volume_detach(self,
                      name,
                      server_name,
                      timeout=300):
        self.compute_conn
        volume = self.volume_show(name)
        server = self.server_by_name(server_name)
        response = nt_ks.volumes.delete_server_volume(
            server['id'],
            volume['attachments'][0]['id']
        )
        trycount = 0
        start = time.time()
        while True:
            trycount += 1
            try:
                response = self._volume_get(volume['id'])
                if response['status'] == 'available':
                    return response
            except Exception as exc:
                log.debug('Volume is detaching: {0}'.format(name))
                time.sleep(1)
                if time.time() - start > timeout:
                    log.error('Timed out after {0} seconds '
                              'while waiting for data'.format(timeout))
                    return False

                log.debug(
                    'Retrying volume_show() (try {0})'.format(trycount)
                )


    def volume_attach(self,
                      name,
                      server_name,
                      device='/dev/xvdb',
                      timeout=300):
        nt_ks = self.compute_conn
        volume = self.volume_show(name)
        server = self.server_by_name(server_name)
        response = nt_ks.volumes.create_server_volume(
            server['id'],
            volume['id'],
            device=device
        )
        trycount = 0
        start = time.time()
        while True:
            trycount += 1
            try:
                response = self._volume_get(volume['id'])
                if response['status'] == 'in-use':
                    return response
            except Exception as exc:
                log.debug('Volume is attaching: {0}'.format(name))
                time.sleep(1)
                if time.time() - start > timeout:
                    log.error('Timed out after {0} seconds '
                              'while waiting for data'.format(timeout))
                    return False

                log.debug(
                    'Retrying volume_show() (try {0})'.format(trycount)
                )


    def suspend(self, instance_id):
        nt_ks = self.compute_conn
        response = nt_ks.servers.suspend(instance_id)
        return True


    def resume(self, instance_id):
        nt_ks = self.compute_conn
        response = nt_ks.servers.resume(instance_id)
        return True


    def lock(self, instance_id):
        nt_ks = self.compute_conn
        response = nt_ks.servers.lock(instance_id)
        return True


    def delete(self, instance_id):
        nt_ks = self.compute_conn
        response = nt_ks.servers.delete(instance_id)
        return True


    def flavor_list(self):
        nt_ks = self.compute_conn
        ret = {}
        for flavor in nt_ks.flavors.list():
            links = {}
            for link in flavor.links:
                links[link['rel']] = link['href']
            ret[flavor.name] = {
                'disk': flavor.disk,
                'id': flavor.id,
                'name': flavor.name,
                'ram': flavor.ram,
                'swap': flavor.swap,
                'vcpus': flavor.vcpus,
                'links': links,
            }
            if hasattr(flavor, 'rxtx_factor'):
                ret[flavor.name]['rxtx_factor'] = flavor.rxtx_factor
        return ret


    def flavor_create(self,
                      name,      # pylint: disable=C0103
                      id=0,      # pylint: disable=C0103
                      ram=0,
                      disk=0,
                      vcpus=1):
        nt_ks = self.compute_conn
        nt_ks.flavors.create(
            name=name, flavorid=id, ram=ram, disk=disk, vcpus=vcpus
        )
        return {'name': name,
                'id': id,
                'ram': ram,
                'disk': disk,
                'vcpus': vcpus}


    def flavor_delete(self, id):  # pylint: disable=C0103
        nt_ks = self.compute_conn
        nt_ks.flavors.delete(id)
        return 'Flavor deleted: {0}'.format(id)


    def keypair_list(self):
        nt_ks = self.compute_conn
        ret = {}
        for keypair in nt_ks.keypairs.list():
            ret[keypair.name] = {
                'name': keypair.name,
                'fingerprint': keypair.fingerprint,
                'public_key': keypair.public_key,
            }
        return ret


    def keypair_add(self, name, pubfile=None, pubkey=None):
        nt_ks = self.compute_conn
        if pubfile:
            ifile = salt.utils.fopen(pubfile, 'r')
            pubkey = ifile.read()
        if not pubkey:
            return False
        nt_ks.keypairs.create(name, public_key=pubkey)
        ret = {'name': name, 'pubkey': pubkey}
        return ret


    def keypair_delete(self, name):
        nt_ks = self.compute_conn
        nt_ks.keypairs.delete(name)
        return 'Keypair deleted: {0}'.format(name)


    def image_list(self, name=None):
        nt_ks = self.compute_conn
        ret = {}
        for image in nt_ks.images.list():
            links = {}
            for link in image.links:
                links[link['rel']] = link['href']
            ret[image.name] = {
                'name': image.name,
                'id': image.id,
                'status': image.status,
                'progress': image.progress,
                'created': image.created,
                'updated': image.updated,
                'metadata': image.metadata,
                'links': links,
            }
            if hasattr(image, 'minDisk'):
                ret[image.name]['minDisk'] = image.minDisk
            if hasattr(image, 'minRam'):
                ret[image.name]['minRam'] = image.minRam
        if name:
            return {name: ret[name]}
        return ret


    def image_meta_set(self,
                       id=None,
                       name=None,
                       **kwargs):  # pylint: disable=C0103
        nt_ks = self.compute_conn
        if name:
            for image in nt_ks.images.list():
                if image.name == name:
                    id = image.id  # pylint: disable=C0103
        if not id:
            return {'Error': 'A valid image name or id was not specified'}
        nt_ks.images.set_meta(id, kwargs)
        return {id: kwargs}


    def image_meta_delete(self,
                          id=None,     # pylint: disable=C0103
                          name=None,
                          keys=None):
        nt_ks = self.compute_conn
        if name:
            for image in nt_ks.images.list():
                if image.name == name:
                    id = image.id  # pylint: disable=C0103
        pairs = keys.split(',')
        if not id:
            return {'Error': 'A valid image name or id was not specified'}
        nt_ks.images.delete_meta(id, pairs)
        return {id: 'Deleted: {0}'.format(pairs)}

    def server_list(self):
        nt_ks = self.compute_conn
        ret = {}
        for item in nt_ks.servers.list():
            ret[item.name] = {
                'id': item.id,
                'name': item.name,
                'status': item.status,
                'accessIPv4': item.accessIPv4,
                'accessIPv6': item.accessIPv6,
                'flavor': {'id': item.flavor['id'],
                           'links': item.flavor['links']},
                'image': {'id': item.image['id'],
                          'links': item.image['links']},
                }
        return ret

    def server_list_detailed(self,):
        nt_ks = self.compute_conn
        ret = {}
        for item in nt_ks.servers.list():
            ret[item.name] = {
                'OS-EXT-SRV-ATTR': {},
                'OS-EXT-STS': {},
                'accessIPv4': item.accessIPv4,
                'accessIPv6': item.accessIPv6,
                'addresses': item.addresses,
                'config_drive': item.config_drive,
                'created': item.created,
                'flavor': {'id': item.flavor['id'],
                           'links': item.flavor['links']},
                'hostId': item.hostId,
                'id': item.id,
                'image': {'id': item.image['id'],
                          'links': item.image['links']},
                'key_name': item.key_name,
                'links': item.links,
                'metadata': item.metadata,
                'name': item.name,
                'progress': item.progress,
                'status': item.status,
                'tenant_id': item.tenant_id,
                'updated': item.updated,
                'user_id': item.user_id,
            }
            if hasattr(item.__dict__, 'OS-DCF:diskConfig'):
                ret[item.name]['OS-DCF'] = {
                    'diskConfig': item.__dict__['OS-DCF:diskConfig']
                }
            if hasattr(item.__dict__, 'OS-EXT-SRV-ATTR:host'):
                ret[item.name]['OS-EXT-SRV-ATTR']['host'] = \
                    item.__dict__['OS-EXT-SRV-ATTR:host']
            if hasattr(item.__dict__, 'OS-EXT-SRV-ATTR:hypervisor_hostname'):
                ret[item.name]['OS-EXT-SRV-ATTR']['hypervisor_hostname'] = \
                    item.__dict__['OS-EXT-SRV-ATTR:hypervisor_hostname']
            if hasattr(item.__dict__, 'OS-EXT-SRV-ATTR:instance_name'):
                ret[item.name]['OS-EXT-SRV-ATTR']['instance_name'] = \
                    item.__dict__['OS-EXT-SRV-ATTR:instance_name']
            if hasattr(item.__dict__, 'OS-EXT-STS:power_state'):
                ret[item.name]['OS-EXT-STS']['power_state'] = \
                    item.__dict__['OS-EXT-STS:power_state']
            if hasattr(item.__dict__, 'OS-EXT-STS:task_state'):
                ret[item.name]['OS-EXT-STS']['task_state'] = \
                    item.__dict__['OS-EXT-STS:task_state']
            if hasattr(item.__dict__, 'OS-EXT-STS:vm_state'):
                ret[item.name]['OS-EXT-STS']['vm_state'] = \
                    item.__dict__['OS-EXT-STS:vm_state']
            if hasattr(item.__dict__, 'security_groups'):
                ret[item.name]['security_groups'] = \
                    item.__dict__['security_groups']
        return ret


    def server_show(self, server_id):
        ret = {}
        servers = self.server_list_detailed()
        for server_name, server in servers.iteritems():
            if str(server['id']) == server_id:
                ret[server_name] = server
        return ret


    def secgroup_create(self, name, description):
        nt_ks = self.compute_conn
        nt_ks.security_groups.create(name, description)
        ret = {'name': name, 'description': description}
        return ret


    def secgroup_delete(self, name):
        nt_ks = self.compute_conn
        for item in nt_ks.security_groups.list():
            if item.name == name:
                nt_ks.security_groups.delete(item.id)
                return {name: 'Deleted security group: {0}'.format(name)}
        return 'Security group not found: {0}'.format(name)


    def secgroup_list(self):
        nt_ks = self.compute_conn
        ret = {}
        for item in nt_ks.security_groups.list():
            ret[item.name] = {
                'name': item.name,
                'description': item.description,
                'id': item.id,
                'tenant_id': item.tenant_id,
                'rules': item.rules,
            }
        return ret


    def _item_list(self):
        nt_ks = self.compute_conn
        ret = []
        for item in nt_ks.items.list():
            ret.append(item.__dict__)
            #ret[item.name] = {
            #        'name': item.name,
            #    }
        return ret

#The following is a list of functions that need to be incorporated in the
#nova module. This list should be updated as functions are added.
#
#absolute-limits     Print a list of absolute limits for a user
#actions             Retrieve server actions.
#add-fixed-ip        Add new IP address to network.
#add-floating-ip     Add a floating IP address to a server.
#aggregate-add-host  Add the host to the specified aggregate.
#aggregate-create    Create a new aggregate with the specified details.
#aggregate-delete    Delete the aggregate by its id.
#aggregate-details   Show details of the specified aggregate.
#aggregate-list      Print a list of all aggregates.
#aggregate-remove-host
#                    Remove the specified host from the specified aggregate.
#aggregate-set-metadata
#                    Update the metadata associated with the aggregate.
#aggregate-update    Update the aggregate's name and optionally
#                    availability zone.
#cloudpipe-create    Create a cloudpipe instance for the given project
#cloudpipe-list      Print a list of all cloudpipe instances.
#console-log         Get console log output of a server.
#credentials         Show user credentials returned from auth
#describe-resource   Show details about a resource
#diagnostics         Retrieve server diagnostics.
#dns-create          Create a DNS entry for domain, name and ip.
#dns-create-private-domain
#                    Create the specified DNS domain.
#dns-create-public-domain
#                    Create the specified DNS domain.
#dns-delete          Delete the specified DNS entry.
#dns-delete-domain   Delete the specified DNS domain.
#dns-domains         Print a list of available dns domains.
#dns-list            List current DNS entries for domain and ip or domain
#                    and name.
#endpoints           Discover endpoints that get returned from the
#                    authenticate services
#floating-ip-create  Allocate a floating IP for the current tenant.
#floating-ip-delete  De-allocate a floating IP.
#floating-ip-list    List floating ips for this tenant.
#floating-ip-pool-list
#                    List all floating ip pools.
#get-vnc-console     Get a vnc console to a server.
#host-action         Perform a power action on a host.
#host-update         Update host settings.
#image-create        Create a new image by taking a snapshot of a running
#                    server.
#image-delete        Delete an image.
#live-migration      Migrates a running instance to a new machine.
#meta                Set or Delete metadata on a server.
#migrate             Migrate a server.
#pause               Pause a server.
#rate-limits         Print a list of rate limits for a user
#reboot              Reboot a server.
#rebuild             Shutdown, re-image, and re-boot a server.
#remove-fixed-ip     Remove an IP address from a server.
#remove-floating-ip  Remove a floating IP address from a server.
#rename              Rename a server.
#rescue              Rescue a server.
#resize              Resize a server.
#resize-confirm      Confirm a previous resize.
#resize-revert       Revert a previous resize (and return to the previous
#                    VM).
#root-password       Change the root password for a server.
#secgroup-add-group-rule
#                    Add a source group rule to a security group.
#secgroup-add-rule   Add a rule to a security group.
#secgroup-delete-group-rule
#                    Delete a source group rule from a security group.
#secgroup-delete-rule
#                    Delete a rule from a security group.
#secgroup-list-rules
#                    List rules for a security group.
#ssh                 SSH into a server.
#unlock              Unlock a server.
#unpause             Unpause a server.
#unrescue            Unrescue a server.
#usage-list          List usage data for all tenants
#volume-list         List all the volumes.
#volume-snapshot-create
#                    Add a new snapshot.
#volume-snapshot-delete
#                    Remove a snapshot.
#volume-snapshot-list
#                    List all the snapshots.
#volume-snapshot-show
#                    Show details about a snapshot.
#volume-type-create  Create a new volume type.
#volume-type-delete  Delete a specific flavor
#volume-type-list    Print a list of available 'volume types'.
#x509-create-cert    Create x509 cert for a user in tenant
#x509-get-root-cert  Fetches the x509 root cert.
