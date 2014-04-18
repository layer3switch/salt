# -*- coding: utf-8 -*-
'''
Pure python state renderer

The SLS file should contain a function called ``run`` which returns high state
data.

In this module, a few objects are defined for you, giving access to Salt's
execution functions, grains, pillar, etc. They are:

* ``__salt__`` - :ref:`Execution functions <all-salt.modules>` (i.e.
  ``__salt__['test.echo']('foo')``)
* ``__grains__`` - :ref:`Grains <targeting-grains>` (i.e. ``__grains__['os']``)
* ``__pillar__`` - :ref:`Pillar data <pillar>` (i.e. ``__pillar__['foo']``)
* ``__opts__`` - Minion configuration options
* ``__env__`` - The effective salt fileserver environment
* ``__sls__`` - The SLS path of the file. For example, if the root of the base
  environment is ``/srv/salt``, and the SLS file is
  ``/srv/salt/foo/bar/baz.sls``, then ``__sls__`` in that file will be
  ``foo.bar.baz``.


.. code-block:: python
   :linenos:

    #!py

    def run():
        config = {}

        if __grains__['os'] == 'Ubuntu':
            user = 'ubuntu'
            group = 'ubuntu'
            home = '/home/{0}'.format(user)
        else:
            user = 'root'
            group = 'root'
            home = '/root/'

        config['s3cmd'] = {
            'pkg': [
                'installed',
                {'name': 's3cmd'},
            ],
        }

        config[home + '/.s3cfg'] = {
            'file.managed': [
                {'source': 'salt://s3cfg/templates/s3cfg'},
                {'template': 'jinja'},
                {'user': user},
                {'group': group},
                {'mode': 600},
                {'context': {
                    'aws_key': __pillar__['AWS_ACCESS_KEY_ID'],
                    'aws_secret_key': __pillar__['AWS_SECRET_ACCESS_KEY'],
                    },
                },
            ],
        }

        return config

'''

# Import python libs
import os

# Import salt libs
from salt.exceptions import SaltRenderError
import salt.utils.templates


def render(template, saltenv='base', sls='', tmplpath=None, **kws):
    '''
    Render the python module's components

    :rtype: string
    '''
    template = tmplpath
    if not os.path.isfile(template):
        raise SaltRenderError('Template {0} is not a file!'.format(template))

    tmp_data = salt.utils.templates.py(
            template,
            True,
            __salt__=__salt__,
            salt=__salt__,
            __grains__=__grains__,
            grains=__grains__,
            __opts__=__opts__,
            opts=__opts__,
            __pillar__=__pillar__,
            pillar=__pillar__,
            __env__=saltenv,
            saltenv=saltenv,
            __sls__=sls,
            sls=sls,
            **kws)
    if not tmp_data.get('result', False):
        raise SaltRenderError(tmp_data.get('data',
            'Unknown render error in py renderer'))

    return tmp_data['data']
