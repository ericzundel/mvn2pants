# General pants regression testing.

import os
import unittest2 as unittest

from squarepants.binary_utils import Command


class PantsIntegrationTest(unittest.TestCase):
  """Guard against regressions with some (hopefully time-inexpensive) regressions test."""

  def setUp(self):
    env = os.environ.copy()
    env['REGENERATE_BUILD'] = 'no'
    self.pants = Command(name='./pants', args=['./pants', '--no-lock'], env=env)
    self._original_wd = os.getcwd()

  def tearDown(self):
    os.chdir(self._original_wd)

  def assert_success(self, pants_run):
    self.assertTrue(pants_run)

  def test_pants_targets(self):
    run = self.pants('targets')
    self.assert_success(run)
    # Spot check a couple build aliases.
    self.assertIn('java_library:', run)
    self.assertIn('square_maven_layout:', run)

  def test_copy_signed_jars(self):
    os.system('rm -rf dist/copy-signed-jars-test*')
    binary_run = self.pants('binary squarepants/src/test/java/com/squareup/squarepants/integration/copysignedjars:copy-signed-jars-test')
    self.assert_success(binary_run)
    os.chdir('./dist')
    run = Command(name='java', args=['java', '-jar', 'copy-signed-jars-test.jar'])()
    self.assertIn('The answer is: 42', run)

