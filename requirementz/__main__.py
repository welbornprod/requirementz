#!/usr/bin/env python3
# -*- coding: utf-8 -*-

""" requirementz.py
    Check requirements.txt against installed/latest packages using pip and
    requirements-parser.
    Bonus features:
      Check for duplicate entries
      Search for entries using regex.
      Add requirement lines.
      List requirements or all installed packages (formatted for readability).
      View package info from PyPi.
      Sort the requirements file.

    This is for Python 3 only.
    -Christopher Welborn 07-19-2015
"""

# TODO: Figure out what to do with cvs or local requirements. -Cj
import os
import pip
import re
import sys
import traceback
from urllib.error import HTTPError

from colr import (
    auto_disable as colr_auto_disable,
    disable as colr_disable,
    docopt,
    Colr as C
)
from fmtblock import FormatBlock

from .tools import (
    __version__,
    colr_label,
    colr_name,
    colr_num,
    debug,
    debugprinter,
    DEFAULT_FILE,
    EmptyFile,
    FatalError,
    format_env_err,
    get_pypi_info,
    parse_version,
    PKGS,
    print_err,
    RequirementPlus,
    Requirementz,
    sort_requirements,
    StatusLine,
)
colr_auto_disable()


NAME = 'Requirementz'
VERSIONSTR = '{} v. {}'.format(NAME, __version__)
SCRIPT = 'requirementz'

USAGESTR = """{versionstr}

    Requirementz checks a requirements.txt package list against installed
    packages or packages found on pypi. It can also show pypi's latest
    information for a package, sort a requirements.txt, or find duplicate
    entries.

    Usage:
        {script} (-h | -v) [-D] [-n]
        {script} [-c | -C] [-e] [-L | -r] [-f file] [-D] [-n]
        {script} [-a line... | -d]        [-f file] [-D] [-n]
        {script} -l [-L | -r]             [-f file] [-D] [-n]
        {script} (-P | -S)                [-f file] [-D] [-n]
        {script} -p [-L]                            [-D] [-n]
        {script} -s pat [-i]              [-f file] [-D] [-n]
        {script} PACKAGE...                         [-D] [-n]

    Options:
        PACKAGE              : Show pypi info for package names.
        -a line,--add line   : Add a requirement line to the file.
                               The -a flag can be used multiple times.
        -C,--checklatest     : Check installed packages and latest versions
                               from PyPi against requirements.
        -c,--check           : Check installed packages against requirements.
        -D,--debug           : Print some debug info while running.
        -d,--duplicates      : List any duplicate entries.
        -e,--errors          : Only show packages with errors when checking.
        -f file,--file file  : Requirements file to parse.
                               Default: ./requirements.txt
        -h,--help            : Show this help message.
        -i,--ignorecase      : Case insensitive when searching.
        -L,--location        : When listing, sort by location instead of name.
                               When checking, show the package location.
        -l,--list            : List all requirements.
        -n,--nocolor         : Force plain text, with no color codes.
        -P,--pypi            : Show pypi info for all packages in
                               requirements.txt.
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

# Handling this flag the old way for early access (before docopt arg parsing).
DEBUG = ('-D' in sys.argv) or ('--debug' in sys.argv)
if DEBUG:
    debugprinter.enable()


def main(argd):
    """ Main entry point, expects doctopt arg dict as argd. """
    global DEBUG
    DEBUG = argd['--debug']
    if argd['--nocolor']:
        colr_disable()

    filename = argd['--file'] or os.path.join(os.getcwd(), DEFAULT_FILE)

    # May opt-in to create a file that doesn't exist.
    if argd['--add']:
        return add_lines(filename, argd['--add'])

    # File must exist for all other flags.
    if argd['--check'] or argd['--checklatest']:
        # Explicit check.
        return check_requirements(
            filename,
            errors_only=argd['--errors'],
            spec_only=argd['--requirement'],
            latest=argd['--checklatest'],
            location=argd['--location'],
        )
    elif argd['--duplicates']:
        return list_duplicates(filename)
    elif argd['--list']:
        return list_requirements(filename, location=argd['--location'])
    elif argd['--packages']:
        return list_packages(location=argd['--location'])
    elif argd['--search']:
        return search_requirements(
            argd['--search'],
            filename=filename,
            ignorecase=argd['--ignorecase']
        )
    elif argd['--pypi']:
        return show_package_infos(get_requirement_names(filename))
    elif argd['--sort']:
        if sort_requirements(filename):
            print('Sorted requirements file: {}'.format(filename))
        return 0
    elif argd['PACKAGE']:
        return show_package_infos(argd['PACKAGE'])

    # Default action, check.
    return check_requirements(
        filename,
        errors_only=argd['--errors'],
        spec_only=argd['--requirement'],
        latest=argd['--checklatest'],
        location=argd['--location'],
    )


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
        except ValueError:
            print_err('Invalid requirement spec.', value=line)
            return 1

        try:
            if reqs.add_line(line):
                msg = colr_label('Added requirement', req)
            else:
                msg = colr_label('Replaced requirement with', req)
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
    print(C('\n').join(msgs))
    return 0


def check_requirements(
        filename=DEFAULT_FILE,
        errors_only=False, spec_only=False, latest=False, location=False):
    """ Check requirements against installed versions and print status lines
        for all of them.
    """
    reqs = Requirementz.from_file(filename=filename)
    if len(reqs) == 0:
        raise EmptyFile()
    errs = 0
    for r in reqs:
        statusline = StatusLine(r)
        if errors_only and not statusline.error:
            continue
        if statusline.error:
            errs += 1
        if spec_only:
            print(statusline.spec(color=True, align=True))
        elif latest:
            print(statusline.with_latest(color=True, location=location))
        else:
            print(statusline.to_str(color=True, location=location))
    return errs


def confirm(s, default=False):
    """ Confirm a yes/no question. """
    if default:
        defaultstr = C('/', style='bright').join(
            C('Y', 'green'),
            C('n', 'red')
        )
    else:
        defaultstr = C('/', style='bright').join(
            C('y', 'green'),
            C('N', 'red')
        )
    s = '{} ({}): '.format(C(s, 'cyan'), defaultstr)
    try:
        answer = input(s).strip().lower()
    except EOFError:
        raise UserCancelled()
    if answer:
        return answer.startswith('y')

    # no answer, return the default.
    return default


def entry_point():
    """ The actual entry point for this script, created to handle
        setuptools console scripts. Module-level error handling goes here.
        This function is responsible for starting `main()` and exiting the
        program.
    """
    try:
        mainret = main(docopt(USAGESTR, version=VERSIONSTR, script=SCRIPT))
    except EmptyFile as ex:
        # This is actually not an error.
        # There's just nothing to do with an empty file.
        print_err(str(ex))
        mainret = 0
    except (KeyboardInterrupt, UserCancelled) as ex:
        if not isinstance(ex, UserCancelled):
            ex = UserCancelled()
        print_err('\n{}'.format(ex))
        mainret = 2
    except (FatalError, HTTPError, UnicodeDecodeError, ValueError) as ex:
        if DEBUG:
            print_err('\n{}\n'.format(traceback.format_exc()))
        else:
            print_err('\n{}\n'.format(ex))
        mainret = 1
    except EnvironmentError as ex:
        if DEBUG:
            print_err(traceback.format_exc())
        else:
            print_err(format_env_err(exc=ex))
        mainret = 1

    sys.exit(mainret)


def file_ensure_exists(filename):
    """ Confirm that a requirements.txt exists, create one if the user
        wants to. If none exists, and the user does not want to create one,
        return False.
        Returns True on success.
    """
    if os.path.isfile(filename):
        debug('File exists: {}'.format(filename))
        return True

    print_err(colr_label('\nThis file doesn\'t exist yet', filename))
    if not confirm('Create it?'):
        raise UserCancelled()

    try:
        with open(filename, 'w'):
            pass
        debug('Created an empty {}'.format(filename))
    except EnvironmentError as ex:
        print('\nError creating file: {}\n{}'.format(filename, ex))
        return False
    return True


def get_pypi_release_dls(releases):
    """ Count downloads from the `releases` key of pypi info from
        `get_pypi_info`.
        Arguments:
            releases : A dict of release versions and info from
                       get_pypi_info(pkgname)['releases'].
    """
    if not releases:
        return 0
    return sum(
        verinfo.get('downloads', 0)
        for ver in releases
        for verinfo in releases[ver]
    )


def get_requirement_names(filename=DEFAULT_FILE):
    """ Return an iterable of requirement names from a requirements.txt. """
    reqs = Requirementz.from_file(filename=filename)
    return sorted(r.name for r in reqs)


def list_duplicates(filename=DEFAULT_FILE):
    """ Print any duplicate package names found in the file.
        Returns the number of duplicates found.
    """
    dupes = Requirementz.from_file(filename=filename).duplicates()
    dupelen = len(dupes)
    if not dupelen:
        print(C('No duplicate requirements found.', 'cyan'))
        return 0

    print(
        C(' ').join(
            C('Found', 'cyan'),
            colr_num(dupelen),
            C(
                '{} with duplicate entries:'.format(
                    'requirement' if dupelen == 1 else 'requirements',
                ),
                'cyan',
            )
        )
    )
    for req, dupcount in dupes.items():
        print('{name:>30} has {num} {plural}'.format(
            name=colr_name(req.name),
            num=colr_num(dupcount, style='bright'),
            plural='duplicate' if dupcount == 1 else 'duplicates'
        ))
    return sum(dupes.values())


def list_packages(location=False):
    """ List all installed packages. """
    # Sort by name first.
    pkgs = sorted(PKGS)
    if location:
        # Sort by location, but the name sort is kept.
        pkgs = sorted(pkgs, key=lambda p: PKGS[p].location)
    for pname in pkgs:
        p = PKGS[pname]
        print('{:<30} v. {:<12} {}'.format(
            colr_name(p.project_name),
            C(pkg_installed_version(pname), fore='cyan'),
            C(p.location, fore='green'),
        ))


def list_requirements(filename=DEFAULT_FILE, location=False):
    """ Lists current requirements. """
    reqs = Requirementz.from_file(filename=filename)
    print('\n'.join(
        reqs.iter_str(color=True, align=True, location=location)
    ))


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


def search_requirements(
        pattern, filename=DEFAULT_FILE, ignorecase=True):
    """ Search requirements lines for a text/regex pattern, and print
        results as they are found.
        Returns the number of results found.
    """
    reqs = Requirementz.from_file(filename=filename)
    try:
        found = Requirementz(
            requirements=reqs.search(pattern, ignorecase=ignorecase)
        )
    except re.error as ex:
        print_err('\nInvalid regex pattern', value=pattern, error=ex)
        return 1
    total = len(found)
    if not total:
        print_err('\nNo entries found with', value=pattern)
        return 1

    print('\n'.join(found.iter_str(color=True, align=True)))
    print(C(' ').join(
        C('\nFound', 'cyan'),
        colr_num(total, style='bright'),
        C('{}.'.format('entry' if total == 1 else 'entries'), 'cyan'),
    ))
    return 0


def show_package_info(packagename):
    """ Show local and pypi info for a package, by name.
        Returns 0 on success, 1 on failure.
    """
    try:
        pypiinfo = get_pypi_info(packagename)
    except (HTTPError, UnicodeDecodeError, ValueError) as ex:
        print_err(
            'Failed to get pypi info for',
            value=packagename,
            error=ex,
        )
        return 1
    info = pypiinfo.get('info', {})
    if not info:
        print_err('No info for package', value=packagename)
        return 1
    releases = pypiinfo.get('releases', [])
    otherreleasecnt = len(releases) - 1
    releasecntstr = ''
    if otherreleasecnt:
        releasecntstr = C('').join(
            C('+', 'yellow'),
            colr_num(otherreleasecnt, style='bright'),
            C(' releases', 'yellow')
        ).join('(', ')', stysle='bright')

    pkgstr = '\n'.join((
        '\n{name:<30} {ver:<10} {releasecnt}',
        '    {summary}',
    )).format(
        name=colr_name(info['name']),
        ver=C(info['version'], 'lightblue'),
        releasecnt=releasecntstr,
        summary=C(
            FormatBlock(info['summary'].strip()).format(
                width=76,
                newlines=True,
                prepend='    ',
                strip_first=True,
            ),
            'cyan'
        ),
    )
    label_color = 'blue'
    value_color = 'cyan'
    subvalue_color = 'lightcyan'
    authorstr = ''
    if info['author'] and info['author'] not in ('UNKNOWN', ):
        authorstr = C(': ').join(
            C('Author', label_color),
            C(info['author'], value_color)
        )
    emailstr = ''
    if info['author_email'] and info['author_email'] not in ('UNKNOWN', ):
        emailstr = C(
            info['author_email'],
            subvalue_color,
        ).join('<', '>', style='bright')

    if authorstr or emailstr:
        pkgstr = '\n'.join((
            pkgstr,
            '    {author}{email}'.format(
                author=authorstr,
                email=' {}'.format(emailstr) if authorstr else emailstr,
            )
        ))

    if info['home_page']:
        homepagestr = C(': ').join(
            C('Homepage', label_color),
            C(info['home_page'], value_color)
        )
        pkgstr = '\n'.join((
            pkgstr,
            '    {homepage}'.format(
                homepage=homepagestr,
            )
        ))
    latestrelease = max(releases, key=parse_version) if releases else None
    if latestrelease:
        try:
            latestdls = releases[latestrelease][0].get('downloads', 0)
        except IndexError:
            # Latest release has no info dict.
            latestdls = 0
        alldls = get_pypi_release_dls(releases)

        lateststr = C(' ').join(
            C(': ').join(
                C('Latest', label_color),
                C(latestrelease, value_color)
            ),
            C('').join(
                colr_num(latestdls),
                C(' dls', 'green'),
                ', ',
                colr_num(alldls),
                C(' for all versions', 'green'),
            ).join('(', ')'),
        )

        # Show the version that is isntalled, if any.
        installedver = pkg_installed_version(packagename)
        if installedver is None:
            installedstr = C('not installed', 'red').join('(', ')')
        elif installedver == latestrelease:
            installedstr = C('installed', 'green').join('(', ')')
        else:
            installedstr = C(': ').join(
                C('installed', label_color),
                C(installedver, value_color),
            ).join('(', ')')
        lateststr = C(' ').join(
            lateststr,
            installedstr,
        )
        pkgstr = '\n'.join((
            pkgstr,
            '    {latest}'.format(
                latest=lateststr,
            )
        ))
    print(pkgstr)
    return 0


def show_package_infos(packagenames):
    """ Show local and pypi info for a list of package names.
        Returns 0 on success, otherwise returns the number of errors.
    """
    if not packagenames:
        raise EmptyFile()
    return sum(show_package_info(name) for name in packagenames)


class UserCancelled(KeyboardInterrupt):
    def __init__(self, msg=None):
        self.msg = str(msg or 'User cancelled.')

    def __str__(self):
        return self.msg


if __name__ == '__main__':
    entry_point()
