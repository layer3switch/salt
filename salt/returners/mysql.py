# -*- coding: utf-8 -*-
'''
Return data to a mysql server

:maintainer:    Dave Boucha <dave@saltstack.com>, Seth House <shouse@saltstack.com>
:maturity:      new
:depends:       python-mysqldb
:platform:      all

To enable this returner, the minion will need the python client for mysql
installed and the following values configured in the minion or master
config. These are the defaults:

.. code-block:: yaml

    mysql.host: 'salt'
    mysql.user: 'salt'
    mysql.pass: 'salt'
    mysql.db: 'salt'
    mysql.port: 3306

SSL is optional. The defaults are set to None. If you do not want to use SSL,
either exclude these options or set them to None.

.. code-block:: yaml

    mysql.ssl_ca: None
    mysql.ssl_cert: None
    mysql.ssl_key: None

Alternative configuration values can be used by prefacing the configuration
with `alternative.`. Any values not found in the alternative configuration will
be pulled from the default location. As stated above, SSL configuration is
optional. The following ssl options are simply for illustration purposes:

.. code-block:: yaml

    alternative.mysql.host: 'salt'
    alternative.mysql.user: 'salt'
    alternative.mysql.pass: 'salt'
    alternative.mysql.db: 'salt'
    alternative.mysql.port: 3306
    alternative.mysql.ssl_ca: '/etc/pki/mysql/certs/localhost.pem'
    alternative.mysql.ssl_cert: '/etc/pki/mysql/certs/localhost.crt'
    alternative.mysql.ssl_key: '/etc/pki/mysql/certs/localhost.key'

Use the following mysql database schema:

.. code-block:: sql

    CREATE DATABASE  `salt`
      DEFAULT CHARACTER SET utf8
      DEFAULT COLLATE utf8_general_ci;

    USE `salt`;

    --
    -- Table structure for table `jids`
    --

    DROP TABLE IF EXISTS `jids`;
    CREATE TABLE `jids` (
      `jid` varchar(255) NOT NULL,
      `load` mediumtext NOT NULL,
      UNIQUE KEY `jid` (`jid`)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8;
    CREATE INDEX jid ON jids(jid) USING BTREE;

    --
    -- Table structure for table `salt_returns`
    --

    DROP TABLE IF EXISTS `salt_returns`;
    CREATE TABLE `salt_returns` (
      `fun` varchar(50) NOT NULL,
      `jid` varchar(255) NOT NULL,
      `return` mediumtext NOT NULL,
      `id` varchar(255) NOT NULL,
      `success` varchar(10) NOT NULL,
      `full_ret` mediumtext NOT NULL,
      `alter_time` TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
      KEY `id` (`id`),
      KEY `jid` (`jid`),
      KEY `fun` (`fun`)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8;

    --
    -- Table structure for table `salt_events`
    --

    DROP TABLE IF EXISTS `salt_events`;
    CREATE TABLE `salt_events` (
    `id` BIGINT NOT NULL AUTO_INCREMENT,
    `tag` varchar(255) NOT NULL,
    `data` mediumtext NOT NULL,
    `alter_time` TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    `master_id` varchar(255) NOT NULL,
    PRIMARY KEY (`id`),
    KEY `tag` (`tag`)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8;

Required python modules: MySQLdb

To use the mysql returner, append '--return mysql' to the salt command.

.. code-block:: bash

    salt '*' test.ping --return mysql

To use the alternative configuration, append '--return_config alternative' to the salt command.

.. versionadded:: 2015.5.0

.. code-block:: bash

    salt '*' test.ping --return mysql --return_config alternative

To override individual configuration items, append --return_kwargs '{"key:": "value"}' to the salt command.

.. versionadded:: 2016.3.0

.. code-block:: bash

    salt '*' test.ping --return mysql --return_kwargs '{"db": "another-salt"}'

'''
from __future__ import absolute_import
# Let's not allow PyLint complain about string substitution
# pylint: disable=W1321,E1321

# Import python libs
from contextlib import contextmanager
import sys
import json
import logging

# Import salt libs
import salt.returners
import salt.utils.jid
import salt.exceptions

# Import third party libs
try:
    import MySQLdb
    HAS_MYSQL = True
except ImportError:
    HAS_MYSQL = False

log = logging.getLogger(__name__)

# Define the module's virtual name
__virtualname__ = 'mysql'


def __virtual__():
    if not HAS_MYSQL:
        return False
    return True


def _get_options(ret=None):
    '''
    Returns options used for the MySQL connection.
    '''
    defaults = {'host': 'salt',
                'user': 'salt',
                'pass': 'salt',
                'db': 'salt',
                'port': 3306,
                'ssl_ca': None,
                'ssl_cert': None,
                'ssl_key': None}

    attrs = {'host': 'host',
             'user': 'user',
             'pass': 'pass',
             'db': 'db',
             'port': 'port',
             'ssl_ca': 'ssl_ca',
             'ssl_cert': 'ssl_cert',
             'ssl_key': 'ssl_key'}

    _options = salt.returners.get_returner_options(__virtualname__,
                                                   ret,
                                                   attrs,
                                                   __salt__=__salt__,
                                                   __opts__=__opts__,
                                                   defaults=defaults)
    # Ensure port is an int
    if 'port' in _options:
        _options['port'] = int(_options['port'])
    return _options


@contextmanager
def _get_serv(ret=None, commit=False):
    '''
    Return a mysql cursor
    '''
    _options = _get_options(ret)

    connect = True
    if __context__ and 'mysql_returner_conn' in __context__:
        try:
            log.debug('Trying to reuse MySQL connection pool')
            conn = __context__['mysql_returner_conn']
            conn.ping()
            connect = False
        except MySQLdb.connections.OperationalError as exc:
            log.debug('OperationalError on ping: {0}'.format(exc))

    if connect:
        log.debug('Generating new MySQL connection pool')
        try:
            # An empty ssl_options dictionary passed to MySQLdb.connect will
            # effectively connect w/o SSL.
            ssl_options = {}
            if _options.get('ssl_ca'):
                ssl_options['ca'] = _options.get('ssl_ca')
            if _options.get('ssl_cert'):
                ssl_options['cert'] = _options.get('ssl_cert')
            if _options.get('ssl_key'):
                ssl_options['key'] = _options.get('ssl_key')
            conn = MySQLdb.connect(host=_options.get('host'),
                                   user=_options.get('user'),
                                   passwd=_options.get('pass'),
                                   db=_options.get('db'),
                                   port=_options.get('port'),
                                   ssl=ssl_options)

            try:
                __context__['mysql_returner_conn'] = conn
            except TypeError:
                pass
        except MySQLdb.connections.OperationalError as exc:
            raise salt.exceptions.SaltMasterError('MySQL returner could not connect to database: {exc}'.format(exc=exc))

    cursor = conn.cursor()

    try:
        yield cursor
    except MySQLdb.DatabaseError as err:
        error = err.args
        sys.stderr.write(str(error))
        cursor.execute("ROLLBACK")
        raise err
    else:
        if commit:
            cursor.execute("COMMIT")
        else:
            cursor.execute("ROLLBACK")


def returner(ret):
    '''
    Return data to a mysql server
    '''
    try:
        with _get_serv(ret, commit=True) as cur:
            sql = '''INSERT INTO `salt_returns`
                    (`fun`, `jid`, `return`, `id`, `success`, `full_ret` )
                    VALUES (%s, %s, %s, %s, %s, %s)'''

            cur.execute(sql, (ret['fun'], ret['jid'],
                              json.dumps(ret['return']),
                              ret['id'],
                              ret.get('success', False),
                              json.dumps(ret)))
    except salt.exceptions.SaltMasterError as exc:
        log.critical(exc)
        log.critical('Could not store return with MySQL returner. MySQL server unavailable.')


def event_return(events):
    '''
    Return event to mysql server

    Requires that configuration be enabled via 'event_return'
    option in master config.
    '''
    with _get_serv(events, commit=True) as cur:
        for event in events:
            tag = event.get('tag', '')
            data = event.get('data', '')
            sql = '''INSERT INTO `salt_events` (`tag`, `data`, `master_id` )
                     VALUES (%s, %s, %s)'''
            cur.execute(sql, (tag, json.dumps(data), __opts__['id']))


def save_load(jid, load, minions=None):
    '''
    Save the load to the specified jid id
    '''
    with _get_serv(commit=True) as cur:

        sql = '''INSERT INTO `jids`
               (`jid`, `load`)
                VALUES (%s, %s)'''

        try:
            cur.execute(sql, (jid, json.dumps(load)))
        except MySQLdb.IntegrityError:
            # https://github.com/saltstack/salt/issues/22171
            # Without this try:except: we get tons of duplicate entry errors
            # which result in job returns not being stored properly
            pass


def save_minions(jid, minions):  # pylint: disable=unused-argument
    '''
    Included for API consistency
    '''
    pass


def get_load(jid):
    '''
    Return the load data that marks a specified jid
    '''
    with _get_serv(ret=None, commit=True) as cur:

        sql = '''SELECT `load` FROM `jids` WHERE `jid` = %s;'''
        cur.execute(sql, (jid,))
        data = cur.fetchone()
        if data:
            return json.loads(data[0])
        return {}


def get_jid(jid):
    '''
    Return the information returned when the specified job id was executed
    '''
    with _get_serv(ret=None, commit=True) as cur:

        sql = '''SELECT id, full_ret FROM `salt_returns`
                WHERE `jid` = %s'''

        cur.execute(sql, (jid,))
        data = cur.fetchall()
        ret = {}
        if data:
            for minion, full_ret in data:
                ret[minion] = json.loads(full_ret)
        return ret


def get_fun(fun):
    '''
    Return a dict of the last function called for all minions
    '''
    with _get_serv(ret=None, commit=True) as cur:

        sql = '''SELECT s.id,s.jid, s.full_ret
                FROM `salt_returns` s
                JOIN ( SELECT MAX(`jid`) as jid
                    from `salt_returns` GROUP BY fun, id) max
                ON s.jid = max.jid
                WHERE s.fun = %s
                '''

        cur.execute(sql, (fun,))
        data = cur.fetchall()

        ret = {}
        if data:
            for minion, _, full_ret in data:
                ret[minion] = json.loads(full_ret)
        return ret


def get_jids():
    '''
    Return a list of all job ids
    '''
    with _get_serv(ret=None, commit=True) as cur:

        sql = '''SELECT DISTINCT `jid`, `load`
                FROM `jids`'''

        cur.execute(sql)
        data = cur.fetchall()
        ret = {}
        for jid in data:
            ret[jid[0]] = salt.utils.jid.format_jid_instance(jid[0],
                                                             json.loads(jid[1]))
        return ret


def get_jids_filter(count, filter_find_job=True):
    '''
    Return a list of all job ids
    :param int count: show not more than the count of most recent jobs
    :param bool filter_find_jobs: filter out 'saltutil.find_job' jobs
    '''
    with _get_serv(ret=None, commit=True) as cur:

        sql = '''SELECT * FROM (
                     SELECT DISTINCT `jid` ,`load` FROM `jids`
                     {0}
                     ORDER BY `jid` DESC limit {1}
                     ) `tmp`
                 ORDER BY `jid`;'''
        where = '''WHERE `load` NOT LIKE '%"fun": "saltutil.find_job"%' '''

        cur.execute(sql.format(where if filter_find_job else '', count))
        data = cur.fetchall()
        ret = []
        for jid in data:
            ret.append(salt.utils.jid.format_jid_instance_ext(jid[0],
                                                              json.loads(jid[1])))
        return ret


def get_minions():
    '''
    Return a list of minions
    '''
    with _get_serv(ret=None, commit=True) as cur:

        sql = '''SELECT DISTINCT id
                FROM `salt_returns`'''

        cur.execute(sql)
        data = cur.fetchall()
        ret = []
        for minion in data:
            ret.append(minion[0])
        return ret


def prep_jid(nocache=False, passed_jid=None):  # pylint: disable=unused-argument
    '''
    Do any work necessary to prepare a JID, including sending a custom id
    '''
    return passed_jid if passed_jid is not None else salt.utils.jid.gen_jid()
