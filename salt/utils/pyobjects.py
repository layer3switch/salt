# -*- coding: utf-8 -*-
'''
:maintainer: Evan Borgstrom <evan@borgstrom.ca>

Pythonic object interface to creating state data, see the pyobjects renderer
for more documentation.
'''
from salt.utils.odict import OrderedDict

REQUISITES = ('require', 'watch', 'use', 'require_in', 'watch_in', 'use_in')


class StateException(Exception):
    pass


class DuplicateState(StateException):
    pass


class InvalidFunction(StateException):
    pass


class StateRegistry(object):
    """
    The StateRegistry holds all of the states that have been created.
    """
    def __init__(self):
        self.empty()

    def empty(self):
        self.states = OrderedDict()
        self.requisites = []

    def salt_data(self):
        states = OrderedDict([
            (id_, state())
            for id_, state in self.states.iteritems()
        ])

        self.empty()

        return states

    def add(self, id_, state):
        if id_ in self.states:
            raise DuplicateState("A state with id '%s' already exists" % id_)

        # if we have requisites in our stack then add them to the state
        if len(self.requisites) > 0:
            for req in self.requisites:
                if req.requisite not in state.kwargs:
                    state.kwargs[req.requisite] = []
                state.kwargs[req.requisite].append(req())

        self.states[id_] = state

    def push_requisite(self, requisite):
        self.requisites.append(requisite)

    def pop_requisite(self):
        del self.requisites[-1]


class StateRequisite(object):
    def __init__(self, requisite, module, id_, registry):
        self.requisite = requisite
        self.module = module
        self.id_ = id_
        self.registry = registry

    def __call__(self):
        return {self.module: self.id_}

    def __enter__(self):
        self.registry.push_requisite(self)

    def __exit__(self, type, value, traceback):
        self.registry.pop_requisite()


class StateFactory(object):
    """
    The StateFactory is used to generate new States through a natural syntax

    It is used by initializing it with the name of the salt module::

        File = StateFactory("file")

    Any attribute accessed on the instance returned by StateFactory is a lambda
    that is a short cut for generating State objects::

        File.managed('/path/', owner='root', group='root')

    The kwargs are passed through to the State object
    """
    def __init__(self, module, registry, valid_funcs=[]):
        self.module = module
        self.valid_funcs = valid_funcs
        self.registry = registry

    def __getattr__(self, func):
        if len(self.valid_funcs) > 0 and func not in self.valid_funcs:
            raise InvalidFunction("The function '%s' does not exist in the "
                                  "StateFactory for '%s'" % (func, self.module))

        def make_state(id_, **kwargs):
            return State(
                id_,
                self.module,
                func,
                registry=self.registry,
                **kwargs
            )
        return make_state

    def __call__(self, id_, requisite='require'):
        """
        When an object is called it is being used as a requisite
        """
        # return the correct data structure for the requisite
        return StateRequisite(requisite, self.module, id_,
                              registry=self.registry)


class State(object):
    """
    This represents a single item in the state tree

    The id_ is the id of the state, the func is the full name of the salt
    state (ie. file.managed). All the keyword args you pass in become the
    properties of your state.

    The registry is where the state should be stored. It is optional and will
    use the default registry if not specified.
    """

    def __init__(self, id_, module, func, registry, **kwargs):
        self.id_ = id_
        self.module = module
        self.func = func
        self.kwargs = kwargs
        self.registry = registry

        self.requisite = StateRequisite('require', self.module, self.id_,
                                        registry=self.registry)

        self.registry.add(self.id_, self)

    @property
    def attrs(self):
        kwargs = self.kwargs

        # handle our requisites
        for attr in REQUISITES:
            if attr in kwargs:
                # our requisites should all be lists, but when you only have a
                # single item it's more convenient to provide it without
                # wrapping it in a list. transform them into a list
                if not isinstance(kwargs[attr], list):
                    kwargs[attr] = [kwargs[attr]]

                # rebuild the requisite list transforming any of the actual
                # StateRequisite objects into their representative dict
                kwargs[attr] = [
                    req() if isinstance(req, StateRequisite) else req
                    for req in kwargs[attr]
                ]

        # build our attrs from kwargs. we sort the kwargs by key so that we
        # have consistent ordering for tests
        return [
            {k: kwargs[k]}
            for k in sorted(kwargs.iterkeys())
        ]

    @property
    def full_func(self):
        return "%s.%s" % (self.module, self.func)

    def __str__(self):
        return "%s = %s:%s" % (self.id_, self.full_func, self.attrs)

    def __call__(self):
        return {
            self.full_func: self.attrs
        }

    def __enter__(self):
        self.registry.push_requisite(self.requisite)

    def __exit__(self, type, value, traceback):
        self.registry.pop_requisite()
