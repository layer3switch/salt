# -*- coding: utf-8 -*-
'''
Control Apache Traffic Server
=============================
'''

def __virtual__():
    '''
    Only load if the Traffic Server module is available in __salt__
    '''
    return 'trafficserver' if 'trafficserver' in __salt__ else False


def bounce_cluster():
    '''
    Bounce all Traffic Server nodes in the cluster. Bouncing Traffic Server
    shuts down and immediately restarts Traffic Server, node-by-node.

    .. code-block:: yaml

        bounce_ats_cluster:
          trafficserver.bounce_cluster
    '''
    ret = {'name': name,
           'changes': {},
           'result': None,
           'comment': ''}

    if __opts__['test']:
        ret['comment'] = 'Bouncing cluster'
        return ret

    __salt__['trafficserver.bounce_cluster']

    ret['result'] = True
    ret['comment'] = 'Bounced cluster'
    return ret


def bounce_local(drain=False):
    '''
    Bounce Traffic Server on the local node. Bouncing Traffic Server shuts down
    and immediately restarts the Traffic Server node.

    This option modifies the behavior of traffic_line -b and traffic_line -L
    such that traffic_server is not shut down until the number of active client
    connections drops to the number given by the
    proxy.config.restart.active_client_threshold configuration variable.

    .. code-block:: yaml

        bounce_ats_local:
          trafficserver.bounce_local

        bounce_ats_local:
          trafficserver.bounce_local
            - drain: True
    '''
    ret = {'name': name,
           'changes': {},
           'result': None,
           'comment': ''}

    if __opts__['test']:
        ret['comment'] = 'Bouncing local node'
        return ret

    if __opts__['drain']:
        __salt__['trafficserver.bounce_local'](drain=True)
        ret['result'] = True
        ret['comment'] = 'Bounced local node with drain option'
        return ret
    else:
        __salt__['trafficserver.bounce_local']
        ret['result'] = True
        ret['comment'] = 'Bounced local node'
        return ret


def clear_cluster():
    '''
    Clears accumulated statistics on all nodes in the cluster.

    .. code-block:: yaml

        clear_ats_cluster:
          trafficserver.clear_cluster
    '''
    ret = {'name': name,
           'changes': {},
           'result': None,
           'comment': ''}

    if __opts__['test']:
        ret['comment'] = 'Clearing cluster statistics'
        return ret

    __salt__['trafficserver.clear_cluster']

    ret['result'] = True
    ret['comment'] = 'Cleared cluster statistics'
    return ret


def clear_node():
    '''
    Clears accumulated statistics on the local node.

    .. code-block:: yaml

        clear_ats_node:
          trafficserver.clear_node
    '''
    ret = {'name': name,
           'changes': {},
           'result': None,
           'comment': ''}

    if __opts__['test']:
        ret['comment'] = 'Clearing local node statistics'
        return ret

    __salt__['trafficserver.clear_node']

    ret['result'] = True
    ret['comment'] = 'Cleared local node statistics'
    return ret


def restart_cluster():
    '''
    Restart the traffic_manager process and the traffic_server process on all
    the nodes in a cluster.

    .. code-block:: bash

        restart_ats_cluster:
          trafficserver.restart_cluster

    '''
    ret = {'name': name,
           'changes': {},
           'result': None,
           'comment': ''}

    if __opts__['test']:
        ret['comment'] = 'Restarting cluster'
        return ret

    __salt__['trafficserver.restart_cluster']

    ret['result'] = True
    ret['comment'] = 'Restarted cluster'
    return ret


def restart_local(drain=False):
    '''
    Restart the traffic_manager and traffic_server processes on the local node.

    This option modifies the behavior of traffic_line -b and traffic_line -L
    such that traffic_server is not shut down until the number of active client
    connections drops to the number given by the
    proxy.config.restart.active_client_threshold configuration variable.

    .. code-block:: yaml

        restart_ats_local:
          trafficserver.restart_local

        restart_ats_local_drain:
          trafficserver.restart_local
            - drain: True
    '''
    ret = {'name': name,
           'changes': {},
           'result': None,
           'comment': ''}

    if __opts__['test']:
        ret['comment'] = 'Restarting local node'
        return ret

    if __opts__['drain']:
        __salt__['trafficserver.restart_local'](drain=True)
        ret['result'] = True
        ret['comment'] = 'Restarted local node with drain option'
        return ret
    else:
        __salt__['trafficserver.restart_local']
        ret['result'] = True
        ret['comment'] = 'Restarted local node'
        return ret


def set_var(name, value):
    '''
    Set Traffic Server variable values

    .. code-block:: yaml

        proxy.config.proxy_name:
          trafficserver.set_var:
            - value: cdn.site.domain.tld

        OR

        traffic_server_setting:
          trafficserver.set_var:
            - name: proxy.config.proxy_name
            - value: cdn.site.domain.tld

    '''
    ret = {'name': name,
           'changes': {},
           'result': None,
           'comment': ''}

    if __opts__['test']:
        ret['comment'] = 'Configuring {0} to {1}'.format(
            name,
            value,
        )
        return ret

    __salt__['trafficserver.set_var'](
        variable=name,
        value=value,
    )

    ret['result'] = True
    ret['comment'] = 'Configured {0} to {1}'.format(name, value)
    return ret


def shutdown():
    '''
    Shut down Traffic Server on the local node.

    .. code-block:: yaml

        shutdown_ats:
          trafficserver.shutdown
    '''
    ret = {'name': name,
           'changes': {},
           'result': None,
           'comment': ''}

    if __opts__['test']:
        ret['comment'] = 'Shutting down local node'
        return ret

    __salt__['trafficserver.shutdown']

    ret['result'] = True
    ret['comment'] = 'Shutdown local node'
    return ret


def startup():
    '''
    Start Traffic Server on the local node.

    .. code-block:: yaml

        startup_ats:
          trafficserver.startup
    '''
    ret = {'name': name,
           'changes': {},
           'result': None,
           'comment': ''}

    if __opts__['test']:
        ret['comment'] = 'Starting up local node'
        return ret

    __salt__['trafficserver.startup']

    ret['result'] = True
    ret['comment'] = 'Starting up local node'
    return ret


def refresh():
    '''
    Initiate a Traffic Server configuration file reread. Use this command to
    update the running configuration after any configuration file modification.

    The timestamp of the last reconfiguration event (in seconds since epoch) is
    published in the proxy.node.config.reconfigure_time metric.

    .. code-block:: yaml

        refresh_ats:
          trafficserver.refresh
    '''
    ret = {'name': name,
           'changes': {},
           'result': None,
           'comment': ''}

    if __opts__['test']:
        ret['comment'] = 'Refreshing local node configuration'
        return ret

    __salt__['trafficserver.refresh']

    ret['result'] = True
    ret['comment'] = 'Refreshed local node configuration'
    return ret


def zero_cluster():
    '''
    Reset performance statistics to zero across the cluster.

    .. code-block:: yaml

        zero_ats_cluster:
          trafficserver.zero_cluster
    '''
    ret = {'name': name,
           'changes': {},
           'result': None,
           'comment': ''}

    if __opts__['test']:
        ret['comment'] = 'Zeroing cluster statistics'
        return ret

    __salt__['trafficserver.zero_cluster']

    ret['result'] = True
    ret['comment'] = 'Zeroed cluster statistics'
    return ret


def zero_node():
    '''
    Reset performance statistics to zero on the local node.

    .. code-block:: yaml

        zero_ats_node:
          trafficserver.zero_node
    '''
    ret = {'name': name,
           'changes': {},
           'result': None,
           'comment': ''}

    if __opts__['test']:
        ret['comment'] = 'Zeroing local node statistics'
        return ret

    __salt__['trafficserver.zero_node']

    ret['result'] = True
    ret['comment'] = 'Zeroed local node statistics'
    return ret


def offline(path):
    '''
    Mark a cache storage device as offline. The storage is identified by a path
    which must match exactly a path specified in storage.config. This removes
    the storage from the cache and redirects requests that would have used this
    storage to other storage. This has exactly the same effect as a disk
    failure for that storage. This does not persist across restarts of the
    traffic_server process.

    .. code-block:: yaml

        offline_ats_path:
          trafficserver.offline:
            - path: /path/to/cache
    '''
    ret = {'name': name,
           'changes': {},
           'result': None,
           'comment': ''}

    if __opts__['test']:
        ret['comment'] = 'Setting {0} to offline'.format(path)
        return ret

    __salt__['trafficserver.offline'](path)

    ret['result'] = True
    ret['comment'] = 'Set {0} as offline'.format(path)
    return ret
