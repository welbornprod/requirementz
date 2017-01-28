#!/usr/bin/env python3
# -*- coding: utf-8 -*-

""" test_requirementz.py
    Unit tests for requirementz.py v. 0.0.1

    -Christopher Welborn 07-20-2015
"""

import os
import sys
import unittest
from urllib.error import HTTPError
from urllib.request import urlopen

from requirementz import (
    RequirementPlus,
    Requirementz,
    StatusLine,
    sort_requirements,
)
compare_versions = RequirementPlus.compare_versions


TEST_LINES = (
    # test_StatusLine_with_latest() depends on this colr line,
    # index doesn't matter.
    'colr >= 0.5.2',
    # test_search() depends on this docopt line,
    # index doesn't matter.
    'docopt >= 0.6.2',
    'requirements-parser >= 0.1.0'
)

TEST_FILE = 'test_requirements.txt'

HAS_CONNECTION = False
CONNECTION_SITES = ('https://welbornprod.com', 'https://google.com')
for url in CONNECTION_SITES:
    try:
        # Try connecting to a site, to test internet connection.
        con = urlopen(url)
    except HTTPError:
        pass
    else:
        HAS_CONNECTION = True
        break
    finally:
        con.close()


class RequirementzTests(unittest.TestCase):

    def tearDown(self):
        if os.path.exists(TEST_FILE):
            os.remove(TEST_FILE)

    def test_add_replace(self):
        """ Requirementz.add_line() works for existing entries """
        reqs = Requirementz.from_lines(TEST_LINES)
        reqs.add_line('docopt >= 0.6.1')
        self.assertTrue(
            len(reqs) == len(TEST_LINES),
            msg='Existing requirement not replaced.'
        )
        r = reqs.get_byname('docopt')
        self.assertIn(
            ('>=', '0.6.1'),
            r.specs,
            msg='Existing requirement not replaced.'
        )

    def test_add_new(self):
        """ Requirementz.add_line() works for new entries """
        reqs = Requirementz.from_lines(TEST_LINES)
        reqs.add_line('six >= 0.0.1')
        self.assertTrue(
            len(reqs) == len(TEST_LINES) + 1,
            msg='New requirement not added.'
        )
        self.assertIn(
            'six',
            reqs.names(),
            msg='New requirement not added.'
        )

    def test_compare_versions(self):
        """ RequirementPlus.compare_versions() works """
        self.assertTrue(compare_versions('1.0.01', '>', '1.0.0'))
        self.assertTrue(compare_versions('1.0.01', '<', '1.0.02'))
        self.assertTrue(compare_versions('1.0.0', '>=', '1.0.0'))
        self.assertTrue(compare_versions('1.0.01', '>=', '1.0.0'))
        self.assertTrue(compare_versions('1.0.0', '<=', '1.0.01'))
        self.assertTrue(compare_versions('1.0.0', '<=', '1.0.0'))
        self.assertTrue(compare_versions('1.0.0', '==', '1.0.0'))
        self.assertTrue(compare_versions('1', '==', '1.0.0'))
        self.assertTrue(compare_versions('0.1', '==', '0.1.0'))
        # Unknown comparison operators default to '>='
        self.assertTrue(compare_versions('2', 'WAT', '1'))
        self.assertTrue(compare_versions('1', None, '1'))

    def test_duplicates(self):
        """ Requirementz.duplicates() catches duplicate entries """
        dupereqs = (
                RequirementPlus.parse_line('docopt >= 0.6.2'),
                RequirementPlus.parse_line('docopt <= 7.0.0'),
                RequirementPlus.parse_line('six > 0'),
                RequirementPlus.parse_line('six >= 1.0.0'),
                RequirementPlus.parse_line('six >= 5.1.6'),
                # Not returned at all, no dupes.
                RequirementPlus.parse_line('lone == 1.0.0'),
        )
        reqs = Requirementz.from_lines(str(r) for r in dupereqs)
        dupesbyname = {r.name: num for r, num in reqs.duplicates().items()}
        self.assertDictEqual(
            dupesbyname,
            {
                'docopt': 1,
                'six': 2
            }
        )

    def test_init(self):
        """ Requirementz.init() from file works """
        reqs = Requirementz.from_lines(TEST_LINES)
        reqs.write(TEST_FILE)
        Requirementz.from_file(TEST_FILE)

    def test_init_lines(self):
        """ Requirementz.init() from lines works """
        Requirementz.from_lines(TEST_LINES)

    def test_search(self):
        """ Requirementz.search() finds existing requirements """
        reqs = Requirementz.from_lines(TEST_LINES)
        for i, knownline in enumerate(TEST_LINES):
            if 'docopt' in knownline:
                known_index = i
                break
        else:
            self.fail('Bad test, failed to find known test requirement.')
        found = tuple(reqs.search('docopt'))
        self.assertTrue(
            len(found) == 1,
            msg='Failed to find requirement.'
        )
        self.assertEqual(
            reqs[known_index],
            found[0],
            msg='Failed to find correct requirement.'
        )
        found = tuple(reqs.search('DoCoPt', ignorecase=True))
        self.assertTrue(
            len(found) == 1,
            msg='Failed to find case-insensitive requirement.'
        )
        self.assertEqual(
            reqs[known_index],
            found[0],
            msg='Failed to find correct case-insensitive requirement.'
        )
        found = tuple(reqs.search('0.6.2'))
        self.assertTrue(
            len(found) == 1,
            msg='Failed to find requirement by version.'
        )
        self.assertEqual(
            reqs[known_index],
            found[0],
            msg='Failed to find correct requirement by version.'
        )
        found = tuple(reqs.search('>= 0.6.2'))
        self.assertTrue(
            len(found) == 1,
            msg='Failed to find requirement.'
        )
        self.assertEqual(
            reqs[known_index],
            found[0],
            msg='Failed to find requirement by spec.'
        )
        notfound = tuple(reqs.search('THIS_DOES_NOT_EXIST'))
        self.assertTrue(len(notfound) == 0, msg='Returned false requirement.')

    def test_sort_requirements(self):
        """ sort_requirements() reads, sorts, and writes """
        unsorted_lines = (
            'six >= 0.1.1',
            'anti-gravity > 0',
            'docopt >= 0.6.2',
            'colr >= 0.2.5'
        )
        sorted_lines = sorted(unsorted_lines)
        with open(TEST_FILE, 'w') as f:
            f.write('\n'.join(unsorted_lines))
        sort_requirements(filename=TEST_FILE)
        with open(TEST_FILE, 'r') as f:
            wrotelines = [l.strip() for l in f.readlines() if l.strip()]
        self.assertListEqual(
            wrotelines,
            sorted_lines,
            msg='Sorting failed.'
        )

    def test_write(self):
        """ Requirementz.write() to file works """
        reqs = Requirementz.from_lines(TEST_LINES)
        reqs.write(filename=TEST_FILE)


class StatusLineTests(unittest.TestCase):
    def test_StatusLine(self):
        """ init() from requirement works """
        reqs = Requirementz.from_lines(TEST_LINES)
        [StatusLine(r) for r in reqs]

    @unittest.skipUnless(HAS_CONNECTION, 'Unreliable i-net connection.')
    def test_StatusLine_with_latest(self):
        """ StatusLine.with_latest should retrieve pypi info. """

        # Ensure no pypi errors for known package name.
        name = 'colr'
        req = RequirementPlus.parse(name)
        try:
            StatusLine(req).with_latest()
        except (HTTPError, UnicodeDecodeError, ValueError) as ex:
            self.fail(
                ' '.join((
                    'Failed to retrieve info for known package:',
                    '{}\n{}'
                )).format(name, ex)
            )
        # Ensure failure for obviously bad package.
        name = 'THERE_IS_NO_PACKAGE_WITH_THIS_NAME'
        req = RequirementPlus.parse(name)
        try:
            StatusLine(req).with_latest()
        except HTTPError as ex:
            if ex.code == 404:
                # This is what we expected.
                return
            else:
                self.fail(
                    'PyPi returned unexpected error number: {}\n{}'.format(
                        ex.errno,
                        ex
                    )
                )
        else:
            self.fail(
                'Should have failed for bad package name: {}'.format(name)
            )


if __name__ == '__main__':
    sys.exit(unittest.main(argv=sys.argv))
