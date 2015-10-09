# Tests for code in squarepants/src/main/python/squarepants/file_utils.py
#
# Run with:
# ./pants test squarepants/src/test/python/squarepants_test:file_utils

import os
import re
import unittest2 as unittest

from squarepants.file_utils import file_pattern_exists_in_subdir, temporary_dir, touch

class PomToBuildTest(unittest.TestCase):

  def test_file_pattern_exists_in_subdir(self):
    pattern = re.compile(r'.*Test.java')
    with temporary_dir() as tmpdir:
      self.assertFalse(file_pattern_exists_in_subdir(tmpdir, pattern))
      touch(os.path.join(tmpdir, 'foo.java'))
      self.assertFalse(file_pattern_exists_in_subdir(tmpdir, pattern))
      touch(os.path.join(tmpdir, 'ExampleTest.java'))
      self.assertTrue(file_pattern_exists_in_subdir(tmpdir, pattern))

    with temporary_dir() as tmpdir:
      nested_dir = os.path.join(tmpdir, 'src', 'main', 'java', 'com', 'squareup', 'foo')
      os.makedirs(nested_dir)
      self.assertFalse(file_pattern_exists_in_subdir(tmpdir, pattern))
      touch(os.path.join(tmpdir, 'bogus.java'))
      touch(os.path.join(nested_dir, 'bogus.java'))
      touch(os.path.join(nested_dir, 'AnotherTest.java'))
      self.assertTrue(file_pattern_exists_in_subdir(tmpdir, pattern))
