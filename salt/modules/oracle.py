#! python
# -*- coding: utf-8 -*-
'''
Oracle DataBase connection module

:mainteiner: Vladimir Bormotov <bormotov@gmail.com>

:maturity: new

:depends: cx_Oracle

:platform: all

:configuration: module provide connections for multiple Oracle DB instances.

    OS Environment:
        ORACLE_HOME: path to oracle product
        PATH: path to Oracle Client libs need to be in PATH
    pillar:
        oracle.dbs: list of known based
        oracle.dbs.<db>.uri: connection credentials in format:
            user/password@host[:port]/sid[ as {sysdba|sysoper}]
'''

import os
import logging
from salt.utils.decorators import depends

log = logging.getLogger(__name__)

try:
    import cx_Oracle
    MODE = {
        'sysdba': cx_Oracle.SYSDBA,
        'sysoper': cx_Oracle.SYSOPER
    }
    HAS_CX_ORACLE = True
except ImportError:
    MODE = {'sysdba': 2, 'sysoper': 4}
    HAS_CX_ORACLE = False


def __virtual__():
    '''
    Load module only if cx_Oracle installed
    '''
    return True

def _cx_oracle_req():
    return '"cx_Oracle" and Oracle Client needs to be installed for this functin exist'

def _unicode_output(cursor, name, defaultType, size, precision, scale):
    '''
    Return strings values as python unicode string

    http://www.oracle.com/technetwork/articles/dsl/tuininga-cx-oracle-084866.html
    '''
    if defaultType in (cx_Oracle.STRING, cx_Oracle.LONG_STRING,
            cx_Oracle.FIXED_CHAR, cx_Oracle.CLOB):
        return cursor.var(unicode, size, cursor.arraysize)

def _connect(uri):
    '''
    uri = user/password@host[:port]/sid[ as {sysdba|sysoper}]

    Return cx_Oracle.Connection instance
    '''
    # cx_Oracle.Connection() not support 'as sysdba' syntax
    uri_l = uri.rsplit(' as ', 1)
    if len(uri_l) == 2:
        credits, mode = uri_l
        mode = MODE[mode]
    else:
        credits = uri_l[0]
        mode = 0
    userpass, hostportsid = credits.split('@')
    user, password = userpass.split('/')
    hostport, sid = hostportsid.split('/')
    hostport_l = hostport.split(':')
    if len(hostport_l) == 2:
        host, port = hostport_l
    else:
        host = hostport_l[0]
        port = 1521
    log.debug('connect: {0}'.format((user, password, host, port, sid, mode)))
    # force UTF-8 client encoding
    os.environ['NLS_LANG'] = '.AL32UTF8'
    conn = cx_Oracle.connect(user, password,
        cx_Oracle.makedsn(host, port, sid),
        mode)
    conn.outputtypehandler = _unicode_output
    return conn

@depends('cx_Oracle', fallback_function=_cx_oracle_req)
def run_query(db, query):
    '''
    Run SQL query and return result

    CLI example:

    .. code-block:: bash

        salt '*' oracle.run_query my_db "select * from my_table"

    '''
    log.debug('run query on {0}: {1}'.format(db, query))
    conn = _connect(show_dbs(db)[db]['uri'])
    return conn.cursor().execute(query).fetchall()

def show_dbs(*dbs):
    '''
    Show databases configuration from pillar. Filter by *args

    .. code-block:: bash

        salt '*' oracle.show_dbs
        salt '*' oracle.show_dbs my_db
    '''
    pillar_dbs = __salt__['pillar.get']('oracle:dbs')
    if dbs:
        log.debug('get dbs from pillar: %s' % dbs)
        return {db:pillar_dbs[db] for db in dbs if pillar_dbs.has_key(db)}
    else:
        log.debug('get all ({0}) dbs from pillar'.format(len(pillar_dbs)))
        return pillar_dbs

@depends('cx_Oracle', fallback_function=_cx_oracle_req)
def version(*dbs):
    '''
    Server Version (select banner  from v$version)

    CLI Example:

    .. code-block:: bash

        salt '*' oracle.version
        salt '*' oracle.version my_db
    '''
    pillar_dbs = __salt__['pillar.get']('oracle:dbs')
    get_version = lambda x: [r[0] for r in \
        run_query(x, "select banner from v$version order by banner")]
    if dbs:
        log.debug('get db versions for: {0}'.format(dbs))
        return {db:get_version(db) for db in dbs if pillar_dbs.has_key(db)}
    else:
        log.debug('get all({0}) dbs versions'.format(len(dbs)))
        return {db:get_version(db) for db in pillar_dbs}

@depends('cx_Oracle', fallback_function=_cx_oracle_req)
def client_version():
    '''
    Oracle Client Version

    CLI Example:

    .. code-block:: bash

        salt '*' oracle.client_version
    '''
    return '.'.join((str(x) for x in cx_Oracle.clientversion()))

def show_pillar(item=None):
    '''
    Show Pillar segment oracle.* and subitem with notation "item:subitem"

    CLI Example:

    .. code-block:: bash

        salt '*' oracle.show_pillar
        salt '*' oracle.show_pillar dbs:my_db
    '''
    if item:
        return __salt__['pillar.get']('oracle:' + item)
    else:
        return __salt__['pillar.get']('oracle')

def show_env():
    '''
    Show Environment used by Oracle Client

    CLI Example:

    .. code-block:: bash

        salt '*' oracle.show_env

    .. note::
        at first _connect() ``NLS_LANG`` will forced to '.AL32UTF8'
    '''
    envs = ['PATH', 'ORACLE_HOME', 'TNS_ADMIN', 'NLS_LANG']
    return {env:os.environ[env] for env in envs if os.environ.has_key(env)}
