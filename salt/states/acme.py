# -*- coding: utf-8 -*-
'''
ACME / Let's Encrypt certificate management state
=================================================

.. versionadded: 2016.3

See also the module documentation

.. code-block:: yaml

    reload-gitlab:
      cmd.run:
        - name: gitlab-ctl hup

    dev.example.com:
      acme.cert:
        - aliases:
          - gitlab.example.com
        - email: acmemaster@example.com
        - webroot: /opt/gitlab/embedded/service/gitlab-rails/public
        - renew: 14
        - fire_event: acme/dev.example.com
        - onchanges_in:
          - cmd: reload-gitlab

'''
# Import python libs
from __future__ import absolute_import, print_function, unicode_literals
import logging

log = logging.getLogger(__name__)


def __virtual__():
    '''
    Only work when the ACME module agrees
    '''
    return 'acme.cert' in __salt__


def cert(name,
         aliases=None,
         email=None,
         webroot=None,
         test_cert=False,
         renew=None,
         keysize=None,
         server=None,
         owner='root',
         group='root',
         certname=None,
         preferred_challenges=None,
         tls_sni_01_port=None,
         tls_sni_01_address=None,
         http_01_port=None,
         http_01_address=None):
    '''
    Obtain/renew a certificate from an ACME CA, probably Let's Encrypt.

    :param name: Common Name of the certificate (DNS name of certificate)
    :param aliases: subjectAltNames (Additional DNS names on certificate)
    :param email: e-mail address for interaction with ACME provider
    :param webroot: True or a full path to webroot. Otherwise use standalone mode
    :param test_cert: Request a certificate from the Happy Hacker Fake CA (mutually exclusive with 'server')
    :param renew: True/'force' to force a renewal, or a window of renewal before expiry in days
    :param keysize: RSA key bits
    :param server: API endpoint to talk to
    :param owner: owner of private key
    :param group: group of private key
    :param certname: Name of the certificate to save
    :param preferred_challenges: A sorted, comma delimited list of the preferred
                                 challenge to use during authorization with the
                                 most preferred challenge listed first.
    :param tls_sni_01_port: Port used during tls-sni-01 challenge. This only affects
                            the port Certbot listens on. A conforming ACME server
                            will still attempt to connect on port 443.
    :param tls_sni_01_address: The address the server listens to during tls-sni-01
                               challenge.
    :param http_01_port: Port used in the http-01 challenge. This only affects
                         the port Certbot listens on. A conforming ACME server
                         will still attempt to connect on port 80.
    :param https_01_address: The address the server listens to during http-01 challenge.
    '''

    if __opts__['test']:
        ret = {
            'name': name,
            'changes': {},
            'result': None
        }
        window = None
        try:
            window = int(renew)
        except:  # pylint: disable=bare-except
            pass

        comment = 'Certificate {0} '.format(name)
        if not __salt__['acme.has'](name):
            comment += 'would have been obtained'
        elif __salt__['acme.needs_renewal'](name, window):
            comment += 'would have been renewed'
        else:
            comment += 'would not have been touched'
            ret['result'] = True
        ret['comment'] = comment
        return ret

    if not __salt__['acme.has'](name):
        old = None
    else:
        old = __salt__['acme.info'](name)

    res = __salt__['acme.cert'](
        name,
        aliases=aliases,
        email=email,
        webroot=webroot,
        certname=certname,
        test_cert=test_cert,
        renew=renew,
        keysize=keysize,
        server=server,
        owner=owner,
        group=group,
        preferred_challenges=preferred_challenges,
        tls_sni_01_port=tls_sni_01_port,
        tls_sni_01_address=tls_sni_01_address,
        http_01_port=http_01_port,
        http_01_address=http_01_address
    )

    ret = {
        'name': name,
        'result': res['result'] is not False,
        'comment': res['comment']
    }

    if res['result'] is None:
        ret['changes'] = {}
    else:
        if not __salt__['acme.has'](name):
            new = None
        else:
            new = __salt__['acme.info'](name)

        ret['changes'] = {
            'old': old,
            'new': new
        }

    return ret
