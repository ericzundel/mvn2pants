# Tests for code in squarepants/src/main/python/squarepants/binary_utils.py
#
# Run with:
# ./pants test squarepants/src/test/python/squarepants_test:binary_utils

import os
import unittest2 as unittest

from squarepants.binary_utils import BinaryUtils, Command, Git, PantsGit
from squarepants.file_utils import temporary_dir


class BinaryUtilsTest(unittest.TestCase):
  """BinaryUtils is actually fairly difficult to test.

  This is mostly because it's hard to safely test operations on git repos.
  """

  def test_squarepants_binary(self):
    with temporary_dir() as tempdir:
      self.assertEquals(os.path.join(tempdir, 'squarepants', 'bin', 'pants_release.sh'),
                        BinaryUtils.squarepants_binary('pants_release.sh', tempdir))

  def test_command(self):
    echo = Command('echo')
    self.assertEquals('test message', echo('test message').strip())
    self.assertTrue(echo('test message', pipe=False))
