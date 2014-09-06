# -*- coding: utf-8 -*-
'''
Set up the version of Salt
'''

# Import python libs
from __future__ import print_function
import re
import sys

# Import salt libs
try:
    from salt._compat import string_types
except ImportError:
    if sys.version_info[0] == 3:
        string_types = str
    else:
        string_types = basestring

# ----- ATTENTION --------------------------------------------------------------------------------------------------->
#
# ALL major version bumps, new release codenames, MUST be defined in the SaltStackVersion.NAMES dictionary, ie:
#
#    class SaltStackVersion(object):
#
#        NAMES = {
#            'Hydrogen': (2014, 1),   # <- This is the tuple to bump versions
#            ( ... )
#        }
#
#
# ONLY UPDATE CODENAMES AFTER BRANCHING
#
# As an example, The Helium codename must only be properly defined with "(2014, 7)" after Hydrogen, "(2014, 1)", has
# been branched out into it's own branch.
#
# ALL OTHER VERSION INFORMATION IS EXTRACTED FROM THE GIT TAGS
#
# <---- ATTENTION ----------------------------------------------------------------------------------------------------


class SaltStackVersion(object):
    '''
    Handle SaltStack versions class.

    Knows how to parse ``git describe`` output, knows about release candidates
    and also supports version comparison.
    '''

    __slots__ = ('name', 'major', 'minor', 'bugfix', 'mbugfix', 'rc', 'noc', 'sha')

    git_describe_regex = re.compile(
        r'(?:[^\d]+)?(?P<major>[\d]{1,4})'
        r'\.(?P<minor>[\d]{1,2})'
        r'(?:\.(?P<bugfix>[\d]{0,2}))?'
        r'(?:\.(?P<mbugfix>[\d]{0,2}))?'
        r'(?:rc(?P<rc>[\d]{1}))?'
        r'(?:(?:.*)-(?P<noc>(?:[\d]+|n/a))-(?P<sha>[a-z0-9]{8}))?'
    )
    git_sha_regex = re.compile(r'(?P<sha>[a-z0-9]{7})')

    # Salt versions after 0.17.0 will be numbered like:
    #   <4-digit-year>.<month>.<bugfix>
    #
    # Since the actual version numbers will only be know on release dates, the
    # periodic table element names will be what's going to be used to name
    # versions and to be able to mention them.

    NAMES = {
        # Let's keep at least 3 version names uncommented counting from the
        # latest release so we can map deprecation warnings to versions.


        # pylint: disable=E8203,E8265
        # ----- Please refrain from fixing PEP-8 E203 and E265------------------------------------------------------->
        # The idea is keep this readable
        # ------------------------------------------------------------------------------------------------------------
        'Hydrogen'      : (2014, 1),
        'Helium'        : (2014, 7),
        'Lithium'       : (sys.maxint - 106, 0),
        'Beryllium'     : (sys.maxint - 105, 0),
        'Boron'         : (sys.maxint - 104, 0),
        #'Carbon'       : (sys.maxint - 103, 0),
        #'Nitrogen'     : (sys.maxint - 102, 0),
        #'Oxygen'       : (sys.maxint - 101, 0),
        #'Fluorine'     : (sys.maxint - 100, 0),
        #'Neon'         : (sys.maxint - 99 , 0),
        #'Sodium'       : (sys.maxint - 98 , 0),
        #'Magnesium'    : (sys.maxint - 97 , 0),
        #'Aluminium'    : (sys.maxint - 96 , 0),
        #'Silicon'      : (sys.maxint - 95 , 0),
        #'Phosphorus'   : (sys.maxint - 94 , 0),
        #'Sulfur'       : (sys.maxint - 93 , 0),
        #'Chlorine'     : (sys.maxint - 92 , 0),
        #'Argon'        : (sys.maxint - 91 , 0),
        #'Potassium'    : (sys.maxint - 90 , 0),
        #'Calcium'      : (sys.maxint - 89 , 0),
        #'Scandium'     : (sys.maxint - 88 , 0),
        #'Titanium'     : (sys.maxint - 87 , 0),
        #'Vanadium'     : (sys.maxint - 86 , 0),
        #'Chromium'     : (sys.maxint - 85 , 0),
        #'Manganese'    : (sys.maxint - 84 , 0),
        #'Iron'         : (sys.maxint - 83 , 0),
        #'Cobalt'       : (sys.maxint - 82 , 0),
        #'Nickel'       : (sys.maxint - 81 , 0),
        #'Copper'       : (sys.maxint - 80 , 0),
        #'Zinc'         : (sys.maxint - 79 , 0),
        #'Gallium'      : (sys.maxint - 78 , 0),
        #'Germanium'    : (sys.maxint - 77 , 0),
        #'Arsenic'      : (sys.maxint - 76 , 0),
        #'Selenium'     : (sys.maxint - 75 , 0),
        #'Bromine'      : (sys.maxint - 74 , 0),
        #'Krypton'      : (sys.maxint - 73 , 0),
        #'Rubidium'     : (sys.maxint - 72 , 0),
        #'Strontium'    : (sys.maxint - 71 , 0),
        #'Yttrium'      : (sys.maxint - 70 , 0),
        #'Zirconium'    : (sys.maxint - 69 , 0),
        #'Niobium'      : (sys.maxint - 68 , 0),
        #'Molybdenum'   : (sys.maxint - 67 , 0),
        #'Technetium'   : (sys.maxint - 66 , 0),
        #'Ruthenium'    : (sys.maxint - 65 , 0),
        #'Rhodium'      : (sys.maxint - 64 , 0),
        #'Palladium'    : (sys.maxint - 63 , 0),
        #'Silver'       : (sys.maxint - 62 , 0),
        #'Cadmium'      : (sys.maxint - 61 , 0),
        #'Indium'       : (sys.maxint - 60 , 0),
        #'Tin'          : (sys.maxint - 59 , 0),
        #'Antimony'     : (sys.maxint - 58 , 0),
        #'Tellurium'    : (sys.maxint - 57 , 0),
        #'Iodine'       : (sys.maxint - 56 , 0),
        #'Xenon'        : (sys.maxint - 55 , 0),
        #'Caesium'      : (sys.maxint - 54 , 0),
        #'Barium'       : (sys.maxint - 53 , 0),
        #'Lanthanum'    : (sys.maxint - 52 , 0),
        #'Cerium'       : (sys.maxint - 51 , 0),
        #'Praseodymium' : (sys.maxint - 50 , 0),
        #'Neodymium'    : (sys.maxint - 49 , 0),
        #'Promethium'   : (sys.maxint - 48 , 0),
        #'Samarium'     : (sys.maxint - 47 , 0),
        #'Europium'     : (sys.maxint - 46 , 0),
        #'Gadolinium'   : (sys.maxint - 45 , 0),
        #'Terbium'      : (sys.maxint - 44 , 0),
        #'Dysprosium'   : (sys.maxint - 43 , 0),
        #'Holmium'      : (sys.maxint - 42 , 0),
        #'Erbium'       : (sys.maxint - 41 , 0),
        #'Thulium'      : (sys.maxint - 40 , 0),
        #'Ytterbium'    : (sys.maxint - 39 , 0),
        #'Lutetium'     : (sys.maxint - 38 , 0),
        #'Hafnium'      : (sys.maxint - 37 , 0),
        #'Tantalum'     : (sys.maxint - 36 , 0),
        #'Tungsten'     : (sys.maxint - 35 , 0),
        #'Rhenium'      : (sys.maxint - 34 , 0),
        #'Osmium'       : (sys.maxint - 33 , 0),
        #'Iridium'      : (sys.maxint - 32 , 0),
        #'Platinum'     : (sys.maxint - 31 , 0),
        #'Gold'         : (sys.maxint - 30 , 0),
        #'Mercury'      : (sys.maxint - 29 , 0),
        #'Thallium'     : (sys.maxint - 28 , 0),
        #'Lead'         : (sys.maxint - 27 , 0),
        #'Bismuth'      : (sys.maxint - 26 , 0),
        #'Polonium'     : (sys.maxint - 25 , 0),
        #'Astatine'     : (sys.maxint - 24 , 0),
        #'Radon'        : (sys.maxint - 23 , 0),
        #'Francium'     : (sys.maxint - 22 , 0),
        #'Radium'       : (sys.maxint - 21 , 0),
        #'Actinium'     : (sys.maxint - 20 , 0),
        #'Thorium'      : (sys.maxint - 19 , 0),
        #'Protactinium' : (sys.maxint - 18 , 0),
        #'Uranium'      : (sys.maxint - 17 , 0),
        #'Neptunium'    : (sys.maxint - 16 , 0),
        #'Plutonium'    : (sys.maxint - 15 , 0),
        #'Americium'    : (sys.maxint - 14 , 0),
        #'Curium'       : (sys.maxint - 13 , 0),
        #'Berkelium'    : (sys.maxint - 12 , 0),
        #'Californium'  : (sys.maxint - 11 , 0),
        #'Einsteinium'  : (sys.maxint - 10 , 0),
        #'Fermium'      : (sys.maxint - 9  , 0),
        #'Mendelevium'  : (sys.maxint - 8  , 0),
        #'Nobelium'     : (sys.maxint - 7  , 0),
        #'Lawrencium'   : (sys.maxint - 6  , 0),
        #'Rutherfordium': (sys.maxint - 5  , 0),
        #'Dubnium'      : (sys.maxint - 4  , 0),
        #'Seaborgium'   : (sys.maxint - 3  , 0),
        #'Bohrium'      : (sys.maxint - 2  , 0),
        #'Hassium'      : (sys.maxint - 1  , 0),
        #'Meitnerium'   : (sys.maxint - 0  , 0),
        # <---- Please refrain from fixing PEP-8 E203 and E265 -------------------------------------------------------
        # pylint: enable=E8203,E8265
    }

    LNAMES = dict((k.lower(), v) for (k, v) in NAMES.iteritems())
    VNAMES = dict((v, k) for (k, v) in NAMES.iteritems())
    RMATCH = dict((v[:2], k) for (k, v) in NAMES.iteritems())

    def __init__(self,              # pylint: disable=C0103
                 major,
                 minor,
                 bugfix=0,
                 mbugfix=0,
                 rc=0,              # pylint: disable=C0103
                 noc=0,
                 sha=None):

        if isinstance(major, string_types):
            major = int(major)

        if isinstance(minor, string_types):
            minor = int(minor)

        if bugfix is None:
            bugfix = 0
        elif isinstance(bugfix, string_types):
            bugfix = int(bugfix)

        if mbugfix is None:
            mbugfix = 0
        elif isinstance(mbugfix, string_types):
            mbugfix = int(mbugfix)

        if rc is None:
            rc = 0
        elif isinstance(rc, string_types):
            rc = int(rc)

        if noc is None:
            noc = 0
        elif isinstance(noc, string_types) and noc == 'n/a':
            noc = -1
        elif isinstance(noc, string_types):
            noc = int(noc)

        self.major = major
        self.minor = minor
        self.bugfix = bugfix
        self.mbugfix = mbugfix
        self.rc = rc  # pylint: disable=C0103
        self.name = self.VNAMES.get((major, minor), None)
        self.noc = noc
        self.sha = sha

    @classmethod
    def parse(cls, version_string):
        if version_string.lower() in cls.LNAMES:
            return cls.from_name(version_string)
        match = cls.git_describe_regex.match(version_string)
        if not match:
            raise ValueError(
                'Unable to parse version string: {0!r}'.format(version_string)
            )
        return cls(*match.groups())

    @classmethod
    def from_name(cls, name):
        if name.lower() not in cls.LNAMES:
            raise ValueError(
                'Named version {0!r} is not known'.format(name)
            )
        return cls(*cls.LNAMES[name.lower()])

    @classmethod
    def from_last_named_version(cls):
        return cls.from_name(
            cls.VNAMES[
                max([version_info for version_info in
                     cls.VNAMES.keys() if
                     version_info[0] < (sys.maxint - 200)])
            ]
        )

    @property
    def sse(self):
        # Higher than 0.17, lower than first date based
        return 0 < self.major < 2014

    @property
    def info(self):
        return (
            self.major,
            self.minor,
            self.bugfix,
            self.mbugfix
        )

    @property
    def rc_info(self):
        return (
            self.major,
            self.minor,
            self.bugfix,
            self.mbugfix,
            self.rc
        )

    @property
    def noc_info(self):
        return (
            self.major,
            self.minor,
            self.bugfix,
            self.mbugfix,
            self.rc,
            self.noc
        )

    @property
    def full_info(self):
        return (
            self.major,
            self.minor,
            self.bugfix,
            self.mbugfix,
            self.rc,
            self.noc,
            self.sha
        )

    @property
    def string(self):
        version_string = '{0}.{1}.{2}'.format(
            self.major,
            self.minor,
            self.bugfix
        )
        if self.mbugfix:
            version_string += '.{0}'.format(self.mbugfix)
        if self.rc:
            version_string += 'rc{0}'.format(self.rc)
        if self.noc and self.sha:
            noc = self.noc
            if noc < 0:
                noc = 'n/a'
            version_string += '-{0}-{1}'.format(noc, self.sha)
        return version_string

    @property
    def formatted_version(self):
        if self.name and self.major > 10000:
            version_string = self.name
            if self.sse:
                version_string += ' Enterprise'
            version_string += ' (Unreleased)'
            return version_string
        version_string = self.string
        if self.sse:
            version_string += ' Enterprise'
        if (self.major, self.minor) in self.RMATCH:
            version_string += ' ({0})'.format(self.RMATCH[(self.major, self.minor)])
        return version_string

    def __str__(self):
        return self.string

    def __cmp__(self, other):
        if not isinstance(other, SaltStackVersion):
            if isinstance(other, string_types):
                other = SaltStackVersion.parse(other)
            elif isinstance(other, (list, tuple)):
                other = SaltStackVersion(*other)
            else:
                raise ValueError(
                    'Cannot instantiate Version from type {0!r}'.format(
                        type(other)
                    )
                )

        if (self.rc and other.rc) or (not self.rc and not other.rc):
            # Both have rc information, regular compare is ok
            return cmp(self.noc_info, other.noc_info)

        # RC's are always lower versions than non RC's
        if self.rc > 0 and other.rc <= 0:
            noc_info = list(self.noc_info)
            noc_info[3] = -1
            return cmp(tuple(noc_info), other.noc_info)

        if self.rc <= 0 and other.rc > 0:
            other_noc_info = list(other.noc_info)
            other_noc_info[3] = -1
            return cmp(self.noc_info, tuple(other_noc_info))

    def __repr__(self):
        parts = []
        if self.name:
            parts.append('name={0!r}'.format(self.name))
        parts.extend([
            'major={0}'.format(self.major),
            'minor={0}'.format(self.minor),
            'bugfix={0}'.format(self.bugfix)
        ])
        if self.mbugfix:
            parts.append('minor-bugfix={0}'.format(self.mbugfix))
        if self.rc:
            parts.append('rc={0}'.format(self.rc))
        noc = self.noc
        if noc == -1:
            noc = 'n/a'
        if noc and self.sha:
            parts.extend([
                'noc={0}'.format(noc),
                'sha={0}'.format(self.sha)
            ])
        return '<{0} {1}>'.format(self.__class__.__name__, ' '.join(parts))


# ----- Hardcoded Salt Codename Version Information ----------------------------------------------------------------->
#
#   There's no need to do anything here. The last released codename will be picked up
# --------------------------------------------------------------------------------------------------------------------
__saltstack_version__ = SaltStackVersion.from_last_named_version()
# <---- Hardcoded Salt Version Information ---------------------------------------------------------------------------


# ----- Dynamic/Runtime Salt Version Information -------------------------------------------------------------------->
def __get_version(saltstack_version):
    '''
    If we can get a version provided at installation time or from Git, use
    that instead, otherwise we carry on.
    '''
    try:
        # Try to import the version information provided at install time
        from salt._version import __saltstack_version__  # pylint: disable=E0611,F0401
        return __saltstack_version__
    except ImportError:
        pass

    # This might be a 'python setup.py develop' installation type. Let's
    # discover the version information at runtime.
    import os
    import subprocess

    if 'SETUP_DIRNAME' in globals():
        # This is from the exec() call in Salt's setup.py
        cwd = SETUP_DIRNAME  # pylint: disable=E0602
        if not os.path.exists(os.path.join(cwd, '.git')):
            # This is not a Salt git checkout!!! Don't even try to parse...
            return saltstack_version
    else:
        cwd = os.path.abspath(os.path.dirname(__file__))
        if not os.path.exists(os.path.join(os.path.dirname(cwd), '.git')):
            # This is not a Salt git checkout!!! Don't even try to parse...
            return saltstack_version

    try:
        kwargs = dict(
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=cwd,
            shell=True
        )

        if not sys.platform.startswith('win'):
            # Let's not import `salt.utils` for the above check
            kwargs['close_fds'] = True

        process = subprocess.Popen(
            'git describe --tags --first-parent --match \'v[0-9]*\' --always 2>{0} || '
            'git describe --tags --match \'v[0-9]*\' --always'.format(os.devnull),
            **kwargs
        )
        out, err = process.communicate()
        out = out.strip()
        err = err.strip()

        if not out or err:
            return saltstack_version

        try:
            return SaltStackVersion.parse(out)
        except ValueError:
            if not SaltStackVersion.git_sha_regex.match(out):
                raise

            # We only define the parsed SHA and set NOC as ??? (unknown)
            saltstack_version.sha = out.strip()
            saltstack_version.noc = -1

    except OSError as os_err:
        if os_err.errno != 2:
            # If the errno is not 2(The system cannot find the file
            # specified), raise the exception so it can be catch by the
            # developers
            raise
    return saltstack_version


# Get additional version information if available
__saltstack_version__ = __get_version(__saltstack_version__)
# This function has executed once, we're done with it. Delete it!
del __get_version
# <---- Dynamic/Runtime Salt Version Information ---------------------------------------------------------------------


# ----- Common version related attributes - NO NEED TO CHANGE ------------------------------------------------------->
__version_info__ = __saltstack_version__.info
__version__ = __saltstack_version__.string
# <---- Common version related attributes - NO NEED TO CHANGE --------------------------------------------------------


def versions_information(include_salt_cloud=False):
    '''
    Report on all of the versions for dependent software
    '''

    libs = [
        ('Salt', None, __version__),
        ('Python', None, sys.version.rsplit('\n')[0].strip()),
        ('Jinja2', 'jinja2', '__version__'),
        ('M2Crypto', 'M2Crypto', 'version'),
        ('msgpack-python', 'msgpack', 'version'),
        ('msgpack-pure', 'msgpack_pure', 'version'),
        ('pycrypto', 'Crypto', '__version__'),
        ('libnacl', 'libnacl', '__version__'),
        ('PyYAML', 'yaml', '__version__'),
        ('ioflo', 'ioflo', '__version__'),
        ('PyZMQ', 'zmq', '__version__'),
        ('RAET', 'raet', '__version__'),
        ('ZMQ', 'zmq', 'zmq_version'),
        ('Mako', 'mako', '__version__'),
    ]

    if include_salt_cloud:
        libs.append(
            ('Apache Libcloud', 'libcloud', '__version__'),
        )

    for name, imp, attr in libs:
        if imp is None:
            yield name, attr
            continue
        try:
            imp = __import__(imp)
            version = getattr(imp, attr)
            if callable(version):
                version = version()
            if isinstance(version, (tuple, list)):
                version = '.'.join(map(str, version))
            yield name, version
        except ImportError:
            yield name, None


def versions_report(include_salt_cloud=False):
    '''
    Yield each library properly formatted for a console clean output.
    '''
    libs = list(versions_information(include_salt_cloud=include_salt_cloud))

    padding = max(len(lib[0]) for lib in libs) + 1

    fmt = '{0:>{pad}}: {1}'

    for name, version in libs:
        yield fmt.format(name, version or 'Not Installed', pad=padding)


if __name__ == '__main__':
    print(__version__)
