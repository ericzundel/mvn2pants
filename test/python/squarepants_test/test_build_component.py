# Tests for code in squarepants/src/main/python/squarepants/build_component.py
#
# Run with:
# ./pants goal test squarepants/src/test/python/squarepants:build_component

from contextlib import contextmanager
import os
from textwrap import dedent
import unittest2 as unittest

from squarepants.build_component import JarFilesMixin
from squarepants_test.test_utils import temporary_dir, reset_caches

class BuildComponentTest(unittest.TestCase):

  def setUp(self):
    self.maxDiff = None
    self._wd = os.getcwd()
    reset_caches()

  def tearDown(self):
    # Restore the working directory
    os.chdir(self._wd)

  def test_format_jar_deps(self):
    # Dependencies should be sorted in alphabetical order
    self.assertEquals(dedent('''
                            jar_library(name='jar_files',
                              jars = [
                                'bar',
                                'baz',
                                'foo'
                              ],
                            )
                            '''),
                      JarFilesMixin.format_jar_library('jar_files', ["'foo'", "'bar'", "'baz'"]))
    # Duplicates should be suppressed
    self.assertEquals(dedent('''
                            jar_library(name='jar_files',
                              jars = [
                                'baz',
                                'foo'
                              ],
                            )
                            '''),
                      JarFilesMixin.format_jar_library('jar_files', ['foo', 'foo', 'baz']))
    # jar() entries shouldn't be quoted.
    self.assertEquals(dedent('''
                            jar_library(name='jar_files',
                              jars = [
                                'baz',
                                'foo',
                                jar(org='square', name='foobar')
                              ],
                            )
                            '''),
                      JarFilesMixin.format_jar_library('jar_files', ['foo', 'foo', 'baz',
                                                       "jar(org='square', name='foobar')"],))

