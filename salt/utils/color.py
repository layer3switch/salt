# -*- coding: utf-8 -*-
'''
Functions used for CLI color themes.
'''

# Import Python libs
from __future__ import absolute_import
import logging
import os

# Import Salt libs
from salt.ext import six
from salt.textformat import TextFormat
import salt.utils.files

log = logging.getLogger(__name__)


def get_color_theme(theme):
    '''
    Return the color theme to use
    '''
    # Keep the heavy lifting out of the module space
    import yaml
    if not os.path.isfile(theme):
        log.warning('The named theme {0} if not available'.format(theme))

    try:
        with salt.utils.files.fopen(theme, 'rb') as fp_:
            colors = yaml.safe_load(fp_.read())
            ret = {}
            for color in colors:
                ret[color] = '\033[{0}m'.format(colors[color])
            if not isinstance(colors, dict):
                log.warning('The theme file {0} is not a dict'.format(theme))
                return {}
            return ret
    except Exception:
        log.warning('Failed to read the color theme {0}'.format(theme))
        return {}


def get_colors(use=True, theme=None):
    '''
    Return the colors as an easy to use dict. Pass `False` to deactivate all
    colors by setting them to empty strings. Pass a string containing only the
    name of a single color to be used in place of all colors. Examples:

    .. code-block:: python

        colors = get_colors()  # enable all colors
        no_colors = get_colors(False)  # disable all colors
        red_colors = get_colors('RED')  # set all colors to red

    '''

    colors = {
        'BLACK': TextFormat('black'),
        'DARK_GRAY': TextFormat('bold', 'black'),
        'RED': TextFormat('red'),
        'LIGHT_RED': TextFormat('bold', 'red'),
        'GREEN': TextFormat('green'),
        'LIGHT_GREEN': TextFormat('bold', 'green'),
        'YELLOW': TextFormat('yellow'),
        'LIGHT_YELLOW': TextFormat('bold', 'yellow'),
        'BLUE': TextFormat('blue'),
        'LIGHT_BLUE': TextFormat('bold', 'blue'),
        'MAGENTA': TextFormat('magenta'),
        'LIGHT_MAGENTA': TextFormat('bold', 'magenta'),
        'CYAN': TextFormat('cyan'),
        'LIGHT_CYAN': TextFormat('bold', 'cyan'),
        'LIGHT_GRAY': TextFormat('white'),
        'WHITE': TextFormat('bold', 'white'),
        'DEFAULT_COLOR': TextFormat('default'),
        'ENDC': TextFormat('reset'),
    }
    if theme:
        colors.update(get_color_theme(theme))

    if not use:
        for color in colors:
            colors[color] = ''
    if isinstance(use, six.string_types):
        # Try to set all of the colors to the passed color
        if use in colors:
            for color in colors:
                # except for color reset
                if color == 'ENDC':
                    continue
                colors[color] = colors[use]

    return colors
