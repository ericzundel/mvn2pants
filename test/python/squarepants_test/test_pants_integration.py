# General pants regression testing.

import os
import logging
import unittest2 as unittest
from contextlib import contextmanager
from zipfile import ZipFile

from squarepants.binary_utils import Command
from squarepants.file_utils import temporary_dir


class PantsIntegrationTest(unittest.TestCase):
  """Guard against regressions with some (hopefully time-inexpensive) regressions test."""

  def setUp(self):
    logging.getLogger('squarepants').addHandler(logging.StreamHandler())
    env = os.environ.copy()
    env['REGENERATE_BUILD'] = 'no'
    self.pants = Command(name='./pants', args=['./pants', '--no-lock', '--print-exception-stacktrace'], env=env)
    self.java = Command(name='java')
    self.jar = Command(name='jar')
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

  def test_copy_signed_jars(self):
    os.system('rm -rf dist/copy-signed-jars-test*')
    binary_run = self.pants('binary squarepants/src/test/java/com/squareup/squarepants/integration/copysignedjars:copy-signed-jars-test')
    self.assert_success(binary_run)
    os.chdir('./dist')
    run = Command(name='java', args=['java', '-jar', 'copy-signed-jars-test.jar'])()
    self.assertIn('The answer is: 42', run)

  def test_square_depmap(self):
    binary_run = self.pants('--sq-depmap-no-run-dot',
                            '--no-sq-depmap-reduce-transitive', 'sq-depmap', 'squarepants::')
    self.assert_success(binary_run)

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

  def test_export_squarepants(self):
    self.assert_success(self.pants('export', 'squarepants::'))

  @contextmanager
  def _invariant_file_contents(self, path):
    """Ensures that the contents of the file are unchanged after the contextmanager exits.

    Reads the file contents before yielding, then writes back the file contents after.
    :param string path: The path to the text file to keep invariant.
    """
    with open(path, 'r') as f:
      contents = f.read()
    try:
      yield contents
    finally:
      with open(path, 'w+') as f:
        f.write(contents)

  def test_app_manifest_bundle(self):
    """Makes sure the app-manifest.yaml properly makes it into the jar file on a ./pants binary.

    In particular, makes sure that the app-manifest.yaml is kept up to date and does not get stale,
    even if it is the only file that has changed since the last time ./pants binary was invoked.
    """
    with temporary_dir() as distdir:
      source_yaml_file = 'squarepants/pants-aop-test-app/app-manifest.yaml'
      with self._invariant_file_contents(source_yaml_file) as plain_app_manifest:
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

  @property
  def _link_resources_jars_testdir(self):
    return 'squarepants/src/test/java/com/squareup/squarepants/integration/linkresourcesjars'

  def test_jar_manifest(self):
    with temporary_dir() as distdir:
      def do_test():
        binary_run = self.pants('--pants-distdir={}'.format(distdir),
                                  'binary', '--binary-jvm-no-use-nailgun',
                                  'squarepants/src/test/java/com/squareup/squarepants/integration/manifest:manifest-test')
        self.assert_success(binary_run)
        binary = os.path.join(distdir, 'manifest-test.jar')
        self.assertTrue(os.path.exists(binary))
        with ZipFile(binary, 'r') as zf:
          with zf.open('META-INF/jar-manifest.txt') as f:
            self.assertIn('com.google.guava:guava:', f.read())

      do_test()
      # Make sure it works a second time
      do_test()
