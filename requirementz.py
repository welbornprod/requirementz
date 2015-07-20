#!/usr/bin/env python3
# -*- coding: utf-8 -*-

""" requirementz.py
    Check requirements.txt against installed packages using pip and
    requirements-parser.
    Bonus features:
    Check for duplicate entries, search for entries using regex,
    add requirement lines (without clobbering existing comments/whitespace),
    and list requirements or all installed packages (both formatted
    for readability).

    Originally designed for Python3, but backporting was fairly easy
    (it cost some readability though). This should run on at least Python 2.7.
    -Christopher Welborn 07-19-2015
"""

# TODO: Figure out what to do with cvs or local requirements. -Cj

from __future__ import print_function
import os
import pip
import re
import sys
from pkg_resources import parse_version

import requirements
from docopt import docopt
from requirements.requirement import Requirement

NAME = 'Requirementz'
VERSION = '0.0.2'
VERSIONSTR = '{} v. {}'.format(NAME, VERSION)
SCRIPT = os.path.split(os.path.abspath(sys.argv[0]))[1]

USAGESTR = """{versionstr}
    Usage:
        {script} -h | -p | -v
        {script} [-c] [-e] [-r] [FILE]
        {script} [-d | -l | -a line | (-s pat [-i])] [FILE]

    Options:
        FILE                 : Requirements file to parse.
                               Default: requirements.txt
        -a line,--add line   : Add a requirement line to the file.
        -c,--check           : Check installed packages against requirements.
        -d,--duplicates      : List any duplicate entries.
        -e,--errors          : Only show errored packages with -c.
        -h,--help            : Show this help message.
        -i,--ignorecase      : Case insensitive when searching.
        -l,--list            : List all requirements.
        -p,--packages        : List all installed packages.
        -r,--requirement     : Print name and version requirement only with -c.
                               Useful for use with -e, to get a list of
                               packages to install or upgrade.
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


def main(argd):
    """ Main entry point, expects doctopt arg dict as argd. """
    filename = argd['FILE'] or os.path.join(os.getcwd(), 'requirements.txt')

    # May opt-in to create a file that doesn't exist.
    if argd['--add']:
        return add_line(filename, argd['--add'])

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
            nocase=argd['--ignorecase'])
    elif argd['--check']:
        # Explicit check.
        return check_requirements(
            filename,
            errors_only=argd['--errors'],
            spec_only=argd['--requirement'])
    # Default action, check.
    return check_requirements(
        filename,
        errors_only=argd['--errors'],
        spec_only=argd['--requirement'])


def add_line(filename, line):
    """ Add a requirements line to the file.
        Returns 0 on success, and 1 on error.
        Prints any errors that occur.
    """
    try:
        req = Requirement.parse_line(line)
    except ValueError as ex:
        print('\nInvalid requirement specification: {}'.format(ex))
        return 1

    if not exists_or_create(filename):
        return 1

    reqname = req.name.lower()

    for existingname, op, requiredver in iter_specs(filename):
        if existingname == reqname:
            print('\n'.join((
                '\nThis requirement already exists!: {} {} {}',
                'Edit the file to change the specification.'
            )).format(
                existingname,
                op,
                requiredver)
            )
            return 1

    try:
        with open(filename, 'a') as f:
            f.write('{}\n'.format(req.line))
    except EnvironmentError as ex:
        print('\nFailed to write requirements: {}\n{}'.format(filename, ex))
        return 1

    print('Added requirement: {}'.format(req.line))
    return 0


def check_requirement(name, op, ver, errors_only=False, spec_only=False):
    """ Check a single requirement, and print it's status.
        Arguments:
            name         : Package name to check.
            op           : Comparison operator for required version.
                           Example: '==', or '>=', or '<', ..
            ver          : Required version string.
            errors_only  : Whether to only print errored packages.
            spec_only    : Whether to print only names and required version.
                           Useful in combination with errors_only.
        Returns 1 if the requirement is not satisfied, or 0 on success.
    """
    installver = installed_version(name)
    requiredver = 'installed' if ver == '0' else '{} {}'.format(op, ver)
    if installver is None:
        errstatus = '!'
        err = True
    else:
        err = False
        if installver is None:
            errstatus = '!'
            err = True
        else:
            if compare_versions(installver, op, ver):
                errstatus = ' '
            else:
                errstatus = '!'
                err = True
    if errors_only and not err:
        return 0
    elif spec_only:
        # Print package and required version.
        # Makes it easy to write a script to install/upgrade packages.
        print('{} {} {}'.format(name, op, ver))
        return int(err)
    # Full format.
    statfmt = '{state:<5} {name:<30} {installed:<13} {err} {required}'
    installstr = 'v. {}'.format(installver) if installver else 'not installed'
    print(statfmt.format(
        state='Error' if err else 'Ok',
        name=name,
        installed=installstr,
        err=errstatus,
        required=requiredver))
    return int(err)


def check_requirements(
        filename='requirements.txt', errors_only=False, spec_only=False):
    """ Check a requirements file, print package/requirements info.
        Returns an exit code (0 for success, non-zero for errors)
    """
    checked = 0
    errors = 0
    try:
        for pkgname, op, installver in iter_specs(filename):
            errors += check_requirement(
                pkgname,
                op,
                installver,
                errors_only=errors_only,
                spec_only=spec_only)
            checked += 1
    except Exception as ex:
        print('\nError checking requirements in {}\n  {}'.format(
            filename,
            ex))
        return 1

    if checked > 0:
        return errors

    print('Requirements file was empty.')
    return 1


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


def exists_or_create(filename):
    """ Confirm that a requirements.txt exists, create one if the USAGESTR
        wants to. If none exists, and the user does not want to create one,
        return False.
        Returns True on success.
    """
    if os.path.isfile(filename):
        return True

    print('\nThis file doesn\'t exist yet: {}'.format(filename))
    ans = input('Would you like to create it? (y/N): ').strip().lower()
    if not ans.startswith('y'):
        print('\nUser cancelled.')
        return False

    try:
        with open(filename, 'w'):
            pass
    except EnvironmentError as ex:
        print('\nError creating file: {}\n{}'.format(filename, ex))
        return False
    return True


def format_requirement(r):
    """ Return a formatted a Requirement for display. """
    vers = ', '.join('{:<2} {}'.format(s[0], s[1]) for s in r.specs)
    extras = '[{}]'.format(', '.join(r.extras)) if r.extras else ''
    return '{:<30} {:<30} {}'.format(r.name, vers, extras)


def installed_version(pkgname):
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


def iter_requirements(filename='requirements.txt', sort=True):
    """ Iterate over a sorted requirements.txt, yield Requirement objects. """
    try:
        with open(filename, 'r') as f:
            reqgen = requirements.parse(f)
            if sort:
                for r in sorted(reqgen, key=lambda r: r.name):
                    yield r
            else:
                for r in reqgen:
                    yield r
    except EnvironmentError as ex:
        errmsgs = {
            # Py2 does not have FileNotFoundError.
            2: 'Requirements file not found: {}'.format(filename),
            # PermissionsError.
            13: 'Invalid permissions for file: {}'.format(filename),
            # Other EnvironmentError.
            None: 'Error reading requirements file: {}\n{}'.format(
                filename,
                ex)
        }
        print('\n{}'.format(errmsgs.get(getattr(ex, 'errno', None))))
        sys.exit(1)
    return


def iter_search(pattern, filename='requirements.txt', nocase=True):
    """ Search requirements file using a text/regex pattern.
        Yields lines that match.
    """
    reflags = re.IGNORECASE if nocase else 0
    pat = re.compile(pattern, flags=reflags)
    for r in iter_requirements(filename=filename):
        if pat.search(r.line) is not None:
            yield r.line


def iter_specs(filename='requirements.txt'):
    """ Iterate over requirements from a requirements file.
        Yields tuples of: (package_name, comparison_operator, version_string)
    """
    for r in iter_requirements(filename=filename):
        if r.specs:
            for op, ver in r.specs:
                yield r.name, op, ver
        else:
            yield r.name, '>', '0'


def list_duplicates(filename='requirements.txt'):
    """ Print any duplicate package names found in the file.
        Returns the number of duplicates found.
    """
    reqs = list(iter_requirements(filename=filename, sort=False))
    names = [r.name.lower() for r in reqs]
    dupes = set()
    dupetotal = 0
    for i, name in enumerate(names):
        if names.count(name) > 1:
            print('#{:<4} {}'.format(i, format_requirement(reqs[i])))
            dupetotal += 1
            if name not in dupes:
                dupes.add(name)

    dupecnt = len(dupes)
    pluralentry = 'entry has' if dupecnt == 1 else 'entries have'
    pluraltotal = 'duplicates'

    print('\nFound {} {}. {} {} {}.'.format(
        dupetotal,
        pluraltotal,
        dupecnt,
        pluralentry,
        pluraltotal))
    return dupetotal


def list_packages():
    """ List all installed packages. """
    for pname in sorted(PKGS):
        p = PKGS[pname]
        print('{:<30} v. {:<8} {}'.format(
            p.project_name,
            installed_version(pname),
            p.location))


def list_requirements(filename='requirements.txt'):
    """ Lists current requirements. """
    for r in iter_requirements(filename=filename):
        print(format_requirement(r))


def search_requirements(pattern, filename='requirements.txt', nocase=True):
    """ Search requirements lines for a text/regex pattern, and print
        results as they are found.
        Returns the number of results found.
    """
    found = 0
    try:
        for line in iter_search(pattern, filename=filename, nocase=nocase):
            found += 1
            print(line)
    except re.error as ex:
        print('\nInvalid regex pattern: {}\n{}'.format(pattern, ex))
        return 1

    print('\nFound {} {}.'.format(
        found,
        'entry' if found == 1 else 'entries'))
    return 0 if found > 0 else 1

if __name__ == '__main__':
    mainret = main(docopt(USAGESTR, version=VERSIONSTR))
    sys.exit(mainret)
