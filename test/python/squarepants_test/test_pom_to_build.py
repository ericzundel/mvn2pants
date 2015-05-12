# Tests for code in squarepants/src/main/python/squarepants/pom_to_build.py
#
# Run with:
# ./pants goal test squarepants/src/test/python/squarepants:pom_to_build

from contextlib import contextmanager
import os
from textwrap import dedent
import unittest2 as unittest

from squarepants.pom_to_build import (PomToBuild, is_aux, infer_target_name, infer_build_name,
                                      write_build_file)
from squarepants_test.test_utils import temporary_dir, reset_caches


class PomToBuildTest(unittest.TestCase):

  def setUp(self):
    self.maxDiff = None
    self._wd = os.getcwd()
    reset_caches()

  def tearDown(self):
    # Restore the working directory
    os.chdir(self._wd)

  def assert_file_contents(self, filename, expected_contents):
    self.assertTrue(os.path.exists(filename))
    with open(filename, 'r') as f:
      contents = f.read()
    self.assertEquals(expected_contents, contents)

  def make_file(self, filename, contents):
    with open(filename, 'w') as f:
      f.write(contents)

  def test_write_build_gen(self):
    with temporary_dir() as build_dir:
      self.assertFalse(is_aux(build_dir))
      self.assertEquals('foo', infer_target_name(build_dir, 'foo'))
      self.assertEquals(os.path.join(build_dir, 'BUILD.gen'), infer_build_name(build_dir))
      write_build_file(build_dir, 'contents of BUILD.gen')
      self.assertTrue(os.path.exists(os.path.join(build_dir, 'BUILD.gen')))
      with open(os.path.join(build_dir, 'BUILD.gen')) as build_file:
        self.assertEquals('contents of BUILD.gen', build_file.read())

  def test_write_build_aux(self):
    with temporary_dir() as build_dir:
      with open(os.path.join(build_dir, 'BUILD'), 'w'):
        self.assertTrue(is_aux(build_dir))
        self.assertEquals('aux-foo', infer_target_name(build_dir, 'foo'))
        self.assertEquals(os.path.join(build_dir, 'BUILD.aux'), infer_build_name(build_dir))
        write_build_file(build_dir, 'contents of BUILD.aux')
        self.assertTrue(os.path.exists(os.path.join(build_dir, 'BUILD.aux')))
        with open(os.path.join(build_dir, 'BUILD.aux')) as build_file:
          self.assertEquals('contents of BUILD.aux', build_file.read())

  def test_format_jar_deps(self):
    pom_to_build = PomToBuild()
    with temporary_dir() as build_dir:
      # Dependencies should be sorted in alphabetical order
      self.assertEquals('''
jar_library(name='jar_files',
  jars = [
    'bar',
    'baz',
    'foo'
  ],
)
''', pom_to_build.format_jar_deps(["'foo'", "'bar'", "'baz'"], build_dir))
      # Duplicates should be suppressed
      self.assertEquals('''
jar_library(name='jar_files',
  jars = [
    baz,
    foo
  ],
)
''', pom_to_build.format_jar_deps(['foo', 'foo', 'baz'], build_dir))


  @contextmanager
  def setup_two_child_poms(self):
    with temporary_dir() as tmpdir:
      os.chdir(tmpdir)

      with open(os.path.join('pom.xml') , 'w') as pomfile:
        pomfile.write(dedent('''<?xml version="1.0" encoding="UTF-8"?>
                <project>

                  <groupId>com.example</groupId>
                  <artifactId>parent</artifactId>
                  <version>HEAD-SNAPSHOT</version>

                  <modules>
                    <module>child1</module>
                    <module>child2</module>
                  </modules>
                </project>
              '''))

      os.makedirs(os.path.join('parents', 'base'))
      with open(os.path.join('parents', 'base', 'pom.xml'), 'w') as base_pom:
        base_pom.write(dedent('''<?xml version="1.0" encoding="UTF-8"?>
                <project>

                  <groupId>com.example</groupId>
                  <artifactId>child1</artifactId>
                  <version>HEAD-SNAPSHOT</version>

                  <dependencyManagement>
                  </dependencyManagement>
                </project>'''))

      child1_path_name =  'child1'
      # Make some empty directories to hold BUILD.gen files
      os.makedirs(os.path.join(child1_path_name, 'src', 'main', 'java'))
      os.makedirs(os.path.join(child1_path_name, 'src', 'main', 'proto'))
      os.makedirs(os.path.join(child1_path_name, 'src', 'main', 'resources'))
      os.makedirs(os.path.join(child1_path_name, 'src', 'test', 'java'))
      os.makedirs(os.path.join(child1_path_name, 'src', 'test', 'proto'))
      os.makedirs(os.path.join(child1_path_name, 'src', 'test', 'resources'))
      child1_pom_name = os.path.join(child1_path_name, 'pom.xml')
      with open(child1_pom_name, 'w') as child1_pomfile:
        child1_pomfile.write(dedent('''<?xml version="1.0" encoding="UTF-8"?>
                <project>

                  <groupId>com.example</groupId>
                  <artifactId>child1</artifactId>
                  <version>HEAD-SNAPSHOT</version>

                  <dependencies>
                    <dependency>
                      <groupId>com.example</groupId>
                      <artifactId>child2</artifactId>
                      <version>HEAD-SNAPSHOT</version>
                    </dependency>
                  </dependencies>
                </project>
              '''))
      child2_path_name = os.path.join('child2')
      os.makedirs(os.path.join(child2_path_name, 'src', 'main', 'java'))
      os.makedirs(os.path.join(child2_path_name, 'src', 'main', 'proto'))
      os.makedirs(os.path.join(child2_path_name, 'src', 'main', 'resources'))
      os.makedirs(os.path.join(child2_path_name, 'src', 'test', 'java'))
      os.makedirs(os.path.join(child2_path_name, 'src', 'test', 'proto'))
      os.makedirs(os.path.join(child2_path_name, 'src', 'test', 'resources'))
      child2_pom_name = os.path.join(child2_path_name, 'pom.xml')
      with open(child2_pom_name, 'w') as child2_pomfile:
        child2_pomfile.write(dedent('''<?xml version="1.0" encoding="UTF-8"?>
                <project>

                  <groupId>com.example</groupId>
                  <artifactId>child2</artifactId>
                  <version>HEAD-SNAPSHOT</version>
                  <dependencies>
                  </dependencies>
                </project>
              '''))
      yield tmpdir


  def test_ignore_empty_dirs_in_self(self):
    with self.setup_two_child_poms() as tmpdir:
      PomToBuild().convert_pom('child1/pom.xml', print_headers=False)

      # Since all the dirs are empty, we should only have a project level pom file,
      # the others should be blank
      self.assert_file_contents('child1/BUILD.gen', """target(name='lib')""")

      self.assertEquals([], os.listdir('child1/src/main/java'))
      self.assertEquals([], os.listdir('child1/src/main/proto'))
      self.assertEquals([], os.listdir('child1/src/main/resources'))
      self.assertEquals([], os.listdir('child1/src/test/java'))
      self.assertEquals([], os.listdir('child1/src/test/proto'))
      self.assertEquals([], os.listdir('child1/src/test/resources'))


  def test_ignore_empty_dirs_in_dep(self):
    with self.setup_two_child_poms() as tmpdir:
      # Create some sources in child1 to create more BUILD.gen files
      self.make_file('child1/src/main/java/Foo.java', 'class Foo { }')
      self.make_file('child1/src/main/proto/foo.proto', 'message Foo_Message {}')
      self.make_file('child1/src/main/resources/foo.txt', "Foo bar baz.")
      self.make_file('child1/src/test/java/FooTest.java', 'class FooTest { }')
      self.make_file('child1/src/test/proto/foo_test.proto', 'message FooTest_Message {}')
      self.make_file('child1/src/test/resources/foo_test.txt', "Testing: Foo bar baz.")
      PomToBuild().convert_pom('child1/pom.xml', rootdir=tmpdir, print_headers=False)

      self.assert_file_contents('child1/BUILD.gen', """
target(name='proto',
  dependencies = [
    'child1/src/main/proto:proto'
  ],
)

target(name='lib',
  dependencies = [
    'child1/src/main/java:lib'
  ],
)

target(name='test',
  dependencies = [
    'child1/src/test/java:test'
  ],
)
""")

      # There should be no references to child2 in the BUILD files under src/main
      # because the directories under child2 are empty
      self.assert_file_contents('child1/src/main/java/BUILD.gen', """
java_library(name='lib',
  sources = rglobs('*.java'),
  resources = [
    'child1/src/main/resources:resources'
  ],
  dependencies = [
    'child1/src/main/proto:proto'
  ],
  provides = artifact(org='com.example',
                      name='child1',
                      repo=square,),  # see squarepants/plugin/repo/register.py
)
""")
      self.assert_file_contents('child1/src/main/proto/BUILD.gen', """
java_protobuf_library(name='proto',
  sources = rglobs('*.proto'),
  imports = [],
  dependencies = [],
)
""")
      self.assert_file_contents('child1/src/main/resources/BUILD.gen', """
resources(name='resources',
  sources = rglobs('*', exclude=[globs('BUILD*')]),
  dependencies = [],
)
""")

      # TODO(Eric Ayers) The provides statement in src/test/java is the same as in lib.  This probably
      # shouldn't be duplicated like this!
      self.assert_file_contents('child1/src/test/java/BUILD.gen', """
junit_tests(name='test',
   # TODO: Ideally, sources between :test and :lib should not intersect
  sources = rglobs('*.java'),
  dependencies = [
    ':lib',
  ],
)

java_library(name='lib',
  sources = rglobs('*.java'),
  resources = [
    'child1/src/test/resources:resources'
  ],
  dependencies = [
    'child1/src/main/java:lib',
    'child1/src/main/proto:proto',
    'child1/src/test/proto:proto',
    'testing-support/src/main/java:lib'
  ],
  provides = artifact(org='com.example',
                      name='child1',
                      repo=square,),  # see squarepants/plugin/repo/register.py
)
""")
      self.assert_file_contents('child1/src/test/proto/BUILD.gen', """
java_protobuf_library(name='proto',
  sources = rglobs('*.proto'),
  imports = [],
  dependencies = [
    'child1/src/main/proto:proto'
  ],
)
""")
      self.assert_file_contents('child1/src/test/resources/BUILD.gen', """
resources(name='resources',
  sources = rglobs('*', exclude=[globs('BUILD*')]),
  dependencies = [],
)
""")


  def test_nonempty_self_and_dep(self):
    with self.setup_two_child_poms() as tmpdir:
      # Create some sources in child1 and child2 so we get BUILD.gen files in both.
      self.make_file('child1/src/main/java/Foo.java', 'class Foo { }')
      self.make_file('child1/src/main/proto/foo.proto', 'message Foo_Message {}')
      self.make_file('child1/src/main/resources/foo.txt', "Foo bar baz.")
      self.make_file('child1/src/test/java/FooTest.java', 'class FooTest { }')
      self.make_file('child1/src/test/proto/foo_test.proto', 'message FooTest_Message {}')
      self.make_file('child1/src/test/resources/foo_test.txt', "Testing: Foo bar baz.")
      self.make_file('child2/src/main/java/Bar.java', "class Bar { }")
      self.make_file('child2/src/main/proto/bar.proto', "message Bar_Message {}")
      self.make_file('child2/src/main/resources/bar.txt', "Foo bar baz.")
      self.make_file('child2/src/test/java/BarTest.java', 'class BarTest { }')
      self.make_file('child2/src/test/proto/bar_test.proto', 'message BarTest_Message {}')
      self.make_file('child2/src/test/resources/bar_test.txt', "Testing: Foo bar baz.")
      PomToBuild().convert_pom('child1/pom.xml', rootdir=tmpdir, print_headers=False)
      self.assert_file_contents('child1/BUILD.gen', """
target(name='proto',
  dependencies = [
    'child1/src/main/proto:proto'
  ],
)

target(name='lib',
  dependencies = [
    'child1/src/main/java:lib'
  ],
)

target(name='test',
  dependencies = [
    'child1/src/test/java:test'
  ],
)
""")
      self.assert_file_contents('child1/src/main/java/BUILD.gen', """
java_library(name='lib',
  sources = rglobs('*.java'),
  resources = [
    'child1/src/main/resources:resources'
  ],
  dependencies = [
    'child1/src/main/proto:proto',
    'child2/src/main/java:lib'
  ],
  provides = artifact(org='com.example',
                      name='child1',
                      repo=square,),  # see squarepants/plugin/repo/register.py
)
""")

      self.assert_file_contents('child1/src/main/proto/BUILD.gen', """
java_protobuf_library(name='proto',
  sources = rglobs('*.proto'),
  imports = [],
  dependencies = [
    'child2/src/main/java:lib'
  ],
)
""")
      self.assert_file_contents('child1/src/main/resources/BUILD.gen', """
resources(name='resources',
  sources = rglobs('*', exclude=[globs('BUILD*')]),
  dependencies = [],
)
""")

      self.assert_file_contents('child1/src/test/java/BUILD.gen', """
junit_tests(name='test',
   # TODO: Ideally, sources between :test and :lib should not intersect
  sources = rglobs('*.java'),
  dependencies = [
    ':lib',
  ],
)

java_library(name='lib',
  sources = rglobs('*.java'),
  resources = [
    'child1/src/test/resources:resources'
  ],
  dependencies = [
    'child1/src/main/java:lib',
    'child1/src/main/proto:proto',
    'child1/src/test/proto:proto',
    'child2/src/main/java:lib',
    'testing-support/src/main/java:lib'
  ],
  provides = artifact(org='com.example',
                      name='child1',
                      repo=square,),  # see squarepants/plugin/repo/register.py
)
""")
      self.assert_file_contents('child1/src/test/proto/BUILD.gen', """
java_protobuf_library(name='proto',
  sources = rglobs('*.proto'),
  imports = [],
  dependencies = [
    'child1/src/main/proto:proto',
    'child2/src/main/java:lib'
  ],
)
""")
      self.assert_file_contents('child1/src/test/resources/BUILD.gen', """
resources(name='resources',
  sources = rglobs('*', exclude=[globs('BUILD*')]),
  dependencies = [],
)
""")


  def test_external_jar_ref(self):
    with temporary_dir() as tmpdir:
      os.chdir(tmpdir)
      with open(os.path.join('pom.xml') , 'w') as pomfile:
        pomfile.write(dedent('''<?xml version="1.0" encoding="UTF-8"?>
                      <project>

                        <groupId>com.example</groupId>
                        <artifactId>parent</artifactId>
                        <version>HEAD-SNAPSHOT</version>

                        <modules>
                          <module>child1</module>
                        </modules>
                      </project>
                    '''))

      os.makedirs(os.path.join('parents', 'base'))
      with open(os.path.join('parents', 'base', 'pom.xml'), 'w') as base_pom:
        base_pom.write(dedent('''<?xml version="1.0" encoding="UTF-8"?>
                    <project>

                      <groupId>com.example</groupId>
                      <artifactId>child1</artifactId>
                      <version>HEAD-SNAPSHOT</version>

                      <dependencyManagement>
                      </dependencyManagement>
                    </project>'''))

      child1_path_name =  'child1'
      # Make some empty directories to hold BUILD.gen files
      os.makedirs(os.path.join(child1_path_name, 'src', 'main', 'java'))
      child1_pom_name = os.path.join(child1_path_name, 'pom.xml')
      with open(child1_pom_name, 'w') as child1_pomfile:
        child1_pomfile.write(dedent('''<?xml version="1.0" encoding="UTF-8"?>
                    <project>

                      <groupId>com.example</groupId>
                      <artifactId>child1</artifactId>
                      <version>HEAD-SNAPSHOT</version>

                      <dependencies>
                        <dependency>
                          <groupId>com.example.external</groupId>
                          <artifactId>foo</artifactId>
                          <version>1.2.3</version>
                          <classifier>shaded</classifier>
                        </dependency>

                      </dependencies>
                    </project>
                  '''))
      self.make_file('child1/src/main/java/Foo.java', 'class Foo { }')
      PomToBuild().convert_pom('child1/pom.xml', rootdir=tmpdir, print_headers=False)
      self.assert_file_contents('child1/BUILD.gen', """
target(name='lib',
  dependencies = [
    'child1/src/main/java:lib'
  ],
)
""")
      self.assert_file_contents('child1/src/main/java/BUILD.gen', """
java_library(name='lib',
  sources = rglobs('*.java'),
  resources = [],
  dependencies = [
        ':jar_files',

  ],
  provides = artifact(org='com.example',
                      name='child1',
                      repo=square,),  # see squarepants/plugin/repo/register.py
)

jar_library(name='jar_files',
  jars = [
    jar(org='com.example.external', name='foo', rev='1.2.3', classifier='shaded')
  ],
)
""")
