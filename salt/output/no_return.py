'''
Display output for minions that did not return
'''

import salt.utils

class NestDisplay(object):
    '''
    Create genreator for netsted output
    '''
    def __init__(self):
        self.colors = salt.utils.get_colors(__opts__.get('color'))

    def display(self, ret, indent, prefix, out):
        '''
        Recursively iterate down through data structures to determine output
        '''
        if isinstance(ret, str):
            lines = ret.split('\n')
            for line in lines:
                out += '{0}{1}{2}{3}{4}\n'.format(
                        self.colors['RED'],
                        ' ' * indent,
                        prefix,
                        line,
                        self.colors['ENDC'])
        elif isinstance(ret, dict):
            for key in sorted(ret):
                val = ret[key]
                out += '{0}{1}{2}{3}{4}:\n'.format(
                        self.colors['CYAN'],
                        ' ' * indent,
                        prefix,
                        key,
                        self.colors['ENDC'])
                out = self.display(val, indent + 4, '', out)
        return out

def output(ret):
    '''
    Display ret data
    '''
    nest = NestDisplay()
    return nest.display(ret, 0, '', '')
