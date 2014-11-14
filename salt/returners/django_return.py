# -*- coding: utf-8 -*-
'''
A returner that will infor a Django system that
returns are available using Django's signal system.

https://docs.djangoproject.com/en/dev/topics/signals/

It is up to the Django developer to register necessary
handlers with the signals provided by this returner
and process returns as necessary.

The easiest way to use signals is to import them from
this returner directly and then use a decorator to register
them.

An example Django module that registers a function called
'returner_callback' with this module's 'returner' function:

    .. code-block:: python

    import salt.returners.django_return
    from django.dispatch import receiver

    @receiver(salt.returners.django_return, sender=returner)
    def returner_callback(sender, ret):
        print('I received {0} from {1}'.format(ret, sender))

'''
# Import Python libraries
from __future__ import absolute_import
import logging

# Import Salt libraries
import salt.returners
import salt.utils

log = logging.getLogger(__name__)

HAS_DJANGO = False

try:
    from django import dispatch
    HAS_DJANGO = True
except ImportError:
    HAS_DJANGO = False

# Define this module's virtual name
__virtualname__ = 'django' 

def __virtual__():
    if not HAS_DJANGO:
        return False
    return True

def returner(ret):
    '''
    Signal a Django server that a return is available
    '''
    signaled = dispatch.Signal(providing_args=['ret']).send(sender='returner', ret=ret)

    for signal in signaled:
        log.debug('Django returner function \'returner\' signaled {0} '
                  'which responded with {1}'.format(signal[0], signal[1]))

def save_load(jid, load):
    '''
    Save the load to the specified jid
    '''
    signaled = dispatch.Signal(
        providing_args=['jid', 'load']).send(
            sender='save_load', jid=jid, load=load)

    for signal in signaled:
        log.debug('Django returner function \'save_load\' signaled {0} '
                  'which responded with {1}'.format(signal[0], signal[1]))

def prep_jid(nocache, passed_jid=None):
    '''
    Do any work necessary to prepare a JID, including sending a custom ID
    '''
    return passed_jid if passed_jid is not None else salt.utils.gen_jid()
