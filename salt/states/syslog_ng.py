# -*- coding: utf-8 -*-
"""
State module for syslog_ng
==========================

:maintainer:    Tibor Benke <btibi@sch.bme.hu>
:maturity:      new
:depends:       cmd, ps
:platform:      all

Users can generate syslog-ng configuration files from YAML format by using
this module or use plain ones and reload, start, or stop their syslog-ng.

Details
-------

The service module is not available on all system, so this module includes
:mod:`syslog_ng.reloaded <salt.states.syslog_ng.reloaded>`,
:mod:`syslog_ng.stopped <salt.states.syslog_ng.stopped>`,
and :mod:`syslog_ng.started <salt.states.syslog_ng.started>` functions.
If the service module is available on the computers, users should use that.

Syslog-ng can be installed via a package manager or from source. In the
latter case, the syslog-ng and syslog-ng-ctl binaries are not available
from the PATH, so users should set location of the sbin directory with
:mod:`syslog_ng.set_binary_path <salt.states.syslog_ng.set_binary_path>`.

Similarly, users can specify the location of the configuration file with
:mod:`syslog_ng.set_config_file <salt.states.syslog_ng.set_config_file>`, then
the module will use it. If it is not set, syslog-ng use the default
configuration file.

For more information see :doc:`syslog-ng state usage </topics/tutorials/syslog_ng-state-usage>`.

Syslog-ng configuration file format
-----------------------------------

The syntax of a configuration snippet in syslog-ng.conf:

    ..

        object_type object_id {<options>};


These constructions are also called statements. There are options inside of them:

    ..

        option(parameter1, parameter2); option2(parameter1, parameter2);

You can find more information about syslog-ng's configuration syntax in the
Syslog-ng Admin guide: http://www.balabit.com/sites/default/files/documents/syslog-ng-ose-3.5-guides/en/syslog-ng-ose-v3.5-guide-admin/html-single/index.html#syslog-ng.conf.5
"""

from __future__ import generators, print_function, with_statement
import cStringIO
import os
import os.path
import logging

from time import strftime
from salt.exceptions import SaltInvocationError

log = logging.getLogger(__name__)
log.setLevel(logging.DEBUG)

_STATEMENT_NAMES = ("source", "destination", "log", "parser", "rewrite",
                    "template", "channel", "junction", "filter", "options")
__SYSLOG_NG_CONFIG_FILE = "/etc/syslog-ng.conf"
__SYSLOG_NG_BINARY_PATH = None
__SALT_GENERATED_CONFIG_HEADER = """#Generated by Salt on {0}"""


class SyslogNgError(Exception):
    pass


def _get_not_None_params(params):
    '''
    Returns the not None elements or params.
    '''
    return filter(lambda x: params[x], params)


def _is_statement_unnamed(statement):
    '''
    Returns True, if the given statement is an unnamed statement, like log or
    junction.

    '''
    return statement in ("log", "channel", "junction", "options")


def _is_statement(name, content):
    '''
    Returns True, if the given name is a statement name and based on the
    content it's a statement.
    '''
    return name in _STATEMENT_NAMES and isinstance(content, list) and \
           (_is_all_element_has_type(content, dict) or
            (len(content) > 1 and _is_all_element_has_type(content[1:], dict) and
             (isinstance(content[0], str) or isinstance(content[0], dict))))


def _is_all_elements_simple_type(container):
    '''
    Returns True, if the given container only has simple types, like int, float, str.
    '''
    return all(map(_is_simple_type, container))


def _is_all_element_has_type(container, type):
    '''
    Returns True, if all elements in container are instances of the given type.
    '''
    return all(map(lambda x: isinstance(x, type), container))


def _is_reference(parent, this, state_stack):
    '''
    Returns True, if the parameters are referring to a formerly created
    statement, like: source(s_local);
    '''
    return isinstance(parent, str) and _is_simple_type(this) and state_stack[-1] == 0


def _is_options(parent, this, state_stack):
    '''
    Returns True, if the given parameter this is a list of options.

    '''
    return isinstance(parent, str) and isinstance(this, list) and state_stack[-1] == 0


def _are_parameters(this, state_stack):
    '''
    Returns True, if the given parameter this is a list of parameters.
    '''
    return isinstance(this, list) and state_stack[-1] == 1


def _is_simple_type(value):
    '''
    Returns True, if the given parameter value is an instance of either
    int, str, float or bool.
    '''
    return isinstance(value, str) or isinstance(value, int) or isinstance(value, float) or isinstance(value, bool)


def _is_simple_parameter(this, state_stack):
    '''
    Return True, if the given argument this is a parameter and a simple type.
    '''
    return state_stack[-1] == 2 and (_is_simple_type(this))


def _is_complex_parameter(this, state_stack):
    '''
    Return True, if the given argument this is a parameter and an instance of
    dict.
    '''
    return state_stack[-1] == 2 and isinstance(this, dict)


def _is_list_parameter(this, state_stack):
    '''
    Returns True, if the given argument this is inside a parameter and it's
    type is list.
    '''
    return state_stack[-1] == 3 and isinstance(this, list)


def _is_string_parameter(this, state_stack):
    '''
    Returns True, if the given argument this is inside a parameter and it's
    type is str.
    '''
    return state_stack[-1] == 3 and isinstance(this, str)


def _is_int_parameter(this, state_stack):
    '''
    Returns True, if the given argument this is inside a parameter and it's
    type is int.
    '''
    return state_stack[-1] == 3 and isinstance(this, int)


def _is_boolean_parameter(this, state_stack):
    '''
    Returns True, if the given argument this is inside a parameter and it's
    type is bool.
    '''
    return state_stack[-1] == 3 and isinstance(this, bool)


def _build_statement(id, parent, this, indent, buffer, state_stack):
    '''
    Builds a configuration snippet which represents a statement, like log,
    junction, etc.

    :param id: the name of the statement
    :param parent: the type of the statement
    :param this: the body
    :param indent: indentation before every line
    :param buffer: the configuration is written into this
    :param state_stack: a list, which represents the position in the configuration tree
    '''
    if _is_statement_unnamed(parent) or len(state_stack) > 1:
        print("{0}{1}".format(indent, parent) + " {", file=buffer)
    else:
        print("{0}{1} {2}".format(indent, parent, id) + " {", file=buffer)
    for i in this:
        if isinstance(i, dict):
            key = i.keys()[0]
            value = i[key]
            state_stack.append(0)
            print(_build_config(id, key, value, state_stack=state_stack), file=buffer)
            state_stack.pop()
    print("{0}".format(indent) + "};", file=buffer, end="")


def _build_complex_parameter(id, this, indent, state_stack):
    '''
    Builds the configuration of a complex parameter (contains more than one item).
    '''
    state_stack.append(3)
    key = this.keys()[0]
    value = this[key]
    begin = "{0}{1}(".format(indent, key)
    content = _build_config(id, key, value, state_stack)
    end = ")"
    state_stack.pop()
    return begin + content + end


def _build_simple_parameter(this, indent):
    '''
    Builds the configuration of a simple parameter.
    '''
    try:
        float(this)
        return indent + this
    except ValueError:
        if isinstance(this, str) and _string_needs_quotation(this):
            return '{0}"{1}"'.format(indent, this)
        else:
            return '{0}{1}'.format(indent, this)


def _build_parameters(id, parent, this, buffer, state_stack):
    '''
    Iterates over the list of parameters and builds the configuration.
    '''
    state_stack.append(2)
    params = [_build_config(id, parent, i, state_stack=state_stack) for i in this]
    print(",\n".join(params), file=buffer)
    state_stack.pop()


def _build_options(id, parent, this, indent, buffer, state_stack):
    '''
    Builds the options' configuration inside of a statement.
    '''
    state_stack.append(1)
    print("{0}{1}(".format(indent, parent), file=buffer)
    print(_build_config(id, parent, this, state_stack=state_stack), file=buffer, end="")
    print(indent + ");", file=buffer, end="")
    state_stack.pop()


def _string_needs_quotation(string):
    '''
    Return True, if the given parameter string has special characters, so it
    needs quotation.
    '''
    need_quotation_chars = "$@:/."

    for i in need_quotation_chars:
        if i in string:
            return True
    return False


def _build_string_parameter(this):
    '''
    Builds the config of a simple string parameter.
    '''
    if _string_needs_quotation(this):
        return '"{0}"'.format(this)
    else:
        return this


def _build_config(salt_id, parent, this, state_stack):
    '''
    Builds syslog-ng configuration from a parsed YAML document. It maintains
    a state_stack list, which represents the current position in the
    configuration tree.

    The last value in the state_stack means:
        0: in the root or in a statement
        1: in an option
        2: in a parameter
        3: in a parameter of a parameter

    Returns the built config.
    '''
    buffer = cStringIO.StringIO()

    deepness = len(state_stack) - 1
    # deepness based indentation
    indent = "{0}".format(deepness * "   ")

    if _is_statement(parent, this):
        _build_statement(salt_id, parent, this, indent, buffer, state_stack)
    elif _is_reference(parent, this, state_stack):
        print("{0}{1}({2});".format(indent, parent, this), file=buffer, end="")
    elif _is_options(parent, this, state_stack):
        _build_options(salt_id, parent, this, indent, buffer, state_stack)
    elif _are_parameters(this, state_stack):
        _build_parameters(salt_id, parent, this, buffer, state_stack)
    elif _is_simple_parameter(this, state_stack):
        return _build_simple_parameter(this, indent)
    elif _is_complex_parameter(this, state_stack):
        return _build_complex_parameter(salt_id, this, indent, state_stack)
    elif _is_list_parameter(this, state_stack):
        return ", ".join(this)
    elif _is_string_parameter(this, state_stack):
        return _build_string_parameter(this)
    elif _is_int_parameter(this, state_stack):
        return str(this)
    elif _is_boolean_parameter(this, state_stack):
        return "no" if this else "yes"
    else:
        # It's an unhandled case
        print("{0}# BUG, please report to the syslog-ng mailing list: syslog-ng@lists.balabit.hu".format(indent),
              file=buffer,
              end="")
        raise SyslogNgError("Unhandled case while generating configuration from YAML to syslog-ng format")

    buffer.seek(0)
    return buffer.read()


def _format_state_result(name, result, changes=None, comment=""):
    '''
    Creates the state result dictionary.
    '''
    if changes is None:
        changes = {"old": "", "new": ""}
    return {"name": name, "result": result, "changes": changes, "comment": comment}


def config(name,
           config,
           write=True):
    '''
    Builds syslog-ng configuration.

    name : the id of the Salt document
    config : the parsed YAML code
    write : if True, it writes  the config into the configuration file,
    otherwise just returns it
    '''
    if not isinstance(config, dict):
        log.debug("Config is: " + str(config))
        raise SaltInvocationError("The config parameter must be a dictionary")

    statement = config.keys()[0]

    stack = [0]
    configs = _build_config(name, parent=statement, this=config[statement], state_stack=stack)

    succ = write
    if write:
        succ = _write_config(config=configs)

    return _format_state_result(name, result=succ, changes={"new": configs, "old": ""})


def _format_generated_config_header():
    '''
    Formats a header, which is prepended to all appended config.
    '''
    now = strftime("%Y-%m-%d %H:%M:%S")
    return __SALT_GENERATED_CONFIG_HEADER.format(now)


def set_config_file(name):
    '''
    Sets the configuration's name.
    '''
    global __SYSLOG_NG_CONFIG_FILE
    old = __SYSLOG_NG_CONFIG_FILE
    __SYSLOG_NG_CONFIG_FILE = name
    return _format_state_result(name, result=True, changes={"new": name, "old": old})


def get_config_file():
    '''
    Returns the configuration directory, which contains syslog-ng.conf.
    '''
    return __SYSLOG_NG_CONFIG_FILE


def write_config(name, config, newlines=2):
    '''
    Writes the given parameter config into the config file.
    '''
    succ = _write_config(config, newlines)
    return _format_state_result("name", result=succ)


def _write_config(config, newlines=2):
    '''
    Writes the given parameter config into the config file.
    '''
    text = config
    if isinstance(config, dict) and len(config.keys()) == 1:
        key = config.keys()[0]
        text = config[key]

    try:
        open_flags = "a"

        with open(__SYSLOG_NG_CONFIG_FILE, open_flags) as f:
            f.write(text)

            for i in range(0, newlines):
                f.write(os.linesep)

        return True
    except Exception as err:
        log.error(str(err))
        return False


def write_version(name):
    '''
    Removes the previous configuration file, then creates a new one and writes the name line.
    '''
    line = "@version: {0}".format(name)
    try:
        if os.path.exists(__SYSLOG_NG_CONFIG_FILE):
            log.debug("Removing previous configuration file: {0}".format(__SYSLOG_NG_CONFIG_FILE))
            os.remove(__SYSLOG_NG_CONFIG_FILE)
            log.debug("Configuration file successfully removed")

        header = _format_generated_config_header()
        _write_config(config=header, newlines=1)
        _write_config(config=line, newlines=2)

        return _format_state_result(name, result=True)
    except os.error as err:
        log.error(
            "Failed to remove previous configuration file '{0}' because: {1}".format(__SYSLOG_NG_CONFIG_FILE, str(err)))
        return _format_state_result(name, result=False)


def set_binary_path(name):
    '''
    Sets the path, where the syslog-ng binary can be found.

    If syslog-ng is installed via a package manager, users don't need to use
    this function.
    '''
    global __SYSLOG_NG_BINARY_PATH
    __SYSLOG_NG_BINARY_PATH = name
    return _format_state_result(name, result=True)


def _add_cli_param(params, key, value):
    '''
    Adds key and value as a command line parameter to params.
    '''
    if value is not None:
        params.append("--{0}={1}".format(key, value))


def _add_boolean_cli_param(params, key, value):
    '''
    Adds key as a command line parameter to params.
    '''
    if value is True:
        params.append("--{0}".format(key))


def stopped(name=None):
    '''
    Kills syslog-ng.
    '''
    pids = __salt__["ps.pgrep"](pattern="syslog-ng")

    if pids is None or len(pids) == 0:
        return _format_state_result(name, result=False, comment="Syslog-ng is not running")

    res = __salt__["ps.pkill"]("syslog-ng")
    killed_pids = res["killed"]

    if killed_pids == pids:
        changes = {"old": killed_pids, "new": []}
        return _format_state_result(name, result=True, changes=changes)
    else:
        return _format_state_result(name, result=False)


def started(name=None,
            user=None,
            group=None,
            chroot=None,
            caps=None,
            no_caps=False,
            pidfile=None,
            enable_core=False,
            fd_limit=None,
            verbose=False,
            debug=False,
            trace=False,
            yydebug=False,
            persist_file=None,
            control=None,
            worker_threads=None,
            *args,
            **kwargs):
    '''
    Ensures, that syslog-ng is started via the given parameters.

    Users shouldn't use this function, if the service module is available on
    their system.
    '''
    params = []
    _add_cli_param(params, "user", user)
    _add_cli_param(params, "group", group)
    _add_cli_param(params, "chroot", chroot)
    _add_cli_param(params, "caps", caps)
    _add_boolean_cli_param(params, "no-capse", no_caps)
    _add_cli_param(params, "pidfile", pidfile)
    _add_boolean_cli_param(params, "enable-core", enable_core)
    _add_cli_param(params, "fd-limit", fd_limit)
    _add_boolean_cli_param(params, "verbose", verbose)
    _add_boolean_cli_param(params, "debug", debug)
    _add_boolean_cli_param(params, "trace", trace)
    _add_boolean_cli_param(params, "yydebug", yydebug)
    _add_cli_param(params, "cfgfile", __SYSLOG_NG_CONFIG_FILE)
    _add_boolean_cli_param(params, "persist-file", persist_file)
    _add_cli_param(params, "control", control)
    _add_cli_param(params, "worker-threads", worker_threads)
    cli_params = " ".join(params)
    if __SYSLOG_NG_BINARY_PATH:
        syslog_ng_binary = os.path.join(__SYSLOG_NG_BINARY_PATH, "syslog-ng")
        command = syslog_ng_binary + " " + cli_params
        result = __salt__["cmd.run_all"](command)
    else:
        command = "syslog-ng " + cli_params
        result = __salt__["cmd.run_all"](command)

    if result["pid"] > 0:
        succ = True
    else:
        succ = False

    return _format_state_result(name, result=succ, changes={"new": command, "old": ""})


def reloaded(name):
    '''
    Reloads syslog-ng.
    '''
    if __SYSLOG_NG_BINARY_PATH:
        syslog_ng_ctl_binary = os.path.join(__SYSLOG_NG_BINARY_PATH, "syslog-ng-ctl")
        command = syslog_ng_ctl_binary + " reload"
        result = __salt__["cmd.run_all"](command)
    else:
        command = "syslog-ng-ctl reload"
        result = __salt__["cmd.run_all"](command)

    succ = True if result["retcode"] == 0 else False
    return _format_state_result(name, result=succ, comment=result["stdout"])
