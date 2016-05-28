#!/usr/bin/env python3
# -*- coding: utf-8 -*-

""" test_requirementz.py
    Unit tests for requirementz.py v. 0.0.1

    -Christopher Welborn 07-20-2015
"""

import sys
import unittest
from requirementz import compare_versions

# Not many tests here yet.


class RequirementzTests(unittest.TestCase):

    def test_version_comparison(self):
        """ compare_versions() works """
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

if __name__ == '__main__':
    sys.exit(unittest.main(argv=sys.argv))
