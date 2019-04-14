#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Requirementz Setup

-Christopher Welborn 03-05-2017
"""

try:
    from setuptools import setup
except ImportError:
    from distutils.core import setup

# Try using the latest DESC.txt.
shortdesc = ' '.join((
    'Checks requirements against installed versions,',
    'and other requirements.txt tools.'
))
try:
    with open('DESC.txt', 'r') as f:
        shortdesc = f.read()
except FileNotFoundError:
    pass

# Default README files to use for the longdesc, if pypandoc fails.
readmefiles = ('docs/README.txt', 'README.txt', 'docs/README.rst')
for readmefile in readmefiles:
    try:
        with open(readmefile, 'r') as f:
            longdesc = f.read()
        break
    except EnvironmentError:
        # File not found or failed to read.
        pass
else:
    # No readme file found.
    # If a README.md exists, and pypandoc is installed, generate a new readme.
    try:
        import pypandoc
    except ImportError:
        print('Pypandoc not installed, using default description.')
        longdesc = shortdesc
    else:
        # Convert using pypandoc.
        try:
            longdesc = pypandoc.convert('README.md', 'rst')
        except EnvironmentError:
            # No readme file, no fresh conversion.
            print('Pypandoc readme conversion failed, using default desc.')
            longdesc = shortdesc

setup(
    name='Requirementz',
    version='0.3.4',
    author='Christopher Welborn',
    author_email='cj@welbornprod.com',
    packages=['requirementz'],
    url='https://github.com/welbornprod/requirementz',
    description=shortdesc,
    long_description=longdesc,
    keywords=('python module library 3 pip requirements requirements.txt'),
    classifiers=[
        'License :: OSI Approved :: MIT License',
        'Operating System :: Microsoft :: Windows',
        'Operating System :: POSIX :: Linux',
        'Programming Language :: Python',
        'Programming Language :: Python :: 3 :: Only',
        'Topic :: Software Development :: Libraries',
        'Topic :: Software Development :: Libraries :: Python Modules',
    ],
    install_requires=[
        'colr >= 0.7.6',
        'docopt >= 0.6.2',
        'formatblock >= 0.3.6',
        'printdebug >= 0.3.0',
        'requirements-parser >= 0.1.0',
    ],
    entry_points={
        'console_scripts': [
            'requirementz = requirementz.__main__:entry_point',
        ]
    }

)
