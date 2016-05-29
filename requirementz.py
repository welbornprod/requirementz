#!/usr/bin/env python3
# -*- coding: utf-8 -*-

""" requirementz.py
    Check requirements.txt against installed packages using pip and
    requirements-parser.
    Bonus features:
    Check for duplicate entries, search for entries using regex,
    add requirement lines,
    and list requirements or all installed packages (both formatted
    for readability).

    Originally designed for Python3, but backporting was fairly easy
    (it cost some readability though).
    This should run on at least Python 2.7.
    Color support is Python 3 only.
    -Christopher Welborn 07-19-2015
"""

# TODO: Figure out what to do with cvs or local requirements. -Cj

from __future__ import print_function
import inspect
import os
import pip
import re
import shutil
import sys
from pkg_resources import parse_version

import requirements
from docopt import docopt
from requirements.requirement import Requirement

try:
    from collections import UserList
except ImportError:
    # Python 2.7 UserList.
    from UserList import UserList
try:
    from contextlib import suppress
except ImportError:
    # Python 2.7 suppress.
    from contextlib import contextmanager

    @contextmanager
    def suppress(*ex_class):
        try:
            yield
        except ex_class:
            pass

# Use Colr if installed, otherwise use a 'fake Colr'.
try:
    from colr import (auto_disable as colr_auto_disable, Colr as C)
    colr_auto_disable()
except ImportError:
    # Colr will probably never support Python 2, but Requirementz should.
    class C(object):
        """ Fake Colr instance for Python 2 (doesn't do anything) """
        def __init__(self, *args, **kwargs):
            self.text = args[0] if args else kwargs.get('text', '')

        def __str__(self):
            return self.text

        def join(self, *args):
            """ Colr.join accepts iterable or individual args, and flattens
                at least once (cuts down on parentheses). Mimicking that here.
            """
            pcs = []
            for a in args:
                if isinstance(a, (list, tuple)):
                    pcs.extend(a)
                else:
                    pcs.append(a)
            return self.__class__(str(self).join(str(s) for s in pcs))

        def ljust(self, width, char=' '):
            return self.__class__(str(self).ljust(width, char))

NAME = 'Requirementz'
VERSION = '0.1.0'
VERSIONSTR = '{} v. {}'.format(NAME, VERSION)
SCRIPT = os.path.split(os.path.abspath(sys.argv[0]))[1]

USAGESTR = """{versionstr}
    Usage:
        {script} (-h | -p | -v) [-D]
        {script} [-c] [-e] [-r] [FILE] [-D]
        {script} [-d | -l | -a line... | (-s pat [-i])] [FILE] [-D]
        {script} -S [FILE] [-D]

    Options:
        FILE                 : Requirements file to parse.
                               Default: requirements.txt
        -a line,--add line   : Add a requirement line to the file.
                               The -a flag can be used multiple times.
        -c,--check           : Check installed packages against requirements.
        -D,--debug           : Print some debug info while running.
        -d,--duplicates      : List any duplicate entries.
        -e,--errors          : Only show errored packages with -c.
        -h,--help            : Show this help message.
        -i,--ignorecase      : Case insensitive when searching.
        -l,--list            : List all requirements.
        -p,--packages        : List all installed packages.
        -r,--requirement     : Print name and version requirement only for -c.
                               Useful for use with -e, to get a list of
                               packages to install or upgrade.
        -S,--sort            : Sort the requirements file by package name.
        -s pat,--search pat  : Search requirements for text/regex pattern.
        -v,--version         : Show version.

    The default action is to check requirements against installed packages.
    This must be ran with the same interpreter the target `pip` uses,
    which is `pip{py_ver.major}` by default.

    Currently using pip v. {pip_ver} for Python {py_ver.major}.{py_ver.minor}.
""".format(
    script=SCRIPT,
    versionstr=VERSIONSTR,
    pip_ver=pip.__version__,
    py_ver=sys.version_info
)

try:
    # Map from package name to pip package.
    PKGS = {
        p.project_name.lower(): p
        for p in pip.get_installed_distributions(local_only=False)
    }
except Exception as ex:
    print('\nUnable to retrieve packages with pip: {}'.format(ex))
    sys.exit(1)

# Map from comparison operator to actual function.
OP_FUNCS = {
    '==': lambda v1, v2: parse_version(v1) == parse_version(v2),
    '>=': lambda v1, v2: parse_version(v1) >= parse_version(v2),
    '<=': lambda v1, v2: parse_version(v1) <= parse_version(v2),
    '>': lambda v1, v2: parse_version(v1) > parse_version(v2),
    '<': lambda v1, v2: parse_version(v1) < parse_version(v2)
}

# Known EnvironmentError errno's, for better error messages.
FILE_NOT_FOUND = 2
INVALID_PERMISSIONS = 13
FILE_ERRS = {
    # Py2 does not have FileNotFoundError.
    FILE_NOT_FOUND: 'Requirements file not found: {filename}',
    # PermissionsError.
    INVALID_PERMISSIONS: 'Invalid permissions for file: {filename}',
    # Other EnvironmentError.
    None: '{msg}: {filename}\n{exc}'
}

DEFAULT_FILE = 'requirements.txt'
DEBUG = False


def main(argd):
    """ Main entry point, expects doctopt arg dict as argd. """
    global DEBUG
    DEBUG = argd['--debug']

    filename = argd['FILE'] or os.path.join(os.getcwd(), DEFAULT_FILE)

    # May opt-in to create a file that doesn't exist.
    if argd['--add']:
        return add_lines(filename, argd['--add'])

    # File must exist for all other flags.
    if argd['--duplicates']:
        return list_duplicates(filename)
    elif argd['--list']:
        return list_requirements(filename)
    elif argd['--packages']:
        return list_packages()
    elif argd['--search']:
        return search_requirements(
            argd['--search'],
            filename=filename,
            ignorecase=argd['--ignorecase'])
    elif argd['--check']:
        # Explicit check.
        return check_requirements(
            filename,
            errors_only=argd['--errors'],
            spec_only=argd['--requirement'])
    elif argd['--sort']:
        sort_requirements(filename)
        print('Sorted requirements file: {}'.format(filename))
        return 0

    # Default action, check.
    return check_requirements(
        filename,
        errors_only=argd['--errors'],
        spec_only=argd['--requirement'])


def add_lines(filename, lines):
    """ Add a requirements line to the file.
        Returns 0 on success, and 1 on error.
        Prints any errors that occur.
    """
    if not file_ensure_exists(filename):
        return 1
    reqs = Requirementz.from_file(filename)
    msgs = []
    for line in lines:
        try:
            req = RequirementPlus.parse(line)
        except ValueError as ex:
            print_err('Invalid requirement spec.: {}'.format(line))
            return 1

        try:
            if reqs.add_line(line):
                msg = 'Added requirement: {}'.format(req)
            else:
                msg = 'Replaced requirement with: {}'.format(req)
        except ValueError as ex:
            raise FatalError(str(ex))
        else:
            msgs.append(msg)

    try:
        reqs.write(filename=filename)
    except EnvironmentError as ex:
        raise FatalError(
            format_env_err(
                filename=filename,
                exc=ex,
                msg='Failed to write file'
            )
        )
    print('\n'.join(msgs))
    return 0


def check_requirements(
        filename=DEFAULT_FILE, errors_only=False, spec_only=False):
    """ Check requirements against installed versions and print status lines
        for all of them.
    """
    reqs = Requirementz.from_file(filename=filename)
    if len(reqs) == 0:
        print('Requirements file is empty.')
        return 1
    errs = 0
    for r in reqs:
        statusline = StatusLine(r)
        if errors_only and not statusline.error:
            continue
        if statusline.error:
            errs += 1
        if spec_only:
            print(statusline.spec)
        else:
            print(statusline)
    return errs


def debug(*args, **kwargs):
    """ Print a message only if DEBUG is truthy. """
    if not (DEBUG and args):
        return None

    # Include parent class name when given.
    parent = kwargs.get('parent', None)
    with suppress(KeyError):
        kwargs.pop('parent')

    # Go back more than once when given.
    backlevel = kwargs.get('back', 1)
    with suppress(KeyError):
        kwargs.pop('back')

    frame = inspect.currentframe()
    # Go back a number of frames (usually 1).
    while backlevel > 0:
        frame = frame.f_back
        backlevel -= 1
    fname = os.path.split(frame.f_code.co_filename)[-1]
    lineno = frame.f_lineno
    if parent:
        func = '{}.{}'.format(parent.__class__.__name__, frame.f_code.co_name)
    else:
        func = frame.f_code.co_name

    lineinfo = '{}:{} {}: '.format(
        C(fname, 'yellow'),
        C(str(lineno).ljust(4), 'blue'),
        C().join(C(func, 'magenta'), '()').ljust(20)
    )
    # Patch args to stay compatible with print().
    pargs = list(C(a, 'green').str() for a in args)
    pargs[0] = ''.join((lineinfo, pargs[0]))
    print(*pargs, **kwargs)


def file_ensure_exists(filename):
    """ Confirm that a requirements.txt exists, create one if the USAGESTR
        wants to. If none exists, and the user does not want to create one,
        return False.
        Returns True on success.
    """
    if os.path.isfile(filename):
        debug('File exists: {}'.format(filename))
        return True

    print('\nThis file doesn\'t exist yet: {}'.format(filename))
    ans = input('Would you like to create it? (y/N): ').strip().lower()
    if not ans.startswith('y'):
        print('\nUser cancelled.')
        return False

    try:
        with open(filename, 'w'):
            pass
        debug('Created an empty {}'.format(filename))
    except EnvironmentError as ex:
        print('\nError creating file: {}\n{}'.format(filename, ex))
        return False
    return True


def format_env_err(**kwargs):
    """ Format a custom message for EnvironmentErrors. """
    exc = kwargs.get('exc', None)
    if exc is None:
        raise ValueError('`exc` is a required kwarg.')
    filename = kwargs.get('filename', getattr(exc, 'filename', ''))
    msg = kwargs.get('msg', 'Error with file')
    return '\n{}'.format(
        FILE_ERRS.get(getattr(exc, 'errno', None)).format(
            filename=filename,
            exc=exc,
            msg=msg
        )
    )


def list_duplicates(filename=DEFAULT_FILE):
    """ Print any duplicate package names found in the file.
        Returns the number of duplicates found.
    """
    dupes = Requirementz.from_file(filename=filename).duplicates()
    dupelen = len(dupes)
    if dupelen == 0:
        print('No duplicate requirements found.')
        return 0

    print('Found {} {} with duplicate entries:'.format(
        dupelen,
        'requirement' if dupelen == 1 else 'requirements'
    ))
    for req, dupcount in dupes.items():
        print('{name:>30} has {num} {plural}'.format(
            name=req.name,
            num=dupcount,
            plural='duplicate' if dupecount == 1 else 'duplicates'
        ))
    return sum(dupes.values())


def list_packages():
    """ List all installed packages. """
    for pname in sorted(PKGS):
        p = PKGS[pname]
        print('{:<30} v. {:<8} {}'.format(
            p.project_name,
            pkg_installed_version(pname),
            p.location))


def list_requirements(filename=DEFAULT_FILE):
    """ Lists current requirements. """
    reqs = Requirementz.from_file(filename=filename)
    print('\n'.join(str(r) for r in reqs))


def pkg_installed_version(pkgname):
    """ Use pip to get an installed package version.
        Return the installed version string, or None if it isn't installed.
    """
    p = PKGS.get(pkgname.lower(), None)
    if p is None:
        return None
    try:
        return p.parsed_version.base_version
    except AttributeError:
        # Python 2...
        vers = []
        for piece in p.parsed_version:
            try:
                vers.append(str(int(piece)))
            except ValueError:
                # final, beta, etc.
                pass
        return '.'.join(vers)


def print_err(*args, **kwargs):
    """ Print a message to stderr by default. """
    if kwargs.get('file', None) is None:
        kwargs['file'] = sys.stderr
    print(C(kwargs.get('sep', ' ').join(args), 'red'), **kwargs)


def search_requirements(
        pattern, filename=DEFAULT_FILE, ignorecase=True):
    """ Search requirements lines for a text/regex pattern, and print
        results as they are found.
        Returns the number of results found.
    """
    found = 0
    reqs = Requirementz.from_file(filename=filename)
    try:
        for req in reqs.search(pattern, ignorecase=ignorecase):
            found += 1
            print(req)
    except re.error as ex:
        print('\nInvalid regex pattern: {}\n{}'.format(pattern, ex))
        return 1

    print('\nFound {} {}.'.format(
        found,
        'entry' if found == 1 else 'entries'))
    return 0 if found > 0 else 1


def sort_requirements(filename=DEFAULT_FILE):
    """ Sort a requirements file, and re-write it. """
    reqs = Requirementz.from_file(filename=filename)
    reqs.write(filename=filename)
    return 0


class FatalError(EnvironmentError):
    def __init__(self, msg):
        self.msg = msg

    def __str__(self):
        return self.msg


class RequirementPlus(Requirement):
    """ A requirements.requirement.Requirement with extra helper methods.
    """
    def __init__(self, line):
        # Requirement asks that you do not call __init__ directly,
        # but use the parse* class methods (requirement.py:128).
        super(RequirementPlus, self).__init__(line)
        # Cache the installed version of this requirement, when needed.
        self._installed_ver = None

    def __eq__(self, other):
        """ RequirementPluses are equal if they have the same specs. """
        if not hasattr(other, 'specs'):
            return False
        return set(self.specs) == set(other.specs)

    def __hash__(self):
        """ hash() implementation for RequirementPlus. """
        return hash(str(self))

    def __repr__(self):
        return str(self)

    def __str__(self):
        """ String representation of a RequirementPlus, which is compatible
            with a requirements.txt line.
        """
        if self.local_file:
            return ' '.join(('-e', self.path))
        elif self.vcs:
            hashstr = '#egg={}'.format(self.name)
            url = '@'.join((self.uri, self.revision))
            spec = ''.join((url, hashstr))
            return ' '.join(('-e', spec))

        # Normal pip package.
        extras = '[{}]'.format(', '.join(self.extras)) if self.extras else ''
        vers = self.spec_string()
        return '{}{} {}'.format(self.name, extras, vers)

    @staticmethod
    def compare_versions(ver1, op, ver2):
        """ Compare version strings according to the requirements.txt spec.
            Return True if `ver` satisfies the comparison with `ver2`.
            Arguments:
                ver1  : Installed version string.
                op    : Comparison operator ('>', or '==', or '>=', ..)
                ver2  : Required version string.

            Example:
                compare_versions('1.0.1', '>=', '1.0.0')
                >> True
                compare_versions('2.0.0' '<=', '1.0.0')
                >> False
        """
        opfunc = OP_FUNCS.get(op, OP_FUNCS['>='])
        return opfunc(ver1, ver2)

    def installed_version(self):
        """ Return a RequirementPlus for the installed version of this
            RequirementPlus, or None if it is not installed.
        """
        if self._installed_ver is not None:
            return self._installed_ver

        p = PKGS.get(self.name.lower(), None)
        if p is None:
            self._installed_ver = None
            return None
        try:
            ver = p.parsed_version.base_version
        except AttributeError:
            # Old setuptools, no base_version.
            pcs = []
            for num in p.parsed_version:
                try:
                    # Fails for '*final', 'beta', etc. Ignore it.
                    pcs.append(str(int(num)))
                except ValueError:
                    pass
                ver = '.'.join(pcs)
        self._installed_ver = RequirementPlus.parse(
            ' '.join((p.project_name, '==', ver))
        )
        return self._installed_ver

    def satisfied(self):
        """ Return True if this requirement is satisfied by the installed
            version. Non-installed packages never satisfy the requirement.
        """
        installedreq = self.installed_version()
        if installedreq is None:
            return False
        for _, installedver in installedreq.specs:
            for op, ver in self.specs:
                if self.compare_versions(installedver, op, ver):
                    return True
        return False

    def spec_string(self):
        """ Just the spec string ('>= 1.0.0, <= 2.0.0') from this requirement.
        """
        return ','.join('{} {}'.format(op, ver) for op, ver in self.specs)


class Requirementz(UserList):
    """ A list of RequirementPlus, with helper methods for reading/writing
        files, sorting, etc.
    """

    def __init__(self, requirements=None):
        super(Requirementz, self).__init__(requirements or tuple())

    def add_line(self, line):
        """ Add a requirement to this list by parsing a line/str.
            Returns True if the requirement was added,
            False if the requirement was replaced.
            Raises ValueError on error.
        """
        try:
            req = RequirementPlus.parse(line)
        except ValueError as ex:
            raise ValueError(
                'Invalid requirement spec.: {}'.format(ex)
            )
        reqname = req.name.lower()
        for i, existingreq in enumerate(self[:]):
            if reqname == existingreq.name.lower():
                debug('Found existing requirement: {}'.format(reqname))
                if req == existingreq:
                    raise ValueError(
                        'Already a requirement: {}'.format(existingreq)
                    )
                debug('...versions are different.')
                # Replace old requirement.
                self[i] = req
                return False
        else:
            # No replacement was found, add the new requirement.
            self.append(req)
        return True

    def check(self, errors_only=False, spec_only=False):
        """ Yield status lines for all requirements in this list. """
        for r in self:
            status = StatusLine(r)
            if errors_only and not status.error:
                continue
            elif spec_only:
                yield status.spec
            else:
                yield str(status)

    def duplicates(self):
        """ Return a dict of {RequirementPlus: number_of_duplicates}
            where number_of_duplicates is requirements.count(requirement) - 1
        """
        names = self.names()
        dupes = {}
        for name in names[:]:
            namecount = names.count(name)
            if namecount == 1:
                continue
            dupes[self.get_byname(name)] = namecount - 1
        return dupes

    @classmethod
    def from_file(cls, filename=DEFAULT_FILE):
        """ Instantiate a Requirementz by reading a requirements.txt and
            parsing it.
        """
        with open(filename, 'r') as f:
            reqs = cls.from_lines(f.readlines())
        # Ensure file is closed before returning the class.
        return reqs

    @classmethod
    def from_lines(cls, lines):
        """ Instantiate a Requirementz from a list of requirements.txt lines.
        """
        return cls(RequirementPlus.parse(l) for l in sorted(lines))

    def get_byname(self, name):
        """ Return the first RequirementPlus found by name.
            Returns None if no requirement could be found.
        """
        for r in self:
            if r.name == name:
                return r
        return None

    def names(self):
        """ Return a tuple of names only from these RequirementPluses. """
        return tuple(r.name for r in self)

    def search(self, pattern, ignorecase=True, reverse=False):
        """ Search RequirementPluses using a text/regex pattern.
            Yield RequirementPluses that match.
            If `reverse` is truthy, yields items that DON'T match.
        """
        strpat = getattr(pattern, 'pattern', pattern)
        flags = re.IGNORECASE if ignorecase else 0
        pat = re.compile(strpat, flags=flags)

        def pat_no_match(r):
            """ RequirementPlus is a match if pattern is NOT found. """
            return pat.search(str(r)) is None

        def pat_match(r):
            """ RequirementPlus is a match if pattern IS found. """
            return pat.search(str(r)) is not None
        is_match = pat_no_match if reverse else pat_match
        for r in self:
            if is_match(r):
                yield r

    def write(self, filename=DEFAULT_FILE):
        """ Write this list of requirements to file. """
        debug('Writing sorted file: {}'.format(filename))
        with SafeWriter(filename, 'w') as f:
            f.write('\n'.join(
                str(r) for r in sorted(self, key=lambda r: r.name)
            ))
            f.write('\n')
        return None


class SafeWriter(object):
    def __init__(self, filename, mode='w'):
        self.filename = filename
        self.mode = mode
        self.f = None
        self.backed_up = False

    def __enter__(self):
        self.file_backup()
        debug(
            'Opening file for mode \'{s.mode}\': {s.filename}'.format(s=self))
        self.f = open(self.filename, mode=self.mode)
        return self.f

    def __exit__(self, extype, val, tb):
        self.f.close()
        if extype is None:
            # No error occurred, safe to remove backup.
            self.file_backup_remove()
        else:
            print_err('A backup file was saved.')

    def file_backup(self):
        """ Create a backup copy, in case something fails. """
        if not os.path.exists(self.filename):
            # File doesn't exist, no backup needed.
            return None
        backupfile = '{}.bak'.format(self.filename)
        debug('Creating backup file: {}'.format(backupfile))
        try:
            shutil.copy2(self.filename, backupfile)
        except EnvironmentError as ex:
            raise FatalError(
                format_env_err(
                    filename=self.filename,
                    exc=ex,
                    msg='Failed to backup')
            )
        self.backed_up = True
        return None

    def file_backup_remove(self):
        """ Remove a backup file, after everything else is done. """
        backupfile = '{}.bak'.format(self.filename)
        if not os.path.exists(backupfile):
            if self.backed_up:
                debug('Backup file does not exist: {}'.format(backupfile))
            return None

        debug('Removing backup file: {}'.format(backupfile))
        try:
            os.remove(backupfile)
        except EnvironmentError as ex:
            raise FatalError(format_env_err(
                filename=backupfile,
                exc=ex,
                msg='Failed to remove backup file'
            ))
        return None


class StatusLine(object):
    def __init__(self, req):
        self.req = req
        self.error = False

        # Init this requirement's status line.
        installedver = req.installed_version()
        includedvers = set(
            ver for op, ver in req.specs if op.endswith('=')
        )
        for op, ver in req.specs:
            if ver == '0':
                requiredver = C('installed', fore='cyan')
                break
        else:
            requiredver = req.spec_string()

        self.spec = '{} {}'.format(req.name, requiredver)

        if installedver is None:
            # No version installed.
            installverstr = None
            installverfmt = C('not installed', fore='red')
            errstatus = C('!', fore='red')
            self.error = True
        else:
            installverstr = installedver.specs[0][1]
            installverfmt = C(' ').join('v.', C(installverstr, fore='cyan'))
            if req.satisfied():
                # Version installed/required mismatches (still okay)
                if installverstr in includedvers:
                    errstatus = ' '
                else:
                    errstatus = C('-', fore='yellow')
            else:
                errstatus = C('!', fore='red')
                self.error = True

        verboseerr = C('Error', fore='red', style='bright')
        verboseok = C('Ok', fore='green')
        # Build status line.
        s = '{verbose} {name} {installed} {status} {required}'
        self.status = s.format(
            verbose=(verboseerr if self.error else verboseok).ljust(5),
            name=C(req.name, fore='blue').ljust(30),
            installed=installverfmt.ljust(13),
            status=errstatus,
            required=C(requiredver, fore=('red' if self.error else 'green'))
        )

    def __str__(self):
        return self.status


if __name__ == '__main__':
    try:
        mainret = main(docopt(USAGESTR, version=VERSIONSTR))
    except FatalError as ex:
        print_err('\n{}\n'.format(ex))
        mainret = 1
    except EnvironmentError as ex:
        print_err(format_env_err(exc=ex))
        mainret = 1
    sys.exit(mainret)
