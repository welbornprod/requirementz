# Requirementz

* Checks `requirements.txt` against installed packages, or latest versions available on PyPi.

* Shows latest package information from PyPi (for `requirements.txt` or any package).

* Searches `requirements.txt` for text/regex patterns.

* Sorts `requirements.txt` lines in place.

* Finds duplicate entries in `requirements.txt`.

## Installation

This tool is installable with `pip`:
```bash
pip install requirementz
```

The command is called `requirementz`.

## Dependencies

Requirementz has several python dependencies, all installable with `pip`.
A `requirements.txt` is provided, for easy installation.

* [colr](https://github.com/welbornprod/colr) - Terminal colors.
* [docopt](https://github.com/docopt/docopt) - Argument parsing.
* [formatblock](https://github.com/welbornprod/fmtblock) - Text wrapping (like `textwrap`).
* [printdebug](https://github.com/welbornprod/printdebug) - Easily disabled debug printing.
* [requirements-parser](https://github.com/davidfischer/requirements-parser) - Parses `requirements.txt`.

If you've cloned the repo, you can run `pip install -r requirements.txt` to install all of them. Otherwise, `pip install requirementz`
should install all dependencies for you.

## Usage

```
Usage:
    requirementz (-h | -v) [-D] [-n]
    requirementz [-c | -C] [-e] [-L | -r] [-f file] [-D] [-n]
    requirementz [-a line... | -d]        [-f file] [-D] [-n]
    requirementz -l [-L | -r]             [-f file] [-D] [-n]
    requirementz (-P | -S)                [-f file] [-D] [-n]
    requirementz -p [-L]                            [-D] [-n]
    requirementz -s pat [-i]              [-f file] [-D] [-n]
    requirementz PACKAGE...                         [-D] [-n]

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

```

## Examples

### Check (installed packages)

Check `requirements.txt` against installed package versions.
```bash
requirementz
```

Here you can see that the `colr >= 0.7.6` requirement was not satisfied, because `0.7.5` is installed:

![Output](http://imgur.com/nbzLv7X.png)

Show package location while checking:
```bash
requirementz -L
```

![Output](http://imgur.com/szaquw9.png)

### Check (latest pypi version)

Check `requirements.txt` against installed package versions, and the latest
pypi version.
```bash
requirementz -C
```

![Output](http://imgur.com/FEiyEgU.png)

Show package location while checking:
```bash
requirementz -C -L
```

![Output](http://imgur.com/h7TgJ0u.png)

### Show pypi info for packages.

`-P` will show pypi information for all packages in `requirements.txt`:
```bash
requirementz -P
```

![Output](http://imgur.com/nxjGyK7.png)

You can do this for any package, whether it's installed or not:
```bash
requirementz antigravity
```

![Output](http://imgur.com/hFXbf8C.png)

You can use more than one package name.

### Find duplicate requirements

Any duplicate entries will be listed by name, with a count of duplicates.
```bash
requirementz -d
```

## Notes

This hasn't been tested very well with CVS or local requirements. Any help in
that area would be appreciated, as I haven't had to use those requirement types.

## Contributions

File an issue or create a pull request. Contributions are welcome.

https://github.com/welbornprod/requirementz
