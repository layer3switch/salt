# -*- coding: utf-8 -*-
# Import Python libs
from __future__ import absolute_import
import os
import re
import logging
from jinja2 import FileSystemLoader, Environment

# Import Salt libs
import salt.utils.path
import salt.utils.yaml

# Import 3rd-party libs
from salt.ext.six import iteritems

log = logging.getLogger(__name__)


# Renders jinja from a template file
def render_jinja(_file, salt_data):
    j_env = Environment(loader=FileSystemLoader(os.path.dirname(_file)))
    j_env.globals.update({
        '__opts__': salt_data['__opts__'],
        '__salt__': salt_data['__salt__'],
        '__grains__': salt_data['__grains__'],
        '__pillar__': salt_data['__pillar__'],
        'minion_id': salt_data['minion_id'],
    })
    j_render = j_env.get_template(os.path.basename(_file)).render()
    return j_render


# Renders yaml from rendered jinja
def render_yaml(_file, salt_data):
    return salt.utils.yaml.safe_load(render_jinja(_file, salt_data))


# Returns a dict from a class yaml definition
def get_class(_class, salt_data):
    l_files = []
    saltclass_path = salt_data['path']

    straight = '{0}/classes/{1}.yml'.format(saltclass_path, _class)
    sub_straight = '{0}/classes/{1}.yml'.format(saltclass_path,
                                                _class.replace('.', '/'))
    sub_init = '{0}/classes/{1}/init.yml'.format(saltclass_path,
                                                 _class.replace('.', '/'))

    for root, dirs, files in salt.utils.path.os_walk('{0}/classes'.format(saltclass_path)):
        for l_file in files:
            l_files.append('{0}/{1}'.format(root, l_file))

    if straight in l_files:
        return render_yaml(straight, salt_data)

    if sub_straight in l_files:
        return render_yaml(sub_straight, salt_data)

    if sub_init in l_files:
        return render_yaml(sub_init, salt_data)

    log.warning('{0}: Class definition not found'.format(_class))
    return {}


# Return environment
def get_env_from_dict(exp_dict_list):
    environment = ''
    for s_class in exp_dict_list:
        if 'environment' in s_class:
            environment = s_class['environment']
    return environment


# Merge dict b into a
def dict_merge(a, b, path=None):
    if path is None:
        path = []

    for key in b:
        if key in a:
            if isinstance(a[key], list) and isinstance(b[key], list):
                if b[key][0] == '^':
                    b[key].pop(0)
                    a[key] = b[key]
                else:
                    a[key].extend(b[key])
            elif isinstance(a[key], dict) and isinstance(b[key], dict):
                dict_merge(a[key], b[key], path + [str(key)])
            elif a[key] == b[key]:
                pass
            else:
                a[key] = b[key]
        else:
            a[key] = b[key]
    return a


# Recursive search and replace in a dict
def dict_search_and_replace(d, old, new, expanded):
    for (k, v) in iteritems(d):
        if isinstance(v, dict):
            dict_search_and_replace(d[k], old, new, expanded)
        if v == old:
            d[k] = new
    return d


# Retrieve original value from ${xx:yy:zz} to be expanded
def find_value_to_expand(x, v):
    a = x
    for i in v[2:-1].split(':'):
        if a is None:
            return v
        if i in a:
            a = a.get(i)
        else:
            return v
    return a


# Return a dict that contains expanded variables if found
def expand_variables(a, b, expanded, path=None):
    if path is None:
        b = a.copy()
        path = []

    for (k, v) in iteritems(a):
        if isinstance(v, dict):
            expand_variables(v, b, expanded, path + [str(k)])
        else:
            if isinstance(v, str):
                vre = re.search(r'(^|.)\$\{.*?\}', v)
                if vre:
                    re_v = vre.group(0)
                    if re_v.startswith('\\'):
                        v_new = v.replace(re_v, re_v.lstrip('\\'))
                        b = dict_search_and_replace(b, v, v_new, expanded)
                        expanded.append(k)
                    elif not re_v.startswith('$'):
                        v_expanded = find_value_to_expand(b, re_v[1:])
                        v_new = v.replace(re_v[1:], v_expanded)
                        b = dict_search_and_replace(b, v, v_new, expanded)
                        expanded.append(k)
                    else:
                        v_expanded = find_value_to_expand(b, re_v)
                        b = dict_search_and_replace(b, v, v_expanded, expanded)
                        expanded.append(k)
    return b


def expand_classes_in_order(minion_dict,
                            salt_data,
                            seen_classes,
                            expanded_classes,
                            classes_to_expand):
    # Get classes to expand from minion dictionnary
    if not classes_to_expand and 'classes' in minion_dict:
        classes_to_expand = minion_dict['classes']

    # Now loop on list to recursively expand them
    for klass in classes_to_expand:
        if klass not in seen_classes:
            seen_classes.append(klass)
            expanded_classes[klass] = get_class(klass, salt_data)
            # Fix corner case where class is loaded but doesn't contain anything
            if expanded_classes[klass] is None:
                expanded_classes[klass] = {}
            # Now replace class element in classes_to_expand by expansion
            if 'classes' in expanded_classes[klass]:
                l_id = classes_to_expand.index(klass)
                classes_to_expand[l_id:l_id] = expanded_classes[klass]['classes']
                expand_classes_in_order(minion_dict,
                                        salt_data,
                                        seen_classes,
                                        expanded_classes,
                                        classes_to_expand)
            else:
                expand_classes_in_order(minion_dict,
                                        salt_data,
                                        seen_classes,
                                        expanded_classes,
                                        classes_to_expand)

    # We may have duplicates here and we want to remove them
    tmp = []
    for t_element in classes_to_expand:
        if t_element not in tmp:
            tmp.append(t_element)

    classes_to_expand = tmp

    # Now that we've retrieved every class in order,
    # let's return an ordered list of dicts
    ord_expanded_classes = []
    ord_expanded_states = []
    for ord_klass in classes_to_expand:
        ord_expanded_classes.append(expanded_classes[ord_klass])
        # And be smart and sort out states list
        # Address the corner case where states is empty in a class definition
        if 'states' in expanded_classes[ord_klass] and expanded_classes[ord_klass]['states'] is None:
            expanded_classes[ord_klass]['states'] = {}

        if 'states' in expanded_classes[ord_klass]:
            ord_expanded_states.extend(expanded_classes[ord_klass]['states'])

    # Add our minion dict as final element but check if we have states to process
    if 'states' in minion_dict and minion_dict['states'] is None:
        minion_dict['states'] = []

    if 'states' in minion_dict:
        ord_expanded_states.extend(minion_dict['states'])

    ord_expanded_classes.append(minion_dict)

    return ord_expanded_classes, classes_to_expand, ord_expanded_states


def expanded_dict_from_minion(minion_id, salt_data):
    _file = ''
    saltclass_path = salt_data['path']
    # Start
    for root, dirs, files in salt.utils.path.os_walk('{0}/nodes'.format(saltclass_path)):
        for minion_file in files:
            if minion_file == '{0}.yml'.format(minion_id):
                _file = os.path.join(root, minion_file)

    # Load the minion_id definition if existing, else an exmpty dict
    node_dict = {}
    if _file:
        node_dict[minion_id] = render_yaml(_file, salt_data)
    else:
        log.warning('{0}: Node definition not found'.format(minion_id))
        node_dict[minion_id] = {}

    # Get 2 ordered lists:
    # expanded_classes: A list of all the dicts
    # classes_list: List of all the classes
    expanded_classes, classes_list, states_list = expand_classes_in_order(
                                                    node_dict[minion_id],
                                                    salt_data, [], {}, [])

    # Here merge the pillars together
    pillars_dict = {}
    for exp_dict in expanded_classes:
        if 'pillars' in exp_dict:
            dict_merge(pillars_dict, exp_dict)

    return expanded_classes, pillars_dict, classes_list, states_list


def get_pillars(minion_id, salt_data):
    # Get 2 dicts and 2 lists
    # expanded_classes: Full list of expanded dicts
    # pillars_dict: dict containing merged pillars in order
    # classes_list: All classes processed in order
    # states_list: All states listed in order
    (expanded_classes,
     pillars_dict,
     classes_list,
     states_list) = expanded_dict_from_minion(minion_id, salt_data)

    # Retrieve environment
    environment = get_env_from_dict(expanded_classes)

    # Expand ${} variables in merged dict
    # pillars key shouldn't exist if we haven't found any minion_id ref
    if 'pillars' in pillars_dict:
        pillars_dict_expanded = expand_variables(pillars_dict['pillars'], {}, [])
    else:
        pillars_dict_expanded = expand_variables({}, {}, [])

    # Build the final pillars dict
    pillars_dict = {}
    pillars_dict['__saltclass__'] = {}
    pillars_dict['__saltclass__']['states'] = states_list
    pillars_dict['__saltclass__']['classes'] = classes_list
    pillars_dict['__saltclass__']['environment'] = environment
    pillars_dict['__saltclass__']['nodename'] = minion_id
    pillars_dict.update(pillars_dict_expanded)

    return pillars_dict


def get_tops(minion_id, salt_data):
    # Get 2 dicts and 2 lists
    # expanded_classes: Full list of expanded dicts
    # pillars_dict: dict containing merged pillars in order
    # classes_list: All classes processed in order
    # states_list: All states listed in order
    (expanded_classes,
     pillars_dict,
     classes_list,
     states_list) = expanded_dict_from_minion(minion_id, salt_data)

    # Retrieve environment
    environment = get_env_from_dict(expanded_classes)

    # Build final top dict
    tops_dict = {}
    tops_dict[environment] = states_list

    return tops_dict
