# General pants regression testing.

import os
import logging
import shutil
from contextlib import contextmanager
from zipfile import ZipFile

from squarepants.binary_utils import Command
from squarepants.file_utils import frozen_dir, temporary_dir
from squarepants.pom_to_build import PomToBuild

from squarepants_test.integration_test_base import IntegrationTestBase

class PantsIntegrationTest(IntegrationTestBase):
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

  @contextmanager
  def _rename_test_builds(self, path, test_build_name='TEST_BUILD'):
    build_name = 'BUILD'
    test_build_map = {}
    for (dirpath, dirnames, filenames) in os.walk(path):
      if test_build_name in filenames:
        test_build_map[os.path.join(dirpath, test_build_name)] = os.path.join(dirpath, build_name)
    for src, dst in test_build_map.items():
      os.rename(src, dst)
    try:
      yield
    finally:
      for src, dst in test_build_map.items():
        os.rename(dst, src)

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

  def test_export_squarepants(self):
    self.assert_success(self.pants('export', 'squarepants::'))

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

  def test_jax_ws_codegen(self):
    with temporary_dir() as distdir:
      binary_run = self.pants(
        '--pants-distdir={}'.format(distdir),
        'binary run',
        '--binary-jvm-no-use-nailgun',
        'squarepants/src/test/java/com/squareup/squarepants/integration/jaxwsgen'
      )
      self.assert_success(binary_run)
      binary = os.path.join(distdir, 'jaxwsgen.jar')
      self.assertTrue(os.path.exists(binary))

  def test_jooq_codegen(self):
    squarepants_java = 'squarepants/src/test/java'
    jooq_package = 'com.squareup.squarepants.integration.jooq'
    jooq_path = os.path.join(squarepants_java, jooq_package.replace('.', '/'))
    spot_check = ['{package}.{name}'.format(package=jooq_package, name=name)
                  for name in ('model.Tables', 'model.tables.People', 'model.tables.Places')]

    jooq_model_directory = os.path.join('squarepants', 'src', 'test', 'java', 'com', 'squareup',
                                        'squarepants', 'integration', 'jooq', 'model')
    shutil.rmtree(jooq_model_directory, ignore_errors=True)

    def check_classes(should_exist):
      for class_name in spot_check:
        path = '{}.java'.format(os.path.join(squarepants_java, class_name.replace('.', '/')))
        self.assertEquals(should_exist, os.path.exists(path))
      if not should_exist:
        # No need to spin up jvm just to check to see if classes *don't* exist.
        return
      run = self.pants('run', '{}:bin'.format(jooq_path))
      self.assert_success(run)
      existence = {}
      for line in run.split('\n'):
        if line and '\t' in line:
          key, val = line.split('\t')
          existence[key] = val
      for class_name in spot_check:
        self.assertEquals(existence[class_name], 'present')

    check_classes(False)

    with frozen_dir(jooq_path):
      # jOOQ is awkward because it generates code to the normal source folders, which is then
      # checked in. So we do this in a frozen_dir context to clean up after it.
      self.assert_success(self.pants('jooq', jooq_path))
      check_classes(True)

    check_classes(False)

  @contextmanager
  def _generated_module(self, module):
    with frozen_dir(module):
      with self._rename_test_builds(module):
        PomToBuild().convert_pom(os.path.join(module, 'pom.xml'))
        yield module

  def test_jooq_parse_pom_and_generate(self):
    with self._generated_module('squarepants/pants-test-app/jooq-integration') as module:
      self.assert_success(self.pants('jooq', '{}:jooq'.format(module)))
      self.assert_success(self.pants('run', '{}'.format(module)))

  def test_parse_and_generate_junit_extra_env_vars(self):
    with self._generated_module('squarepants/pants-test-app/env-vars') as module:
      self.assert_success(self.pants('test', '{}/src/test/java:test'.format(module)))

  def test_parse_and_generate_junit_extra_jvm_options(self):
    with self._generated_module('squarepants/pants-test-app/jvm-options') as module:
      self.assert_success(self.pants('test', '{}/src/test/java:test'.format(module)))

  def test_generate_and_use_build_symbols(self):
    with self._generated_module('squarepants/pants-test-app/build-symbols') as module:
      PomToBuild().convert_pom(os.path.join(module, 'pom.xml'))
      self.assert_success(self.pants('test', '{}/src/test/java:test'.format(module)))

  def test_generate_jar_with_excludes(self):
    with self._generated_module('squarepants/pants-test-app/jar-excludes') as module:
      contains_jar_files = False
      contains_hamcrest_exclude = False
      with open(os.path.join(module, 'src', 'main', 'java', 'BUILD.gen')) as f:
        lines = f.readlines()
        for line in lines:
          if "jar_library(name='jar_files'," in line:
            contains_jar_files = True
          elif "exclude(org='org.hamcrest', name='hamcrest-core')" in line:
            contains_hamcrest_exclude = True
      self.assertTrue(contains_jar_files and contains_hamcrest_exclude,
                      'Missing expected jar library with excludes!\n\n{}\n'.format(''.join(lines)))

  def test_protobuf_publishing(self):
    with temporary_dir() as tmpdir:
      test_spec = 'service/exemplar-db/src/main/proto'
      command = [
        'publish.jar',
        '--no-dryrun',
        '--no-commit',
        '--no-prompt',
        '--no-transitive',
        '--local={}'.format(tmpdir),
        '--doc-javadoc-ignore-failure',
        test_spec,
      ]
      run = self.pants(*command)
      self.assert_success(run)

      def find_published_jar():
        for root, dirs, files in os.walk(tmpdir):
          for name in files:
            if name.endswith('SNAPSHOT.jar'):
              return os.path.join(root, name)

      jar_path = find_published_jar()
      self.assertFalse(jar_path is None)
      with ZipFile(jar_path, 'r') as jar:
        contents = jar.namelist()
        self.assertTrue(any(name.endswith('.proto') for name in contents))
        self.assertTrue(any(name.endswith('.class') for name in contents))
        self.assertFalse(any(name.endswith('.java') for name in contents))
