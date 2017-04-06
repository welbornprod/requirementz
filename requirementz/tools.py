#!/usr/bin/env python3
""" Requirementz - Classes
    Classes and utility functions for requirementz.
    -Christopher Welborn 3-5-17
"""

import json
import os
import pip
import re
import shutil
import sys
from collections import UserList
from contextlib import suppress
from functools import total_ordering
from pkg_resources import parse_version
from urllib.error import HTTPError
from urllib.request import urlopen

from requirements.requirement import Requirement

from colr import Colr as C
from printdebug import DebugColrPrinter
debugprinter = DebugColrPrinter()
debugprinter.disable()
debug = debugprinter.debug

__version__ = '0.3.3'

# Operates on ./requirements.txt by default.
DEFAULT_FILE = 'requirements.txt'

# Map from comparison operator to actual version comparison function.
OP_FUNCS = {
    '==': lambda v1, v2: parse_version(v1) == parse_version(v2),
    '>=': lambda v1, v2: parse_version(v1) >= parse_version(v2),
    '<=': lambda v1, v2: parse_version(v1) <= parse_version(v2),
    '>': lambda v1, v2: parse_version(v1) > parse_version(v2),
    '<': lambda v1, v2: parse_version(v1) < parse_version(v2)
}

# 256 color numbers.
LIGHTPURPLE = 63
LIGHTRED = 196

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


def colr_label(label, value, **kwargs):
    """ Colorize a label/value pair.
        Any kwargs are passed on to colr for the value.
    """
    return C(': ').join(C(label, 'cyan'), C(value, 'blue', **kwargs))


def colr_name(name, **kwargs):
    """ Colorize a name (str). This function is used for consistency.
        Any kwargs are passed on to Colr.
    """
    error = False
    with suppress(KeyError):
        error = kwargs.pop('error')

    if error:
        color = LIGHTRED if is_local_pkg(name) else 'red'
    else:
        color = LIGHTPURPLE if is_local_pkg(name) else 'blue'
    return C(name, color, **kwargs)


def colr_num(num, **kwargs):
    """ Colorize a number. This function is used for consistency.
        Any kwargs are passed on to Colr.
    """
    return C(num, 'blue', **kwargs)


def format_env_err(**kwargs):
    """ Format a custom message for EnvironmentErrors. """
    exc = kwargs.get('exc', None)
    if exc is None:
        raise ValueError('`exc` is a required kwarg.')
    filename = kwargs.get('filename', getattr(exc, 'filename', ''))
    msg = kwargs.get('msg', 'Error with file')
    return C('\n{}').format(
        C(
            FILE_ERRS.get(getattr(exc, 'errno', None)).format(
                filename=C(filename, 'blue'),
                exc=C(exc, 'red', style='bright'),
                msg=C(msg, 'red'),
            ),
            'red',
        )
    )


def get_pypi_info(packagename):
    url = 'https://pypi.python.org/pypi/{}/json'.format(packagename)
    debug('Getting info for \'{}\' from: {}'.format(packagename, url))
    try:
        con = urlopen(url)
    except HTTPError as excon:
        if excon.code == 404:
            excon.msg = 'No package found for: {}'.format(packagename)
        else:
            excon.msg = '\n'.join((
                'Unable to connect to get info for: {}'.format(url),
                excon.msg
            ))
        raise excon
    else:
        try:
            jsonstr = con.read().decode()
        except UnicodeDecodeError as exdec:
            raise UnicodeDecodeError(
                'Unable to decode data from package info: {}\n{}'.format(
                    url,
                    exdec
                ),
            ) from exdec
        finally:
            con.close()

    try:
        data = json.loads(jsonstr)
    except ValueError as exjson:
        raise ValueError(
            'Unable to decode JSON data from: {}\n{}'.format(url, exjson),
        ) from exjson
    return data


def is_local_pkg(name):
    """ Returns True if the package name is installed somewhere in /home.
    """
    pkg = PKGS.get(name.lower().strip(), None)
    if pkg is None:
        return False
    if not pkg.location:
        return False
    return pkg.location.startswith('/home')


def load_packages(local_only=False):
    """ Load all known packages from pip.
        Returns a dict of {package_name.lower(): Package}
        Possibly raises a FatalError.
    """
    debug('Loading package list...')
    try:
        # Map from package name to pip package.
        pkgs = {
            p.project_name.lower(): p
            for p in pip.get_installed_distributions(local_only=local_only)
        }
    except Exception as ex:
        raise FatalError(
            'Unable to retrieve packages with pip: {}'.format(ex)
        )
    debug('Packages loaded: {}'.format(len(pkgs)))
    return pkgs


def print_err(*args, **kwargs):
    """ Print a message to stderr by default. """
    if kwargs.get('file', None) is None:
        kwargs['file'] = sys.stderr
    nothing = object()
    value = nothing
    with suppress(KeyError):
        value = kwargs.pop('value')
    error = nothing
    with suppress(KeyError):
        error = kwargs.pop('error')

    msg = kwargs.get('sep', ' ').join(
        str(a) if isinstance(a, C) else str(C(a, 'red'))
        for a in args
    )
    if (value is nothing) and (error is nothing):
        print(msg, **kwargs)
        return None
    # Label/value pair.
    if value is not nothing:
        msg = C(': ').join(msg, C(value, 'blue'))
    if error is not nothing:
        msg = C('\n  ').join(msg, C(error, 'red', style='bright'))
    print(msg, **kwargs)
    return None


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


@total_ordering
class RequirementPlus(Requirement):
    """ A requirements.requirement.Requirement with extra helper methods.
    """
    name_width = 25
    ver_width = 16

    def __init__(self, line):
        # Requirement asks that you do not call __init__ directly,
        # but use the parse* class methods (requirement.py:128).
        super().__init__(line)
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

    def __lt__(self, other):
        nothing = object()
        othername = getattr(other, 'name', nothing)
        if othername is nothing:
            return False
        if not (self.name < othername):
            return False

        otherspecs = getattr(other, 'specs', nothing)
        try:
            specslt = self.specs < otherspecs
        except TypeError:
            if self.specs:
                # Other has no specs.
                return False
            # Self has no specs.
            return bool(other.specs)
        return specslt

    def __repr__(self):
        return str(self)

    def __str__(self):
        """ String representation of a RequirementPlus, which is compatible
            with a requirements.txt line.
        """
        return self.to_str(color=False, align=False, location=False)

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

    def location(self, color=False, default=''):
        """ Returns the location of any installed version for this
            requirement. If the package is not installed, then `default`
            is returned.
        """
        p = PKGS.get(self.name.lower(), None)
        if p is None:
            loc = default or ''
        else:
            loc = p.location or (default or '')
        if color:
            return str(C(loc, 'yellow'))
        return loc

    def satisfied(self, against=None):
        """ Return True if this requirement is satisfied by the installed
            version. Non-installed packages never satisfy the requirement.
            If no `against` requirement is given, and no installed version
            exists, this always returns False.
            Arguments:
                against  : Requirement/RequirementPlus or version string to
                           test against.
                           Default: installed version Requirement, if any.
        """
        againstreq = self.installed_version() if against is None else against
        if againstreq is None:
            return False
        if isinstance(againstreq, str):
            againstspecs = (('', againstreq), )
        elif hasattr(againstreq, 'specs'):
            againstspecs = againstreq.specs
        else:
            raise TypeError(
                ' '.join((
                    'Expecting version str or Requirement/RequirementPlus,',
                    'got: ({}) {!r}'
                )).format(type(against).__name__, against)
            )
        for _, againstver in againstspecs:
            for op, ver in self.specs:
                if self.compare_versions(againstver, op, ver):
                    return True
        return False

    def spec_string(self, color=False, error=False, ljust=None):
        """ Just the spec string ('>= 1.0.0, <= 2.0.0') from this requirement.
        """
        if color:
            return str(
                C(',').join(
                    C(' ').join(
                        C(op),
                        C(ver, 'red' if error else 'cyan'),
                    )
                    for op, ver in self.specs
                ).ljust(ljust or 0)
            )
        return ','.join(
            '{} {}'.format(op, ver)
            for op, ver in self.specs
        ).ljust(ljust or 0)

    def to_str(self, color=False, align=False, location=False, error=False):
        """ Like __str__, except colors can be used, and more info can
            be added.
            Arguments:
                color    : Whether to colorize the string.
                align    : Whether to align the names/versions.
                location : Whether to show the location for this requirement,
                           (if installed).
                error    : Whether to color the name as an error.
        """
        if self.local_file:
            if color:
                return str(C(' ').join(
                    C('-e', 'cyan'),
                    C(self.path, 'green'),
                ))
            return ' '.join(('-e', self.path))
        elif self.vcs:
            if color:
                hashstr = str(
                    C('=').join(C('#egg', 'lightblue'), C(self.name, 'green'))
                )
            else:
                hashstr = '#egg={}'.format(self.name)
            if color:
                url = str(
                    C('@').join(
                        C(self.uri, 'blue'),
                        C(self.revision, 'yellow'),
                    )
                )
            else:
                url = '@'.join((self.uri, self.revision))
            spec = ''.join((url, hashstr))
            if color:
                return C(' ').join(
                    C('-e', 'cyan'),
                    spec,
                )
            return ' '.join(('-e', spec))

        # Normal pip package.
        if self.extras:
            if color:
                extras = C(', ').join(
                    C(e, 'cyan')
                    for e in self.extras
                ).join('[', ']', style='bright')
            else:
                extras = '[{}]'.format(', '.join(self.extras))
        else:
            extras = ''

        namefmt = '{name:<{ljust}}'.format(
            name=C('').join(
                colr_name(self.name, error=error) if color else self.name,
                extras,
            ),
            ljust=self.name_width if align else 0,
        )
        s = '{name} {ver}'.format(
            name=namefmt,
            ver=self.spec_string(
                color=color,
                error=error,
                ljust=self.ver_width if align else 0,
            ),
        )
        if location:
            s = ' '.join((
                s,
                self.location(color=color, default='(not installed)'),
            ))
        return s


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

    def iter_str(self, color=False, align=False, location=False):
        """ Yields req.to_str() for each RequirementPlus in this list.
            The keyword arguments are passed on to RequirementPlus.to_str().
            Alignment/justification is calculated before iterating.
        """
        try:
            max_name = len(max(self, key=lambda req: len(req.name)).name)
            max_ver = len(
                max(self, key=lambda req: len(req.spec_string(color=False)))
                .spec_string(color=False)
            )
        except ValueError:
            # No requirements to iterate over.
            pass
        else:
            for req in sorted(self, key=lambda req: req.name):
                req.name_width = max_name
                req.ver_width = max_ver
                yield req.to_str(color=color, align=align, location=location)

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
        # This will be set to the backed up file name, if one is made.
        # On success, the backup is removed.
        self.backup = None

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
            return False
        if self.backup:
            print_err('A backup file was saved', value=self.backup)
            return False
        print_err('No backup was saved!')
        return False

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
                    msg='Failed to backup'
                )
            )
        self.backup = backupfile
        return None

    def file_backup_remove(self):
        """ Remove a backup file, after everything else is done. """
        if not self.backup:
            debug('No backup file was set.')
            return None
        if not os.path.exists(self.backup):
            debug('Backup file does not exist: {}'.format(self.backup))
            return None

        debug('Removing backup file: {}'.format(self.backup))
        try:
            os.remove(self.backup)
        except EnvironmentError as ex:
            raise FatalError(format_env_err(
                filename=self.backup,
                exc=ex,
                msg='Failed to remove backup file'
            ))
        return None


class StatusLine(object):
    def __init__(self, req):
        self.req = req
        self.error = False
        # Cached by self.with_latest() on demand.
        self.pypi_info = None
        self.status_latest = None

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
                    errstatus = C('-', fore='yellow', style='bright')
            else:
                errstatus = C('!', fore='red', style='bright')
                self.error = True

        verboseerr = C('Error', fore='red', style='bright')
        verboseok = C('Ok', fore='green')
        # Build status line.
        colr_fmt = C(
            '{verbose:<5} {name:<30} {installed:<13} {status} {required:<12}'
        )
        self.status_colr = colr_fmt.format(
            verbose=verboseerr if self.error else verboseok,
            name=colr_name(req.name, error=self.error),
            installed=installverfmt,
            status=errstatus,
            required=C(
                requiredver,
                fore=('red' if self.error else 'green')
            ),
        )
        self.pkg = PKGS.get(self.req.name.lower(), None)
        self.pkg_location = getattr(self.pkg, 'location', None)

    def __str__(self):
        return self.to_str(color=False)

    def location(self, color=False, default=''):
        """ Return the location on disk for this requirement's package,
            if installed. Otherwise return ''.
        """
        s = self.pkg_location or (default or '')
        if color:
            return str(C(s, 'yellow'))
        return s

    def spec(self, color=False, align=False):
        """ Return self.spec if color is False, otherwise colorize self.spec
            and return it.
        """
        # The requirement handles spec strings, we just need to tell it
        # whether it was an erroneous requirement.
        return self.req.to_str(color=color, align=align, error=self.error)

    def status(self, color=False, location=False):
        """ Return a stringified status for this requirement. """
        statusstr = str(
            self.status_colr if color else self.status_colr.stripped()
        )
        if location:
            return ' '.join((
                statusstr,
                self.location(color=color, default='(not installed)')
            ))
        return statusstr

    def with_latest(self, color=False, location=False):
        """ Return this status line, with the latest available version
            appended. This connects to pypi to retrieve the latest.
            Possibly raises urllib.error.HTTPError, UnicodeDecodeError, and
            ValueError from `get_pypi_info()`.
        """
        if self.status_latest:
            # Info is cached for this requirement, no need to contact pypi.
            return self.status_latest

        # Grab pypi info from python.org.
        try:
            pypiinfo = get_pypi_info(self.req.name)
        except HTTPError as exhttp:
            if exhttp.code != 404:
                # A real error occurred.
                raise
            # Package not found on pypi.
            latest_color = LIGHTRED
            markerstr = C('?', 'magenta', style='bright')
            verstr = C('not found', latest_color)
        else:
            latest = pypiinfo.get('info', {}).get('version', None)
            if latest is None:
                print_err('No version info found for', value=self.req.name)
                return self.status
            self.pypi_info = pypiinfo

            if self.req.satisfied(against=latest):
                reqver = self.req.specs[0][1]
                if reqver == latest:
                    markerstr = ' '
                    latest_color = 'green'
                else:
                    markerstr = C('-', 'yellow', style='bright')
                    latest_color = 'yellow'
            else:
                latest_color = 'red'
                markerstr = C('!', 'red', style='bright')

            verstr = C(self.pypi_info['info']['version'], fore=latest_color)
        latest_colr = C('{} {}').format(
            # Location will be appended after the pypi info.
            self.status(color=color, location=False),
            C(
                '{} {}: {:<10}'.format(
                    markerstr,
                    C('pypi', LIGHTPURPLE),
                    verstr,
                )
            )
        )
        if location:
            latest_colr = C(' ').join((
                latest_colr,
                self.location(color=True, default='(not installed)'),
            ))
        if color:
            self.status_latest = str(latest_colr)
        else:
            self.status_latest = str(latest_colr.stripped())
        return self.status_latest

    def to_str(self, color=False, location=False):
        if location:
            return C(' ').join(
                self.status(color=color),
                self.location(color=color, default='(not installed)')
            )
        return self.status(color=color)


# Global {package_name: package} dict.
PKGS = load_packages()
