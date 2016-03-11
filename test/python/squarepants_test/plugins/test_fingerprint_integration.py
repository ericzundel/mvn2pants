# Regression testing for the link_resources plugin

import os

from zipfile import ZipFile

from squarepants.file_utils import temporary_dir
from squarepants_test.integration_test_base import IntegrationTestBase


class FingerprintIntegrationTest(IntegrationTestBase):
  """Integration tests for the fingerprint plugin."""

  def test_app_manifest_bundle(self):
    """Makes sure the app-manifest.yaml properly makes it into the jar file on a ./pants binary.

    In particular, makes sure that the app-manifest.yaml is kept up to date and does not get stale,
    even if it is the only file that has changed since the last time ./pants binary was invoked.
    """
    with temporary_dir() as distdir:
      source_yaml_file = 'squarepants/pants-aop-test-app/app-manifest.yaml'
      with self.invariant_file_contents(source_yaml_file) as plain_app_manifest:
        self.assertNotIn('bogus_flag: "bogus one"', plain_app_manifest)

        with open(source_yaml_file, 'a') as f:
          f.write('\nbogus_flag: "bogus one"\n')

        self.assert_success(self.pants('--pants-distdir={}'.format(distdir),
                                       'binary', '--binary-jvm-no-use-nailgun',
                                       'squarepants/pants-aop-test-app'))

        binary = os.path.join(distdir, 'pants-aop-test-app.jar')
        self.assertTrue(os.path.exists(binary))
        with ZipFile(binary, 'r') as zf:
          with zf.open('app-manifest.yaml') as f:
            self.assertIn('bogus_flag: bogus one', f.read())

        with open(source_yaml_file, 'w') as f:
          f.write(plain_app_manifest)

        self.assert_success(self.pants('--pants-distdir={}'.format(distdir),
                                       'binary', '--binary-jvm-no-use-nailgun',
                                       'squarepants/pants-aop-test-app',
                                       ))

        binary = os.path.join(distdir, 'pants-aop-test-app.jar')
        self.assertTrue(os.path.exists(binary))
        with ZipFile(binary, 'r') as zf:
          with zf.open('app-manifest.yaml') as f:
            self.assertNotIn('bogus_flag: bogus one', f.read())
