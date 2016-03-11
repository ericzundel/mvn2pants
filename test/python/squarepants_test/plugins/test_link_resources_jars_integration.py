# Regression testing for the link_resources plugin

import os

from squarepants.file_utils import temporary_dir
from squarepants_test.integration_test_base import IntegrationTestBase


class LinkedResourcesIntegrationTest(IntegrationTestBase):
  """Integration tests for the linked_resources plugin."""

  def test_link_resources_jars(self):
    binary_run = self.pants('test', self._link_resources_jars_testdir)
    self.assert_success(binary_run)

  def test_link_resources_jars_binary(self):
    binary_spec = '{path}:{name}'.format(path=self._link_resources_jars_testdir, name='bin')
    with temporary_dir() as dist_dir:
      self.assert_success(self.pants('--pants-distdir={}'.format(dist_dir), 'binary', binary_spec))
      binary_jar = os.path.join(dist_dir, 'link-resources-jars.jar')
      java_result = self.java('-jar', binary_jar)
      self.assert_success(java_result)
      self.assertIn('Everything looks OK.', java_result)
      self.assertIn('xyzzy.jar', self.jar('-tf', binary_jar))

  @property
  def _link_resources_jars_testdir(self):
    return 'squarepants/src/test/java/com/squareup/squarepants/integration/linkresourcesjars'

