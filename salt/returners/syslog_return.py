'''
Return data to the host operating system's syslog facility

Required python modules: syslog, json

Thi syslog returner simply reuses the operating system's syslog
facility to log return data
'''

import syslog
import json


def __virtual__():
    return 'syslog_return'


def returner(ret):
    '''
    Return data to the local syslog
    '''
    try:
        syslog.syslog(syslog.LOG_INFO,
                     "salt-minion: %s" %
                      json.dumps(ret))
    except ValueError:
        syslog.syslog(syslog.LOG_ERR,
                     "salt-minion: %s" %
                      ret)
    except Exception, e:
        raise e
