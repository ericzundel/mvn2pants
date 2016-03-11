# Tests for code in squarepants/src/main/python/squarepants/pom_to_build.py
#
# Run with:
# ./pants test squarepants/src/test/python/squarepants_test:pom_to_build

from contextlib import contextmanager
import os
import sys
from textwrap import dedent
import unittest2 as unittest

from squarepants.pom_to_build import PomToBuild
from squarepants.generation_context import GenerationContext
from squarepants.file_utils import temporary_dir, touch
from squarepants.pom_utils import PomUtils


class PomToBuildTest(unittest.TestCase):

  def setUp(self):
    self.maxDiff = None
    self._wd = os.getcwd()
    PomUtils.reset_caches()

  def tearDown(self):
    # Restore the working directory
    os.chdir(self._wd)

  def assert_file_contents(self, filename, expected_contents, ignore_blanklines=True,
                           ignore_trailing_spaces=True,
                           ignore_leading_spaces=False):
    self.assertTrue(os.path.exists(filename), msg="Missing file {}".format(filename))

    def reformat(text):
      lines = text.split('\n')
      if ignore_blanklines:
        lines = [line for line in lines if line.strip()]
      if ignore_leading_spaces and ignore_trailing_spaces:
        lines = [line.strip() for line in lines]
      elif ignore_leading_spaces:
        lines = [line.lstrip() for line in lines]
      elif ignore_trailing_spaces:
        lines = [line.rstrip() for line in lines]
      return '\n'.join(lines)

    with open(filename, 'r') as f:
      contents = f.read()

    print('\nExpected: ')
    print(dedent(expected_contents))
    print('\nReceived: ')
    print(dedent(contents))
    expected_contents = reformat(expected_contents)
    contents = reformat(contents)
    self.assertEquals(expected_contents, contents)

  def make_file(self, filename, contents):
    if os.path.dirname(filename):
      if not os.path.exists(os.path.dirname(filename)):
        os.makedirs(os.path.dirname(filename))
    with open(filename, 'w') as f:
      f.write(contents)

  def test_write_build_gen(self):
    gen_context = GenerationContext(print_headers=False)
    is_aux = gen_context.is_aux
    infer_target_name = gen_context.infer_target_name
    infer_build_name = gen_context.infer_build_name
    write_build_file = gen_context.write_build_file
    with temporary_dir() as build_dir:
      self.assertFalse(is_aux(build_dir))
      self.assertEquals('foo', infer_target_name(build_dir, 'foo'))
      self.assertEquals(os.path.join(build_dir, 'BUILD.gen'), infer_build_name(build_dir))
      write_build_file(build_dir, 'contents of BUILD.gen')
      self.assertTrue(os.path.exists(os.path.join(build_dir, 'BUILD.gen')))
      with open(os.path.join(build_dir, 'BUILD.gen')) as build_file:
        self.assertEquals('contents of BUILD.gen', build_file.read())

  def test_write_build_aux(self):
    gen_context = GenerationContext(print_headers=False)
    is_aux = gen_context.is_aux
    infer_target_name = gen_context.infer_target_name
    infer_build_name = gen_context.infer_build_name
    write_build_file = gen_context.write_build_file
    with temporary_dir() as build_dir:
      with open(os.path.join(build_dir, 'BUILD'), 'w'):
        self.assertTrue(is_aux(build_dir))
        self.assertEquals('aux-foo', infer_target_name(build_dir, 'foo'))
        self.assertEquals(os.path.join(build_dir, 'BUILD.aux'), infer_build_name(build_dir))
        write_build_file(build_dir, 'contents of BUILD.aux')
        self.assertTrue(os.path.exists(os.path.join(build_dir, 'BUILD.aux')))
        with open(os.path.join(build_dir, 'BUILD.aux')) as build_file:
          self.assertEquals('contents of BUILD.aux', build_file.read())

  def create_pom_with_modules(self, path, modules, extra_project_contents=None,
                              extra_parent_contents=None,
                              extra_root_contents=None):
    with open(os.path.join(path, 'pom.xml'), 'w') as pomfile:
      triple_quote_string = """<?xml version="1.0" encoding="UTF-8"?>
                <project>

                  <groupId>com.example</groupId>
                  <artifactId>parent</artifactId>
                  <version>HEAD-SNAPSHOT</version>

                  <modules>
                    {module_text}
                  </modules>
                  {extra_contents}
                </project>
              """
      pomfile.write(smart_dedent(triple_quote_string).format(
        module_text='\n'.join('    <module>{}</module>'.format(module) for module in modules),
        extra_contents=extra_root_contents or ''
      ))
    os.makedirs(os.path.join('parents', 'base'))
    with open(os.path.join('parents', 'base', 'pom.xml'), 'w') as pomfile:
      triple_quote_string = """<project>

                  <groupId>com.example</groupId>
                  <artifactId>{module}</artifactId>
                  <version>HEAD-SNAPSHOT</version>

                  <dependencyManagement>
                  </dependencyManagement>
                </project>
                """
      module_text = '\n'.join(smart_dedent(triple_quote_string).format(module=module)
                              for module in modules[:1])
      if extra_parent_contents:
        module_text += extra_parent_contents
      print(module_text)
      pomfile.write('<?xml version="1.0" encoding="UTF-8"?>\n{}'.format(module_text))
    for module in modules:
      triple_quote_string = """<?xml version="1.0" encoding="UTF-8"?>
                <project>

                  <groupId>com.example</groupId>
                  <artifactId>{module}</artifactId>
                  <version>HEAD-SNAPSHOT</version>

                  <dependencies>
                  </dependencies>

                  {extra_contents}
                </project>
      """
      with open(os.path.join(path, module, 'pom.xml'), 'w') as pomfile:
        pomfile.write(smart_dedent(triple_quote_string).format(
            module=module,
          extra_contents = extra_project_contents or ''
        ))

  @contextmanager
  def setup_two_child_poms(self):
    with temporary_dir() as tmpdir:
      os.chdir(tmpdir)

      with open(os.path.join('pom.xml') , 'w') as pomfile:
        triple_quote_string = """<?xml version="1.0" encoding="UTF-8"?>
                <project>

                  <groupId>com.example</groupId>
                  <artifactId>parent</artifactId>
                  <version>HEAD-SNAPSHOT</version>

                  <modules>
                    <module>child1</module>
                    <module>child2</module>
                  </modules>
                </project>
              """
        pomfile.write(smart_dedent(triple_quote_string))

      os.makedirs(os.path.join('parents', 'base'))
      with open(os.path.join('parents', 'base', 'pom.xml'), 'w') as base_pom:
        triple_quote_string = """<?xml version="1.0" encoding="UTF-8"?>
                <project>

                  <groupId>com.example</groupId>
                  <artifactId>child1</artifactId>
                  <version>HEAD-SNAPSHOT</version>

                  <dependencyManagement>
                  </dependencyManagement>
                </project>"""
        base_pom.write(smart_dedent(triple_quote_string))

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
        triple_quote_string = """<?xml version="1.0" encoding="UTF-8"?>
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
              """
        child1_pomfile.write(smart_dedent(triple_quote_string))
      child2_path_name = os.path.join('child2')
      os.makedirs(os.path.join(child2_path_name, 'src', 'main', 'java'))
      os.makedirs(os.path.join(child2_path_name, 'src', 'main', 'proto'))
      os.makedirs(os.path.join(child2_path_name, 'src', 'main', 'resources'))
      os.makedirs(os.path.join(child2_path_name, 'src', 'test', 'java'))
      os.makedirs(os.path.join(child2_path_name, 'src', 'test', 'proto'))
      os.makedirs(os.path.join(child2_path_name, 'src', 'test', 'resources'))
      child2_pom_name = os.path.join(child2_path_name, 'pom.xml')
      with open(child2_pom_name, 'w') as child2_pomfile:
        triple_quote_string = """<?xml version="1.0" encoding="UTF-8"?>
                <project>

                  <groupId>com.example</groupId>
                  <artifactId>child2</artifactId>
                  <version>HEAD-SNAPSHOT</version>
                  <dependencies>
                  </dependencies>
                </project>
              """
        child2_pomfile.write(smart_dedent(triple_quote_string))
      yield tmpdir


  def test_ignore_empty_dirs_in_self(self):
    with self.setup_two_child_poms() as tmpdir:
      PomToBuild().convert_pom('child1/pom.xml',
                               generation_context=GenerationContext(print_headers=False))

      # Since all the dirs are empty, we should only have a project level pom file,
      # the others should be blank
      triple_quote_string = """
        target(name='lib')


        target(name='test',
          dependencies = [
            ':lib'
          ],
        )
      """
      self.assert_file_contents('child1/BUILD.gen', smart_dedent(triple_quote_string))

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
      self.make_file('child1/src/test/java/FooIT.java', 'class FooIT {}')
      self.make_file('child1/src/test/resources/foo_test.txt', "Testing: Foo bar baz.")
      PomToBuild().convert_pom('child1/pom.xml', rootdir=tmpdir,
                               generation_context=GenerationContext(print_headers=False))

      triple_quote_string = """
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
"""
      self.assert_file_contents('child1/BUILD.gen', triple_quote_string)

      # There should be no references to child2 in the BUILD files under src/main
      # because the directories under child2 are empty
      triple_quote_string = """
java_library(name='lib',
  sources = rglobs('*.java'),
  resources = [
    'child1/src/main/resources:resources'
  ],
  dependencies = [
    'child1/src/main/proto'
  ],
  provides = artifact(org='com.example',
                      name='child1',
                      repo=square,),  # see squarepants/plugin/repo/register.py
)
"""
      self.assert_file_contents('child1/src/main/java/BUILD.gen', triple_quote_string)
      triple_quote_string = """
java_protobuf_library(name='proto',
  sources = rglobs('*.proto'),
  imports = [],
  dependencies = [
    ':proto-sources'
  ],
  provides = artifact(org='com.example',
                      name='child1-proto',
                      repo=square,),  # see squarepants/plugin/repo/register.py
)
wire_proto_path(name='path',
  sources=rglobs('*.proto'),
  dependencies=[],
)
resources(name='proto-sources',
  sources = rglobs('*.proto'),
)
"""
      self.assert_file_contents('child1/src/main/proto/BUILD.gen', triple_quote_string)
      triple_quote_string = """
resources(name='resources',
  sources = rglobs('*', exclude=[globs('BUILD*')]),
  dependencies = [],
)
"""
      self.assert_file_contents('child1/src/main/resources/BUILD.gen', triple_quote_string)

      # TODO(Eric Ayers) The provides statement in src/test/java is the same as in lib.  This probably
      # shouldn't be duplicated like this!
      triple_quote_string = """
junit_tests(name='test',
  # TODO: Ideally, sources between :test, :integration-tests  and :lib should not intersect
  sources = rglobs('*Test.java'),
  cwd = 'child1',
  dependencies = [
    ':lib'
  ],
)
junit_tests(name='integration-tests',
  # TODO: Ideally, sources between :test, :integration-tests  and :lib should not intersect
  sources = rglobs('*IT.java'),
  cwd = 'child1',
  tags = [
    'integration'
  ],
  dependencies = [
    ':lib'
  ],
)
java_library(name='lib',
  sources = rglobs('*.java'),
  resources = [
    'child1/src/test/resources:resources'
  ],
  dependencies = [
    'child1/src/main/java:lib',
    'child1/src/main/proto',
    'child1/src/test/proto',
    'testing-support/src/main/java:lib'
  ],
  provides = artifact(org='com.example',
                      name='child1-test',
                      repo=square,),  # see squarepants/plugin/repo/register.py
)
"""
      self.assert_file_contents('child1/src/test/java/BUILD.gen', triple_quote_string)
      triple_quote_string = """
java_protobuf_library(name='proto',
  sources = rglobs('*.proto'),
  imports = [],
  dependencies = [
    ':proto-sources',
    'child1/src/main/proto'
  ],
  provides = artifact(org='com.example',
                      name='child1-proto',
                      repo=square,),  # see squarepants/plugin/repo/register.py
)

wire_proto_path(name='path',
  sources=rglobs('*.proto'),
  dependencies=[
    'child1/src/main/proto:path'
  ],
)

resources(name='proto-sources',
  sources = rglobs('*.proto'),
)
"""
      self.assert_file_contents('child1/src/test/proto/BUILD.gen', triple_quote_string)
      triple_quote_string = """
resources(name='resources',
  sources = rglobs('*', exclude=[globs('BUILD*')]),
  dependencies = [],
)
"""
      self.assert_file_contents('child1/src/test/resources/BUILD.gen', triple_quote_string)


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
      PomToBuild().convert_pom('child1/pom.xml', rootdir=tmpdir,
                               generation_context=GenerationContext(print_headers=False))
      triple_quote_string = """
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
"""
      self.assert_file_contents('child1/BUILD.gen', triple_quote_string, ignore_leading_spaces=True)
      triple_quote_string = """
java_library(name='lib',
  sources = rglobs('*.java'),
  resources = [
    'child1/src/main/resources:resources'
  ],
  dependencies = [
    'child1/src/main/proto',
    'child2/src/main/java:lib'
  ],
  provides = artifact(org='com.example',
                      name='child1',
                      repo=square,),  # see squarepants/plugin/repo/register.py
)
"""
      self.assert_file_contents('child1/src/main/java/BUILD.gen', triple_quote_string)

      triple_quote_string = """
java_protobuf_library(name='proto',
  sources = rglobs('*.proto'),
  imports = [],
  dependencies = [
    ':proto-sources',
    'child2/src/main/java:lib'
  ],
  provides = artifact(org='com.example',
                      name='child1-proto',
                      repo=square,),  # see squarepants/plugin/repo/register.py
)
wire_proto_path(name='path',
  sources=rglobs('*.proto'),
  dependencies=[],
)
resources(name='proto-sources',
  sources = rglobs('*.proto'),
)
"""
      self.assert_file_contents('child1/src/main/proto/BUILD.gen', triple_quote_string)
      triple_quote_string = """
resources(name='resources',
  sources = rglobs('*', exclude=[globs('BUILD*')]),
  dependencies = [],
)
"""
      self.assert_file_contents('child1/src/main/resources/BUILD.gen', triple_quote_string)

      triple_quote_string = """
junit_tests(name='test',
  # TODO: Ideally, sources between :test, :integration-tests  and :lib should not intersect
  sources = rglobs('*Test.java'),
  cwd = 'child1',
  dependencies = [
    ':lib'
  ],
)
junit_tests(name='integration-tests',
  # TODO: Ideally, sources between :test, :integration-tests  and :lib should not intersect
  sources = rglobs('*IT.java'),
  cwd = 'child1',
  tags = [
    'integration'
  ],
  dependencies = [
    ':lib'
  ],
)
java_library(name='lib',
  sources = rglobs('*.java'),
  resources = [
    'child1/src/test/resources:resources'
  ],
  dependencies = [
    'child1/src/main/java:lib',
    'child1/src/main/proto',
    'child1/src/test/proto',
    'child2/src/main/java:lib',
    'testing-support/src/main/java:lib'
  ],
  provides = artifact(org='com.example',
                      name='child1-test',
                      repo=square,),  # see squarepants/plugin/repo/register.py
)
"""
      self.assert_file_contents('child1/src/test/java/BUILD.gen', triple_quote_string)
      triple_quote_string = """
java_protobuf_library(name='proto',
  sources = rglobs('*.proto'),
  imports = [],
  dependencies = [
    ':proto-sources',
    'child1/src/main/proto',
    'child2/src/main/java:lib'
  ],
  provides = artifact(org='com.example',
                      name='child1-proto',
                      repo=square,),  # see squarepants/plugin/repo/register.py
)

wire_proto_path(name='path',
  sources=rglobs('*.proto'),
  dependencies=[
    'child1/src/main/proto:path'
  ],
)

resources(name='proto-sources',
  sources = rglobs('*.proto'),
)
"""
      self.assert_file_contents('child1/src/test/proto/BUILD.gen', triple_quote_string)
      triple_quote_string = """
resources(name='resources',
  sources = rglobs('*', exclude=[globs('BUILD*')]),
  dependencies = [],
)
"""
      self.assert_file_contents('child1/src/test/resources/BUILD.gen', triple_quote_string)


  def test_external_jar_ref(self):
    with temporary_dir() as tmpdir:
      os.chdir(tmpdir)
      with open(os.path.join('pom.xml') , 'w') as pomfile:
        triple_quote_string = """<?xml version="1.0" encoding="UTF-8"?>
                      <project>

                        <groupId>com.example</groupId>
                        <artifactId>parent</artifactId>
                        <version>HEAD-SNAPSHOT</version>

                        <modules>
                          <module>child1</module>
                        </modules>
                      </project>
                    """
        pomfile.write(smart_dedent(triple_quote_string))

      os.makedirs(os.path.join('parents', 'base'))
      with open(os.path.join('parents', 'base', 'pom.xml'), 'w') as base_pom:
        triple_quote_string = """<?xml version="1.0" encoding="UTF-8"?>
                    <project>

                      <groupId>com.example</groupId>
                      <artifactId>child1</artifactId>
                      <version>HEAD-SNAPSHOT</version>

                      <dependencyManagement>
                      </dependencyManagement>
                    </project>"""
        base_pom.write(smart_dedent(triple_quote_string))

      child1_path_name =  'child1'
      # Make some empty directories to hold BUILD.gen files
      os.makedirs(os.path.join(child1_path_name, 'src', 'main', 'java'))
      child1_pom_name = os.path.join(child1_path_name, 'pom.xml')
      with open(child1_pom_name, 'w') as child1_pomfile:
        triple_quote_string = """<?xml version="1.0" encoding="UTF-8"?>
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
                          <type>tar.gz</type>
                        </dependency>

                      </dependencies>
                    </project>
                  """
        child1_pomfile.write(smart_dedent(triple_quote_string))
      self.make_file('child1/src/main/java/Foo.java', 'class Foo { }')
      PomToBuild().convert_pom('child1/pom.xml', rootdir=tmpdir,
                               generation_context=GenerationContext(print_headers=False))
      triple_quote_string = """
target(name='lib',
  dependencies = [
    'child1/src/main/java:lib'
  ],
)
target(name='test',
  dependencies = [
    ':lib'
  ],
)
"""
      self.assert_file_contents('child1/BUILD.gen', triple_quote_string)
      triple_quote_string = """
java_library(name='lib',
  sources = rglobs('*.java'),
  resources = [],
  dependencies = [
    ':jar_files'
  ],
  provides = artifact(org='com.example',
                      name='child1',
                      repo=square,),  # see squarepants/plugin/repo/register.py
)

jar_library(name='jar_files',
  jars=[
    sjar(org='com.example.external', name='foo', rev='1.2.3', classifier='shaded', ext='tar.gz',)
  ],
)
"""
      self.assert_file_contents('child1/src/main/java/BUILD.gen', triple_quote_string)

  def test_default_test_target(self):
    with temporary_dir() as tmp_dir:
      os.chdir(tmp_dir)
      proto_file = 'project1/src/main/proto/foo.proto'
      java_file = 'project2/src/main/java/Foo.java'
      self.make_file(proto_file, '/* proto file */')
      self.make_file(java_file, '/* java file */')
      projects = ['project1', 'project2']
      self.create_pom_with_modules(tmp_dir, projects)
      for project in projects:
        PomToBuild().convert_pom(os.path.join(project, 'pom.xml'), rootdir=tmp_dir,
                                 generation_context=GenerationContext(print_headers=False))
      triple_quote_string = """
        target(name='proto',
          dependencies = [
            'project1/src/main/proto:proto'
          ],
        )
        target(name='lib',
          dependencies = [
            ':proto'
          ],
        )
        target(name='test',
          dependencies = [
            ':lib'
          ],
        )
      """
      self.assert_file_contents('project1/BUILD.gen', triple_quote_string,
                                ignore_leading_spaces=True)
      triple_quote_string = """
        target(name='lib',
          dependencies = [
            'project2/src/main/java:lib'
          ],
        )
        target(name='test',
          dependencies = [
            ':lib'
          ],
        )
      """
      self.assert_file_contents('project2/BUILD.gen', triple_quote_string,
                                ignore_leading_spaces=True)

  def test_jvm_binary_target(self):
    with temporary_dir() as tmp_dir:
      os.chdir(tmp_dir)
      self.make_file('example-app/src/main/java/com/example/ExampleApp.java', '/* java file */')

      extra_contents = """
      <properties>
        <project.mainclass>com.example.ExampleApp</project.mainclass>
      </properties>
      """
      self.create_pom_with_modules(tmp_dir, ['example-app'],
                                   extra_project_contents=extra_contents)

      PomToBuild().convert_pom(os.path.join('example-app', 'pom.xml'), rootdir=tmp_dir,
                               generation_context=GenerationContext(print_headers=False))

      expected_contents = """
        jvm_binary(name='example-app',
          main = 'com.example.ExampleApp',
          basename= 'example-app',
          dependencies = [
            ':lib'
          ],
          manifest_entries = square_manifest(),
        )

        # This target's sole purpose is just to invalidate the cache if loose files (eg app-manifest.yaml)
        # for the jvm_binary change.
        fingerprint(name='extra-files',
          sources = [],
          dependencies = [],
        )

        target(name='lib',
          dependencies = [
            'example-app/src/main/java:lib'
          ],
        )

        target(name='test',
          dependencies = [
            ':lib'
          ],
        )
      """
      self.assert_file_contents('example-app/BUILD.gen', expected_contents,
                                 ignore_leading_spaces=True)

  @property
  def _system_specific_properties_dependencies_text(self):
    return dedent('''
    <dependencies>
      <dependency>
        <groupId>com.example</groupId>
        <artifactId>foobar-${arch}</artifactId>
        <version>${arch}-1234</version>
      </dependency>
    </dependencies>
    ''')

  @property
  def _system_specific_properties_profiles_text(self):
    return dedent('''
    <profiles>
      <profile>
        <id>not-me</id>
        <activation>
          <os>
            <name>not-my-system-type</name>
          </os>
        </activation>
        <properties>
          <arch>not-my-architecture</arch>
        </properties>
      </profile>
      <profile>
        <id>who knows, something unix-based</id>
        <activation>
          <os>
            <name>{system_name}</name>
          </os>
        </activation>
        <properties>
          <arch>for-my-architecture</arch>
        </properties>
      </profile>
      <profile>
        <id>also-not-me</id>
        <activation>
          <os>
            <name>hal</name>
          </os>
        </activation>
        <properties>
          <arch>space-ship-9000</arch>
        </properties>
      </profile>
    </profiles>
    '''.format(system_name=sys.platform))

  @property
  def _system_specific_properties_expected_text(self):
    return """
java_library(name='lib',
  sources = rglobs('*.java'),
  resources = [],
  dependencies = [
    ':jar_files'
  ],
  provides = artifact(org='com.example',
                      name='project',
                      repo=square,),  # see squarepants/plugin/repo/register.py
)

jar_library(name='jar_files',
  jars=[
    sjar(org='com.example', name='foobar-for-my-architecture', rev='for-my-architecture-1234',)
  ],
)"""

  def test_system_specific_properties(self):
    dependencies = self._system_specific_properties_dependencies_text
    profiles = self._system_specific_properties_profiles_text
    with temporary_dir() as tmp_dir:
      os.chdir(tmp_dir)
      self.make_file('project/src/main/java/Foobar.java', '/* nothing to see here */')
      self.create_pom_with_modules(tmp_dir, ['project'],
                                   extra_project_contents=dependencies + profiles)
      PomToBuild().convert_pom('project/pom.xml', rootdir=tmp_dir,
                               generation_context=GenerationContext(print_headers=False))

      self.assert_file_contents('project/src/main/java/BUILD.gen',
                                self._system_specific_properties_expected_text,
                                ignore_leading_spaces=True,
                                ignore_trailing_spaces=True,
                                ignore_blanklines=True)

  @property
  def _signed_jar_expected_text(self):
    return '''
jvm_binary(name='project',
  main = 'com.example.project.Project',
  basename= 'project',
  dependencies = [
    ':lib',
    ':project-signed-jars'
  ],
  manifest_entries = square_manifest({
    'Class-Path': 'project-signed-jars/artifact-one.jar project-signed-jars/artifact-two.jar',
  }),
  deploy_excludes = [
    exclude(org='org.barfoo', name='artifact-two'),
    exclude(org='org.foobar', name='artifact-one')
  ],
)

signed_jars(name='project-signed-jars',
  dependencies=[
    '3rdparty:org.barfoo.artifact-two',
    '3rdparty:org.foobar.artifact-one'
  ],
  strip_version=True,
)

# This target's sole purpose is just to invalidate the cache if loose files (eg app-manifest.yaml)
# for the jvm_binary change.
fingerprint(name='extra-files',
  sources = [],
  dependencies = [],
)

target(name='lib',
  dependencies = [
    'project/src/main/java:lib'
  ],
)

target(name='test',
  dependencies = [
    ':lib'
  ],
)
'''

  @contextmanager
  def _setup_signed_jar_test(self):
    with temporary_dir() as tmp_dir:
      os.chdir(tmp_dir)
      parent_pom_text = '''
<?xml version="1.0" encoding="UTF-8"?>
<project xmlns="http://maven.apache.org/POM/4.0.0"
    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
    xsi:schemaLocation="http://maven.apache.org/POM/4.0.0 http://maven.apache.org/xsd/maven-4.0.0.xsd">
  <modelVersion>4.0.0</modelVersion>

  <parent>
    <groupId>com.example</groupId>
    <artifactId>app</artifactId>
    <version>HEAD-SNAPSHOT</version>
    <relativePath>../base/pom.xml</relativePath>
  </parent>

  <groupId>com.example</groupId>
  <artifactId>the-parent-pom</artifactId>
  <version>HEAD-SNAPSHOT</version>
  <packaging>pom</packaging>

  <build>
    <plugins>
      <plugin>
        <groupId>com.squareup.maven.plugins</groupId>
        <artifactId>shade-plugin</artifactId>
        <version>${shade-plugin.version}</version>
        <executions>
          <execution>
            <phase>package</phase>
            <goals>
              <goal>shade</goal>
            </goals>
            <configuration>
              <shadedArtifactAttached>true</shadedArtifactAttached>
              <shadedClassifierName>shaded</shadedClassifierName>
              <transformers>
                <transformer>
                  <manifestEntries>
                    <Class-Path>lib-signed/artifact-one.jar lib-signed/artifact-two.jar</Class-Path>
                  </manifestEntries>
                </transformer>
              </transformers>
              <artifactSet>
                <excludes>
                  <exclude>org.foobar:artifact-one</exclude>
                  <exclude>org.barfoo:artifact-two</exclude>
                </excludes>
              </artifactSet>
            </configuration>
          </execution>
        </executions>
      </plugin>
      <plugin>
        <groupId>org.apache.maven.plugins</groupId>
        <artifactId>maven-dependency-plugin</artifactId>
        <executions>
          <execution>
            <id>copy</id>
            <phase>package</phase>
            <goals>
              <goal>copy-dependencies</goal>
            </goals>
            <configuration>
              <outputDirectory>${project.build.directory}/lib-signed</outputDirectory>
              <includeArtifactIds>artifact-one,artifact-two</includeArtifactIds>
              <stripVersion>true</stripVersion>
            </configuration>
          </execution>
        </executions>
      </plugin>
    </plugins>
  </build>
</project>
'''
      parent_pom_text = parent_pom_text.strip()

      project_pom_text = '''
<?xml version="1.0" encoding="UTF-8"?>
<project xmlns="http://maven.apache.org/POM/4.0.0"
    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
    xsi:schemaLocation="http://maven.apache.org/POM/4.0.0 http://maven.apache.org/xsd/maven-4.0.0.xsd">
  <modelVersion>4.0.0</modelVersion>

  <parent>
    <groupId>com.example</groupId>
    <artifactId>the-parent-pom</artifactId>
    <version>HEAD-SNAPSHOT</version>
    <relativePath>../parents/the-parent/pom.xml</relativePath>
  </parent>

  <groupId>com.example.project</groupId>
  <artifactId>project</artifactId>
  <version>HEAD-SNAPSHOT</version>

  <name>gns-server</name>

  <properties>
    <project.mainclass>com.example.project.Project</project.mainclass>
    <deployableBranch>project</deployableBranch>
  </properties>

  <dependencies>
  </dependencies>
</project>
'''
      project_pom_text = project_pom_text.strip()

      parent_base_text = '''
<?xml version="1.0" encoding="UTF-8"?>
<project>
  <groupId>com.example</groupId>
  <artifactId>the-parent-pom</artifactId>
  <version>HEAD-SNAPSHOT</version>

  <dependencyManagement>
  </dependencyManagement>
</project>
'''
      parent_base_text = parent_base_text.strip()

      root_pom_text = """
<?xml version="1.0" encoding="UTF-8"?>
<project>

  <groupId>com.example</groupId>
  <artifactId>parent</artifactId>
  <version>HEAD-SNAPSHOT</version>

  <modules>
    <module>child1</module>
  </modules>
</project>
"""
      root_pom_text = root_pom_text.strip()

      self.make_file('project/src/main/java/com/example/project/Project.java', '/* nope */')
      # NOTE(gm): This test probably could be made to work with fewer pom.xml's, this seems
      # excessive.
      self.make_file('project/pom.xml', project_pom_text)
      self.make_file('parents/the-parent/pom.xml', parent_pom_text)
      self.make_file('parents/base/pom.xml', parent_base_text)
      self.make_file('pom.xml', root_pom_text)
      yield tmp_dir

  def test_signed_jars(self):
    with self._setup_signed_jar_test() as tmp_dir:
      PomToBuild().convert_pom('project/pom.xml', rootdir=tmp_dir,
                               generation_context=GenerationContext(print_headers=False))
      self.assert_file_contents('project/BUILD.gen', self._signed_jar_expected_text)

  @contextmanager
  def _setup_single_module(self, module_name, module_pom_contents, touch_files=None):
    with temporary_dir() as tempdir:
      current_dir = os.path.abspath('.')
      os.chdir(tempdir)

      self.make_file('pom.xml', dedent('''
        <?xml version="1.0" encoding="UTF-8"?>
        <project>
          <groupId>com.example</groupId>
          <artifactId>parent</artifactId>
          <version>HEAD-SNAPSHOT</version>

          <modules>
            <module>{module_name}</module>
          </modules>
        </project>
      '''.format(module_name=module_name)).strip())

      self.make_file(os.path.join('parents', 'base', 'pom.xml'), dedent('''
        <?xml version="1.0" encoding="UTF-8"?>
        <project>
          <groupId>com.example</groupId>
          <artifactId>the-parent-pom</artifactId>
          <version>HEAD-SNAPSHOT</version>

          <dependencyManagement>
          </dependencyManagement>
        </project>
      '''.strip()))

      self.make_file(os.path.join(module_name, 'pom.xml'), dedent('''
        <?xml version="1.0" encoding="UTF-8"?>
        <project xmlns="http://maven.apache.org/POM/4.0.0"
            xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
            xsi:schemaLocation="http://maven.apache.org/POM/4.0.0 http://maven.apache.org/xsd/maven-4.0.0.xsd">
          <modelVersion>4.0.0</modelVersion>

          <parent>
            <groupId>com.example</groupId>
            <artifactId>the-parent-pom</artifactId>
            <version>HEAD-SNAPSHOT</version>
            <relativePath>../parents/base/pom.xml</relativePath>
          </parent>

          <groupId>com.example.project</groupId>
          <artifactId>{module_name}</artifactId>
          <version>HEAD-SNAPSHOT</version>

          {module_pom_contents}
        </project>
      ''').format(module_name=module_name,
                  module_pom_contents=module_pom_contents).strip())

      for path in (touch_files or ()):
        touch(path, makedirs=True)

      yield os.path.join(module_name, 'pom.xml')

      os.chdir(current_dir)

  def _shading_pom_contents(self):
    return smart_dedent('''
      <properties>
        <project.mainclass>com.squareup.example.foobar.Main</project.mainclass>
        <deployableBranch>shading-test</deployableBranch>
      </properties>

      <build>
        <plugins>
          <plugin>
            <groupId>org.apache.maven.plugins</groupId>
            <artifactId>maven-compiler-plugin</artifactId>
            <configuration>
              <source>1.7</source>
              <target>1.7</target>
              <fork>true</fork>
              <compilerArgs>
                <arg>-Xbootclasspath:${java7.bootclasspath}</arg>
                <arg>-Xlint:cast</arg>
                <arg>-Xlint:deprecation</arg>
                <arg>-Xlint:empty</arg>
                <arg>-Xlint:finally</arg>
              </compilerArgs>
            </configuration>
          </plugin>
          <plugin>
            <groupId>org.apache.maven.plugins</groupId>
            <artifactId>maven-surefire-plugin</artifactId>
            <configuration>
              <jvm>/path/to/jvm/bin/java</jvm>
            </configuration>
          </plugin>
          <plugin>
            <groupId>com.squareup.maven.plugins</groupId>
            <artifactId>shade-plugin</artifactId>
            <version>${shade-plugin.version}</version>
            <executions>
              <execution>
                <phase>package</phase>
                <goals>
                  <goal>shade</goal>
                </goals>
                <configuration>
                  <shadedArtifactAttached>true</shadedArtifactAttached>
                  <shadedClassifierName>shaded</shadedClassifierName>
                  <relocations>
                    <relocation>
                      <!-- hadoop uses guava 11, but our java repo uses guava 14 -->
                      <pattern>com.google.common.</pattern>
                      <shadedPattern>shaded_for_hadoop.com.google.common.</shadedPattern>
                    </relocation>
                    <relocation>
                      <!-- hadoop uses guice 3.x but our java repo uses guice 4.x -->
                      <pattern>com.google.inject.</pattern>
                      <shadedPattern>shaded_for_hadoop.com.google.inject.</shadedPattern>
                    </relocation>
                    <relocation>
                      <!-- CDH 4.3.0 uses hsqldb 1.8.0.7, but our java repo uses 2.2.4 -->
                      <pattern>org.hsqldb.</pattern>
                      <shadedPattern>shaded_for_hadoop.org.hsqldb.</shadedPattern>
                    </relocation>
                    <relocation>
                      <!-- CDH 4.3.0 uses protobuf 2.4.0a, but our java repo uses 2.4.1.square.1.3 -->
                      <pattern>com.google.protobuf.</pattern>
                      <shadedPattern>shaded_for_hadoop.com.google.protobuf.</shadedPattern>
                    </relocation>
                  </relocations>
                </configuration>
              </execution>
            </executions>
          </plugin>
        </plugins>
      </build>
    ''')

  def _shading_rules_expected(self):
    return dedent('''
      jvm_binary(name='shading-test',
        main = 'com.squareup.example.foobar.Main',
        basename= 'shading-test',
        dependencies = [
          ':lib'
        ],
        manifest_entries = square_manifest(),
        platform = '1.7',
        shading_rules = [
          shading_relocate_package('com.google.common', shade_prefix='shaded_for_hadoop.'),
          shading_relocate_package('com.google.inject', shade_prefix='shaded_for_hadoop.'),
          shading_relocate_package('org.hsqldb', shade_prefix='shaded_for_hadoop.'),
          shading_relocate_package('com.google.protobuf', shade_prefix='shaded_for_hadoop.')
        ],
       )


       # This target's sole purpose is just to invalidate the cache if loose files (eg app-manifest.yaml)
       # for the jvm_binary change.
       fingerprint(name='extra-files',
         sources = [],
         dependencies = [],
       )

       target(name='lib')

       target(name='test',
        dependencies = [
          ':lib'
        ],
       )
    ''').strip()

  def test_shading_rules(self):
    with self._setup_single_module('shading-test', self._shading_pom_contents()) as pom:
      PomToBuild().convert_pom(pom, rootdir=os.path.abspath('.'),
                               generation_context=GenerationContext(print_headers=False))
      self.assert_file_contents('{}/BUILD.gen'.format(os.path.dirname(pom)),
                                self._shading_rules_expected(), ignore_leading_spaces=True)

  def _system_path_module(self):
    return smart_dedent('''
        <dependencies>
          <dependency>
            <groupId>com.sun</groupId>
            <artifactId>tools</artifactId>
            <version>1.8.0_45</version>
            <scope>system</scope>
            <systemPath>/Path/To/Java/lib/tools.jar</systemPath>
          </dependency>
        </dependencies>
    ''')

  def _system_path_expected(self):
    return smart_dedent('''
      java_library(name='lib',
       sources = rglobs('*.java'),
       resources = [],
       dependencies = [
         ':jar_files'
       ],
       provides = artifact(org='com.example.project',
                           name='criteriabuilders',
                           repo=square,),  # see squarepants/plugin/repo/register.py
      )

      jar_library(name='jar_files',
       jars=[
         sjar(org='com.example', name='the-parent-pom', rev='HEAD-SNAPSHOT',),
         sjar(org='com.sun', name='tools', rev='1.8.0_45',
           url='file:///Path/To/Java/lib/tools.jar',)
       ],
      )
    ''')

  def test_system_path(self):
    with self._setup_single_module('criteriabuilders', self._system_path_module(),
                                   touch_files=['criteriabuilders/src/main/java/Foo.java']) as pom:
      PomToBuild().convert_pom(pom, rootdir=os.path.abspath('.'),
                               generation_context=GenerationContext(print_headers=False))
      path = os.path.join(os.path.dirname(pom), 'src/main/java/BUILD.gen')
      self.assert_file_contents(path,
                                self._system_path_expected(), ignore_leading_spaces=True)

def smart_dedent(text):
  """Like dedent, but dedents the first line separately from the rest of the string."""
  lines = text.split('\n')
  if len(lines) <= 1:
    return dedent(text)
  return '{}\n{}'.format(dedent(lines[0]), dedent('\n'.join(lines[1:])))
