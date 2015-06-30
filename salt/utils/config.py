# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Pedro Algarvio (pedro@algarvio.me)`


    salt.utils.config
    ~~~~~~~~~~~~~~~~~

    Object Oriented Configuration - JSON Schema compatible generator

    This code was inspired by `jsl`__, "A Python DSL for describing JSON schemas".

    .. __: http://jsl.readthedocs.org/


    A configuration document or configuration document section is defined using the
    py:class:`Configuration`, the configuration items are defined by any of the subclasses
    of py:class:`BaseConfigItem` as attributes of a subclass of py:class:`Configuration` class.

    As an example:

    .. code-block:: python

        class HostConfig(Configuration):
            title = 'Host Configuration'
            description = 'This is the host configuration'

            host = StringConfig(
                'Host',
                'The looong host description',
                default=None,
                minimum=1
            )

            port = NumberConfig(
                description='The port number',
                default=80,
                required=False,
                minimum=0,
                inclusiveMinimum=False,
                maximum=65535
            )

    The serialized version of the above configuration definition is:

    .. code-block:: python

        >>> print(HostConfig.serialize())
        OrderedDict([
            ('$schema', 'http://json-schema.org/draft-04/schema#'),
            ('title', 'Host Configuration'),
            ('description', 'This is the host configuration'),
            ('type', 'object'),
            ('properties', OrderedDict([
                ('host', {'minimum': 1,
                          'type': 'string',
                          'description': 'The looong host description',
                          'title': 'Host'}),
                ('port', {'description': 'The port number',
                          'default': 80,
                          'inclusiveMinimum': False,
                          'maximum': 65535,
                          'minimum': 0,
                          'type': 'number'})
            ])),
            ('required', ['host']),
            ('x-ordering', ['host', 'port']),
            ('additionalProperties', True)]
        )
        >>> print(json.dumps(HostConfig.serialize(), indent=2))
        {
            "$schema": "http://json-schema.org/draft-04/schema#",
            "title": "Host Configuration",
            "description": "This is the host configuration",
            "type": "object",
            "properties": {
                "host": {
                    "minimum": 1,
                    "type": "string",
                    "description": "The looong host description",
                    "title": "Host"
                },
                "port": {
                    "description": "The port number",
                    "default": 80,
                    "inclusiveMinimum": false,
                    "maximum": 65535,
                    "minimum": 0,
                    "type": "number"
                }
            },
            "required": [
                "host"
            ],
            "x-ordering": [
                "host",
                "port"
            ],
            "additionalProperties": false
        }


    The serialized version of the configuration block can be used to validate a configuration dictionary using
    the `python jsonschema library`__.

    .. __: https://pypi.python.org/pypi/jsonschema

    .. code-block:: python

        >>> import jsonschema
        >>> jsonschema.validate({'host': 'localhost', 'port': 80}, HostConfig.serialize())
        >>> jsonschema.validate({'host': 'localhost', 'port': -1}, HostConfig.serialize())
        Traceback (most recent call last):
        File "<stdin>", line 1, in <module>
        File "/usr/lib/python2.7/site-packages/jsonschema/validators.py", line 478, in validate
            cls(schema, *args, **kwargs).validate(instance)
        File "/usr/lib/python2.7/site-packages/jsonschema/validators.py", line 123, in validate
            raise error
        jsonschema.exceptions.ValidationError: -1 is less than the minimum of 0

        Failed validating 'minimum' in schema['properties']['port']:
            {'default': 80,
            'description': 'The port number',
            'inclusiveMinimum': False,
            'maximum': 65535,
            'minimum': 0,
            'type': 'number'}

        On instance['port']:
            -1
        >>>


    A configuration document can even be split into configuration sections. Let's reuse the above
    ``HostConfig`` class and include it in a configuration block:

    .. code-block:: python

        class LoggingConfig(Configuration):
            title = 'Logging Configuration'
            description = 'This is the logging configuration'

            log_level = StringConfig(
                'Logging Level',
                'The logging level',
                default='debug',
                minimum=1
            )

        class MyConfig(Configuration):

            title = 'My Config'
            description = 'This my configuration'

            hostconfig = HostConfig()
            logconfig = LoggingConfig()


    The JSON Schema string version of the above is:

    .. code-block:: python

        >>> print json.dumps(MyConfig.serialize(), indent=4)
        {
            "$schema": "http://json-schema.org/draft-04/schema#",
            "title": "My Config",
            "description": "This my configuration",
            "type": "object",
            "properties": {
                "hostconfig": {
                    "id": "https://non-existing.saltstack.com/schemas/hostconfig.json#",
                    "title": "Host Configuration",
                    "description": "This is the host configuration",
                    "type": "object",
                    "properties": {
                        "host": {
                            "minimum": 1,
                            "type": "string",
                            "description": "The looong host description",
                            "title": "Host"
                        },
                        "port": {
                            "description": "The port number",
                            "default": 80,
                            "inclusiveMinimum": false,
                            "maximum": 65535,
                            "minimum": 0,
                            "type": "number"
                        }
                    },
                    "required": [
                        "host"
                    ],
                    "x-ordering": [
                        "host",
                        "port"
                    ],
                    "additionalProperties": false
                },
                "logconfig": {
                    "id": "https://non-existing.saltstack.com/schemas/logconfig.json#",
                    "title": "Logging Configuration",
                    "description": "This is the logging configuration",
                    "type": "object",
                    "properties": {
                        "log_level": {
                            "default": "debug",
                            "minimum": 1,
                            "type": "string",
                            "description": "The logging level",
                            "title": "Logging Level"
                        }
                    },
                    "required": [
                        "log_level"
                    ],
                    "x-ordering": [
                        "log_level"
                    ],
                    "additionalProperties": false
                }
            },
            "additionalProperties": false
        }

        >>> import jsonschema
        >>> jsonschema.validate(
            {'hostconfig': {'host': 'localhost', 'port': 80},
             'logconfig': {'log_level': 'debug'}},
            MyConfig.serialize())
        >>> jsonschema.validate(
            {'hostconfig': {'host': 'localhost', 'port': -1},
             'logconfig': {'log_level': 'debug'}},
            MyConfig.serialize())
        Traceback (most recent call last):
        File "<stdin>", line 1, in <module>
        File "/usr/lib/python2.7/site-packages/jsonschema/validators.py", line 478, in validate
            cls(schema, *args, **kwargs).validate(instance)
        File "/usr/lib/python2.7/site-packages/jsonschema/validators.py", line 123, in validate
            raise error
        jsonschema.exceptions.ValidationError: -1 is less than the minimum of 0

        Failed validating 'minimum' in schema['properties']['hostconfig']['properties']['port']:
            {'default': 80,
            'description': 'The port number',
            'inclusiveMinimum': False,
            'maximum': 65535,
            'minimum': 0,
            'type': 'number'}

        On instance['hostconfig']['port']:
            -1
        >>>

    If however, you just want to use the configuration blocks for readability and do not desire the nested
    dictionaries serialization, you can pass ``flatten=True`` when defining a configuration section as a
    configuration subclass attribute:

    .. code-block:: python

        class MyConfig(Configuration):

            title = 'My Config'
            description = 'This my configuration'

            hostconfig = HostConfig(flatten=True)
            logconfig = LoggingConfig(flatten=True)


    The JSON Schema string version of the above is:

    .. code-block:: python

        >>> print(json.dumps(MyConfig, indent=4))
        {
            "$schema": "http://json-schema.org/draft-04/schema#",
            "title": "My Config",
            "description": "This my configuration",
            "type": "object",
            "properties": {
                "host": {
                    "minimum": 1,
                    "type": "string",
                    "description": "The looong host description",
                    "title": "Host"
                },
                "port": {
                    "description": "The port number",
                    "default": 80,
                    "inclusiveMinimum": false,
                    "maximum": 65535,
                    "minimum": 0,
                    "type": "number"
                },
                "log_level": {
                    "default": "debug",
                    "minimum": 1,
                    "type": "string",
                    "description": "The logging level",
                    "title": "Logging Level"
                }
            },
            "x-ordering": [
                "host",
                "port",
                "log_level"
            ],
            "additionalProperties": false
        }
'''

# Import python libs
from __future__ import absolute_import, print_function
import sys
import inspect
import textwrap
import functools

# Import salt libs
from salt.utils.odict import OrderedDict

# Import 3rd-party libs
import yaml
import salt.ext.six as six

BASE_SCHEMA_URL = 'https://non-existing.saltstack.com/schemas'
RENDER_COMMENT_YAML_MAX_LINE_LENGTH = 80


class Prepareable(type):
    '''
    Preserve attributes order for python 2.x
    '''
    # This code was taken from
    # https://github.com/aromanovich/jsl/blob/master/jsl/_compat/prepareable.py
    # which in turn was taken from https://gist.github.com/DasIch/5562625 with minor fixes
    if not six.PY3:
        def __new__(mcs, name, bases, attributes):
            try:
                constructor = attributes["__new__"]
            except KeyError:
                return type.__new__(mcs, name, bases, attributes)

            def preparing_constructor(mcs, name, bases, attributes):
                try:
                    mcs.__prepare__
                except AttributeError:
                    return constructor(mcs, name, bases, attributes)
                namespace = mcs.__prepare__(name, bases)
                defining_frame = sys._getframe(1)
                for constant in reversed(defining_frame.f_code.co_consts):
                    if inspect.iscode(constant) and constant.co_name == name:
                        def get_index(attribute_name, _names=constant.co_names):
                            try:
                                return _names.index(attribute_name)
                            except ValueError:
                                return 0
                        break
                else:
                    return constructor(mcs, name, bases, attributes)

                by_appearance = sorted(
                    attributes.items(), key=lambda item: get_index(item[0])
                )
                for key, value in by_appearance:
                    namespace[key] = value
                return constructor(mcs, name, bases, namespace)
            attributes["__new__"] = functools.wraps(constructor)(preparing_constructor)
            return type.__new__(mcs, name, bases, attributes)


class NullSentinel(object):
    '''
    A class which instance represents a null value.
    Allows specifying fields with a default value of null.
    '''

    def __bool__(self):
        return False

    __nonzero__ = __bool__


Null = NullSentinel()
'''
A special value that can be used to set the default value
of a field to null.
'''


# make sure nobody creates another Null value
def _failing_new(*args, **kwargs):
    raise TypeError('Can\'t create another NullSentinel instance')

NullSentinel.__new__ = staticmethod(_failing_new)
del _failing_new


class ConfigurationMeta(six.with_metaclass(Prepareable, type)):

    @classmethod
    def __prepare__(mcs, name, bases):
        return OrderedDict()

    def __new__(mcs, name, bases, attrs):
        # Mark the instance as a configuration document/section
        attrs['__config__'] = True
        attrs['__flatten__'] = False

        # Let's record the configuration items/sections
        items = OrderedDict()
        sections = OrderedDict()
        # items from parent classes
        for base in reversed(bases):
            if hasattr(base, '_items'):
                items.update(base._items)
            if hasattr(base, '_sections'):
                sections.update(base._sections)

        # Iterate through attrs to discover items/config sections
        for key, value in six.iteritems(attrs):
            if hasattr(value, '__item__'):
                # the value is an item instance
                if hasattr(value, 'title') and value.title is None:
                    # It's an item instance without a title, make the title
                    # it's name
                    value.title = key
                items[key] = value
            if hasattr(value, '__config__'):
                # the value is a configuration section
                sections[key] = value

        attrs['_items'] = items
        attrs['_sections'] = sections
        return type.__new__(mcs, name, bases, attrs)

    def __call__(cls, flatten=False, allow_additional_items=False, **kwargs):
        instance = object.__new__(cls)
        if flatten is True:
            # This configuration block is to be treated as a part of the
            # configuration for which it was defined as an attribute, not as
            # it's own sub configuration
            instance.__flatten__ = True
        if allow_additional_items is True:
            # The configuration block only accepts the configuration items
            # which are defined on the class. On additional items, validation
            # with jsonschema will fail
            instance.__allow_additional_items__ = True
        instance.__init__(**kwargs)
        return instance


class BaseConfigItemMeta(six.with_metaclass(Prepareable, type)):
    '''
    Config item metaclass to "tag" the class as a configuration item
    '''
    @classmethod
    def __prepare__(mcs, name, bases):
        return OrderedDict()

    def __new__(mcs, name, bases, attrs):
        # Register the class as an item class
        attrs['__item__'] = True
        # Instantiate an empty list to store the config item attribute names
        attrs['_attributes'] = []
        return type.__new__(mcs, name, bases, attrs)

    def __call__(cls, *args, **kwargs):
        # Create the instance class
        instance = object.__new__(cls)
        args = list(args)
        if args:
            # We were passed un-named keyword arguments. Let's map them to
            # keyword arguments since no configuration item shall support
            # unnamed arguments
            argspec = inspect.getargspec(instance.__init__)
            for idx, argvalue in enumerate(args[:]):
                args.remove(argvalue)
                kwargs[argspec.args[idx+1]] = argvalue
        for key in kwargs.keys():
            # Store the kwarg keys as the instance attributes for the
            # serialization step
            if key not in instance._attributes:
                instance._attributes.append(key)
        # Init the class
        instance.__init__(*args, **kwargs)
        # Return the initialized class
        return instance


class Configuration(six.with_metaclass(ConfigurationMeta, object)):
    '''
    Configuration definition class
    '''

    # Define some class level attributes to make PyLint happier
    title = None
    description = None
    _items = _sections = None
    __flatten__ = False
    __allow_additional_items__ = False

    @classmethod
    def serialize(cls, id_=None):
        # The order matters
        serialized = OrderedDict()
        if id_ is not None:
            # This is meant as a configuration section, sub json schema
            serialized['id'] = '{0}/{1}.json#'.format(BASE_SCHEMA_URL, id_)
        else:
            # Main configuration block, json schema
            serialized['$schema'] = 'http://json-schema.org/draft-04/schema#'
        if cls.title is not None:
            serialized['title'] = cls.title
        if cls.description is not None:
            serialized['description'] = cls.description

        required = []
        ordering = []
        serialized['type'] = 'object'
        properties = OrderedDict()
        for name, section in cls._sections.items():
            serialized_section = section.serialize(None if section.__flatten__ is True else name)
            if section.__flatten__ is True:
                # Flatten the configuration section into the parent
                # configuration
                properties.update(serialized_section['properties'])
                if 'x-ordering' in serialized_section:
                    ordering.extend(serialized_section['x-ordering'])
                if 'required' in serialized:
                    required.extend(serialized_section['required'])
            else:
                # Store it as a configuration section
                properties[name] = serialized_section

        # Handle the configuration items defined in the class instance
        for name, config in cls._items.items():
            properties[name] = config.serialize()
            # Store the order of the item
            ordering.append(name)
            if config.required:
                # If it's a required item, add it to the required list
                required.append(name)
        serialized['properties'] = properties
        if required:
            # Only include required if not empty
            serialized['required'] = required
        if ordering:
            # Only include ordering if not empty
            serialized['x-ordering'] = ordering
        serialized['additionalProperties'] = cls.__allow_additional_items__
        return serialized

    @classmethod
    def render_as_rst(cls):
        '''
        Render the configuration block as a restructured text string
        '''
        # TODO: Implement RST rendering
        raise NotImplementedError

    @classmethod
    def render_as_yaml(cls):
        '''
        Render the configuration block as a parseable YAML string including comments
        '''
        # TODO: Implement YAML rendering
        raise NotImplementedError


class BaseConfigItem(six.with_metaclass(BaseConfigItemMeta, object)):
    '''
    Base configuration items class.

    All configurations must subclass it
    '''

    # Define some class level attributes to make PyLint happier
    __type__ = None
    __format__ = None
    _attributes = None

    __serialize_attr_aliases__ = None

    def __init__(self, title=None, description=None, default=None, required=False, enum=None, **extra):
        '''
        :param title:
            A short explanation about the purpose of the data described by this item.
        :param description:
            A detailed explanation about the purpose of the data described by this item.
        :param default:
            The default value for this configuration item. May be :data:`.Null` (a special value
            to set the default value to null).
        :param required: If the configuration item is required. Defaults to ``False``.
        :param enum: A list(list, tuple, set) of valid choices.
        '''
        self.title = title
        self.description = description or self.__doc__
        self.default = default
        self.required = required
        if enum is not None:
            if not isinstance(enum, (list, tuple, set)):
                raise RuntimeError(
                    'Only the \'list\', \'tuple\' and \'set\' python types can be used '
                    'to define \'enum\''
                )
            enum = list(enum)
        self.enum = enum
        self.extra = extra

    def _get_argname_value(self, argname):
        '''
        Return the argname value looking up on all possible attributes
        '''
        # Let's see if the value is defined as a public class variable
        argvalue = getattr(self, argname, None)
        if argvalue is None:
            # Let's see if it's defined as a private class variable
            argvalue = getattr(self, '__{0}__'.format(argname), None)
        if argvalue is None:
            # Let's look for it in the extra dictionary
            argvalue = self.extra.get(argname, None)
        return argvalue

    def serialize(self):
        '''
        Return a serializable form of the config instance
        '''
        serialized = {'type': self.__type__}
        for argname in self._attributes:
            if argname == 'required':
                # This is handled elsewhere
                continue
            argvalue = self._get_argname_value(argname)
            if argvalue is not None:
                # None values are not meant to be included in the
                # serialization, since this is not None...
                if self.__serialize_attr_aliases__ and argname in self.__serialize_attr_aliases__:
                    argname = self.__serialize_attr_aliases__[argname]
                serialized[argname] = argvalue
        return serialized

    def render_as_rst(self, name):
        '''
        Render the configuration item as a restructured text string
        '''
        # TODO: Implement YAML rendering
        raise NotImplementedError

    def render_as_yaml(self, name):
        '''
        Render the configuration item as a parseable YAML string including comments
        '''
        # TODO: Include the item rules in the output, minimum, maximum, etc...
        output = '# ----- '
        output += self.title
        output += ' '
        output += '-' * (RENDER_COMMENT_YAML_MAX_LINE_LENGTH - 7 - len(self.title) - 2)
        output += '>\n'
        if self.description:
            output += '\n'.join(textwrap.wrap(self.description,
                                              width=RENDER_COMMENT_YAML_MAX_LINE_LENGTH,
                                              initial_indent='# '))
            output += '\n'
            yamled_default_value = yaml.dump(self.default, default_flow_style=False).split('\n...', 1)[0]
            output += '# Default: {0}\n'.format(yamled_default_value)
            output += '#{0}: {1}\n'.format(name, yamled_default_value)
        output += '# <---- '
        output += self.title
        output += ' '
        output += '-' * (RENDER_COMMENT_YAML_MAX_LINE_LENGTH - 7 - len(self.title) - 1)
        return output + '\n'


class BooleanConfig(BaseConfigItem):
    __type__ = 'boolean'


class StringConfig(BaseConfigItem):
    '''
    A string configuration field
    '''

    __type__ = 'string'

    __serialize_attr_aliases__ = {
        'min_length': 'minLength',
        'max_length': 'maxLength'
    }

    def __init__(self, format=None, pattern=None, min_length=None, max_length=None, **kwargs):
        '''
        :param title:
            A short explanation about the purpose of the data described by this item.
        :param description:
            A detailed explanation about the purpose of the data described by this item.
        :param default:
            The default value for this configuration item. May be :data:`.Null` (a special value
            to set the default value to null).
        :param required:
            If the configuration item is required. Defaults to ``False``.
        :param enum:
            A list(list, tuple, set) of valid choices.
        :param format:
            A semantic format of the string (for example, ``"date-time"``, ``"email"``, or ``"uri"``).
        :param pattern:
            A regular expression (ECMA 262) that a string value must match.
        :param min_length:
            The minimum length
        :param max_length:
            The maximum length
        '''
        self.format = format or self.__format__
        self.pattern = pattern
        self.min_length = min_length
        self.max_length = max_length
        super(StringConfig, self).__init__(**kwargs)


class EMailConfig(StringConfig):
    '''
    An internet email address, see `RFC 5322, section 3.4.1`__.

    .. __: http://tools.ietf.org/html/rfc5322
    '''
    __format__ = 'email'


class IPv4Config(StringConfig):
    '''
    An IPv4 address configuration field, according to dotted-quad ABNF syntax as defined in
    `RFC 2673, section 3.2`__.

    .. __: http://tools.ietf.org/html/rfc2673
    '''
    __format__ = 'ipv4'


class IPv6Config(StringConfig):
    '''
    An IPv6 address configuration field, as defined in `RFC 2373, section 2.2`__.

    .. __: http://tools.ietf.org/html/rfc2373
    '''
    __format__ = 'ipv6'


class HostnameConfig(StringConfig):
    '''
    An Internet host name configuration field, see `RFC 1034, section 3.1`__.

    .. __: http://tools.ietf.org/html/rfc1034
    '''
    __format__ = 'hostname'


class DateTimeConfig(StringConfig):
    '''
    An ISO 8601 formatted date-time configuration field, as defined by `RFC 3339, section 5.6`__.

    .. __: http://tools.ietf.org/html/rfc3339
    '''
    __format__ = 'date-time'


class UriConfig(StringConfig):
    '''
    A universal resource identifier (URI) configuration field, according to `RFC3986`__.

    .. __: http://tools.ietf.org/html/rfc3986
    '''
    __format__ = 'uri'


class SecretConfig(StringConfig):
    '''
    A string configuration field containing a secret, for example, passwords, API keys, etc
    '''
    __format__ = 'secret'


class NumberConfig(BaseConfigItem):

    __type__ = 'number'

    __serialize_attr_aliases__ = {
        'multiple_of': 'multipleOf',
        'exclusive_minimum': 'exclusiveMinimum',
        'exclusive_maximum': 'exclusiveMaximum',
    }

    def __init__(self,
                 multiple_of=None,
                 minimum=None,
                 exclusive_minimum=None,
                 maximum=None,
                 exclusive_maximum=None,
                 **kwargs):
        '''
        :param title:
            A short explanation about the purpose of the data described by this item.
        :param description:
            A detailed explanation about the purpose of the data described by this item.
        :param default:
            The default value for this configuration item. May be :data:`.Null` (a special value
            to set the default value to null).
        :param required:
            If the configuration item is required. Defaults to ``False``.
        :param enum:
            A list(list, tuple, set) of valid choices.
        :param multiple_of:
            A value must be a multiple of this factor.
        :param minimum:
            The minimum allowed value
        :param exclusive_minimum:
            Wether a value is allowed to be exactly equal to the minimum
        :param maximum:
            The maximum allowed value
        :param exclusive_maximum:
            Wether a value is allowed to be exactly equal to the maximum
        '''
        self.multiple_of = multiple_of
        self.minimum = minimum
        self.exclusive_minimum = exclusive_minimum,
        self.maximum = maximum
        self.exclusive_maximum = exclusive_maximum
        super(NumberConfig, self).__init__(**kwargs)


class IntConfig(NumberConfig):
    __type__ = 'integer'
