'''
Module to provide Postgres compatibility to salt.

In order to connect to Postgres, certain configuration is required
in /etc/salt/minion on the relevant minions. Some sample configs
might look like::

    postgres.host: 'localhost'
    postgres.port: '5432'
    postgres.user: 'postgres'
    postgres.pass: ''
    postgres.db: 'postgres'

'''

import logging

log = logging.getLogger(__name__)
__opts__ = {}


def version():
    '''
    Return the version of a Postgres server using the output
    from the ``psql --version`` cmd.

    CLI Example::

        salt '*' postgres.version
    '''
    version_line =  __salt__['cmd.run']('psql --version').split("\n")[0]
    name = version_line.split(" ")[1]
    ver = version_line.split(" ")[2]
    return "%s %s" % (name, ver)


'''
Database related actions
'''


def db_list(user=None, host=None, port=None):
    '''
    Return a list of databases of a Postgres server using the output
    from the ``psql -l`` query.

    CLI Example::

        salt '*' postgres.db_list
    '''
    if not user:
        user = __opts__['postgres.user']
    if not host:
        host = __opts__['postgres.host']
    if not port:
        port = __opts__['postgres.port']

    ret = []
    cmd = "psql -l -h {host} -U {user} -p {port}".format(
            host=host, user=user, port=port)


    lines = [x for x in __salt__['cmd.run'](cmd).split("\n") if len(x.split("|")) == 6]
    header = [x.strip() for x in lines[0].split("|")]
    for line in lines[1:]:
        line = [x.strip() for x in line.split("|")]
        if not line[0] == "":        
            ret.append(zip(header[:-1], line[:-1]))

    return ret

def db_exists(name, user=None, host=None, port=None):
    '''
    Checks if a database exists on the Postgres server.

    CLI Example::

        salt '*' postgres.db_exists 'dbname'
    '''
    databases = __salt__['postgres.db_list'](user=user, host=host, port=port)
    for db in databases:
        if name == dict(db).get('Name'):
            return True

    return False


def db_create(name, 
              user=None, 
              host=None, 
              port=None, 
              tablespace=None,
              encoding=None,
              local=None,
              lc_collate=None,
              lc_ctype=None,
              owner=None,
              template=None):
    '''
    Adds a databases to the Postgres server.

    CLI Example::

        salt '*' postgres.db_create 'dbname' 

        salt '*' postgres.db_create 'dbname' template=template_postgis
    
    '''
    # check if db exists
    if db_exists(name, user, host, port):
        log.info("DB '{0}' already exists".format(name,))
        return False
 
    cmd = 'createdb {0}'.format(name)
  
    if tablespace:
        cmd = "{0} -D {1}".format(cmd, tablespace)

    if encoding:
        cmd = "{0} -E {1}".format(cmd, encoding)

    if local:
        cmd = "{0} -l {1}".format(cmd, local)

    if lc_collate:
        cmd = "{0} --lc-collate {1}".format(cmd, lc_collate)

    if lc_ctype:
        cmd = "{0} --lc-ctype {1}".format(cmd, lc_ctype)

    if owner:
        cmd = "{0} -O {1}".format(cmd, owner)

    if template:
        if db_exists(template, user, host, port):
            cmd = "{cmd} -T {template}".format(cmd=cmd, template=template)
        else:
            log.info("template '{0}' does not exist.".format(template, ))
            return False
    
    __salt__['cmd.run'](cmd)

    if db_exists(name, user, host, port):
        return True
    else:
        log.info("Failed to create DB '{0}'".format(name,))
        return False


def db_remove(name, user=None, host=None, port=None):
    '''
    Removes a databases from the MySQL server.

    CLI Example::

        salt '*' mysql.db_remove 'dbname'
    '''
    # check if db exists
    if not db_exists(name):
        log.info("DB '{0}' does not exist".format(name,))
        return False

    # db doesnt exist, proceed
    cmd = 'dropdb {0}'.format(name)
    __salt__['cmd.run'](cmd)
    if not db_exists(name, user, host, port):
        return True
    else:
        log.info("Failed to delete DB '{0}'.".format(name, ))
        return False
        

'''
User related actions
'''
def user_create(user,
                host='localhost',
                password=None,
                password_hash=None):
    '''
    Creates a MySQL user.

    CLI Examples::

        salt '*' mysql.user_create 'username' 'hostname' 'password

        salt '*' mysql.user_create 'username' 'hostname' password_hash='hash'
    '''
    pass


