# -*- coding: utf-8 -*-
'''
Special outputter for grains
============================

This outputter is a more condensed version of the :mod:`nested
<salt.output.nested>` outputter, used by default to display grains when the
following functions are invoked:

* :mod:`grains.item <salt.modules.grains.item>`
* :mod:`grains.items <salt.modules.grains.items>`
* :mod:`grains.setval <salt.modules.grains.setval>`

Example output::

    myminion:
      dictionary: {'abc': 123, 'def': 456}
      list:
          Hello
          World
      bar: baz
'''

# Import python libs
from __future__ import absolute_import

# Import salt libs
import salt.utils

# Import 3rd-party libs
import salt.ext.six as six


def output(grains):
    '''
    Output the grains in a clean way
    '''
    colors = salt.utils.get_colors(__opts__.get('color'), __opts__.get('color_theme'))
    # find an encoding
    encoding = 'unknown'  # default to unknown
    # find *an* encoding
    for _, min_grains in grains.iteritems():
        if 'defaultencoding' in min_grains.get('locale_info', {}):
            encoding = min_grains['locale_info']['defaultencoding']
            break
    if encoding == 'unknown':
        encoding = 'utf-8'  # let's hope for the best


    ret = u''
    for id_, minion in six.iteritems(grains):
        ret += u'{0}{1}{2}:\n'.format(colors['GREEN'], id_.decode(encoding), colors['ENDC'])
        for key in sorted(minion):
            ret += u'  {0}{1}{2}:'.format(colors['CYAN'], key.decode(encoding), colors['ENDC'])
            if key == 'cpu_flags':
                ret += str(colors['LIGHT_GREEN'])
                for val in minion[key]:
                    ret += u' {0}'.format(val.decode(encoding))
                ret += '{0}\n'.format(colors['ENDC'])
            elif key == 'pythonversion':
                ret += ' {0}'.format(colors['LIGHT_GREEN'])
                for val in minion[key]:
                    ret += u'{0}.'.format(six.text_type(val))
                ret = ret[:-1]
                ret += '{0}\n'.format(colors['ENDC'])
            elif isinstance(minion[key], list):
                for val in minion[key]:
                    ret += u'\n      {0}{1}{2}'.format(colors['LIGHT_GREEN'], str(val).decode(encoding), colors['ENDC'])
                ret += '\n'
            else:
                ret += u' {0}{1}{2}\n'.format(colors['LIGHT_GREEN'], str(minion[key]).decode(encoding), colors['ENDC'])
    return ret
