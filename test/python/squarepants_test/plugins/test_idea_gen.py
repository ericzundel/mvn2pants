# Tests for code in squarepants/src/main/python/squarepants/plugins/square_idea/tasks/square_idea.py
#
# Run with:
# ./pants test squarepants/src/test/python/squarepants_test/plugins:idea_gen

from pants.backend.jvm.targets.jvm_binary import JvmBinary
from pants.base.exceptions import TaskError
from pants_test.tasks.task_test_base import TaskTestBase
import unittest

# from squarepants.plugins.square_idea.tasks.square_idea import SquareIdea
from squarepants.plugins.square_idea.tasks.square_idea_project import IdeaProject


# NB(gmalmquist): This should ideally be a subclass of TaskTestBase to test SquareIdea.
# Unfortunately we have to wait until the next open-source pants release (>= 0.0.54) for that,
# the current version of the testinfra (0.0.53) does not contain the ExportTask that SquareIdea
# depends on, so attempting to import it for unit testing crashes the test runner. This isn't a
# problem for actually running `./pants idea ...`, because that loads our own internal release of
# pants which does have the ExportTask class. For now, all we can test is the code in IdeaProject.
class SquareIdeaTest(unittest.TestCase):

  def test_common_prefix(self):
    common_prefix = IdeaProject.common_prefix
    self.assertEqual('hello', common_prefix(['hello']))
    self.assertEqual('hello', common_prefix(['hello', 'hello there']))
    self.assertEqual('hello', common_prefix(['hello there', 'hello']))
    self.assertEqual('hello', common_prefix(['hello sir', 'hello mam', 'hello-world']))
    self.assertEqual(('one', 'two'), common_prefix([
      ('one', 'two', 'three', 'four', 'five', 'six'),
      ('one', 'two', 'five', 'six'),
    ]))

  def test_java_language_level(self):
    blob = {
      'jvm_platforms': {
        'platforms': {
          '1.7': {'source_level': '1.7'},
          'the-best': {'source_level': '1.8.34._5'},
          'not-the-best': {'source_level': '1.6.1.3_12'},
        }
      },
      'targets': {
        'squarepants/faketarget': {'platform': 'the-best'},
        'squarepants/shamtarget': {'platform': 'not-the-best'},
      }
    }
    project = IdeaProject(blob, '.', '.', None)
    self.assertEqual('JDK_1_8',
                     project._java_language_level(blob['targets']['squarepants/faketarget']))
    self.assertEqual('JDK_1_6',
                     project._java_language_level(blob['targets']['squarepants/shamtarget']))

  def test_content_type(self):
    get_type = IdeaProject._content_type
    self.assertEqual('java-test-resource', get_type({'target_type': 'TEST_RESOURCE'}))

  def test_module_dependencies(self):
    blob = {
      'jvm_platforms': {
        'platforms': {
          '1.7': {'source_level': '1.7'},
        },
        'default_platform': '1.7',
      },
      'targets': {
        'foo/a:a': {
          'roots': [
            { 'source_root': 'foo/a/src/main/java' }
          ]
        },
        'foo/b:b': {
          'targets': [
            'foo/a:a',
          ],
          'roots': [
            { 'source_root': 'foo/b/src/main/java' }
          ]
        },
        'foo/c:c': {
          'roots': [
            { 'source_root': 'foo/c/src/main/java' }
          ]
        },
        'foo/d:d': {
          'roots': [
            { 'source_root': 'foo/d/src/main/java' }
          ]
        },
        'foo/e:e': {
          'targets': [
            'foo/c:c',
            'foo/d:d',
          ]
        },
        'foo/f:f': {
          'targets': [
            'foo/e:e',
          ]
        },
        'foo:foo': {
          'targets': [
            'foo/b:b',
            'foo/f:f',
          ],
          'roots': [
            { 'source_root': 'foo/src/main/java' }
          ]
        },
        'foo/cycle:cycle': {
          'targets': [
            'foo/cycle:cycle',
          ]
        },
        'bar:bar': {
          'targets': [
            'foo:foo',
          ],
          'roots': [
            { 'source_root': 'bar/src/main/java' }
          ]
        }
      }
    }

    for target in blob['targets'].values():
      target['pants_target_type'] = 'java_library'

    def module_dependencies(spec):
      modules, _ = project._compute_module_and_library_dependencies(blob['targets'][spec])
      return modules

    project = IdeaProject(blob, '.', '.', None, maven_style=True)
    self.assertEqual(set(), module_dependencies('foo/a:a'))
    self.assertEqual({'foo-a'}, module_dependencies('foo/b:b'))
    self.assertEqual({'foo-c', 'foo-d'}, module_dependencies('foo/e:e'))
    self.assertEqual({'foo-c', 'foo-d'}, module_dependencies('foo/f:f'))

    # foo/a:a isn't included because it's a transitive dependency of foo/b:b, and foo/b:b has source
    # roots. Transitive dependencies are only "collapsed" if the intermediary dependency has no
    # source roots (and thus no module to correspond to).
    self.assertEqual({'foo-b', 'foo-c', 'foo-d'}, module_dependencies('foo:foo'))
    self.assertEqual(set(), module_dependencies('foo/cycle:cycle'))
    self.assertEqual({'foo'}, module_dependencies('bar:bar'))

  def test_infer_processor_name(self):
    infer_name = IdeaProject.infer_processor_name
    self.assertEqual('1-Potato', infer_name(1, ['com.foo.bar.Potato']))
    self.assertEqual('2-com.foo.bar', infer_name(2, ['com.foo.bar.Potato',
                                                     'com.foo.bar.Carrot']))
    self.assertEqual('3-com.foo.bar', infer_name(3, ['com.foo.bar.Potato',
                                                     'com.foo.bar.fruit.Orange']))
    self.assertEqual('4-com.foo.bar.Potato-org.bar.foo.Tomato',
                     infer_name(4, ['com.foo.bar.Potato', 'org.bar.foo.Tomato']))
    self.assertEqual('5-DefaultAnnotationProcessing',
                     infer_name(5, []))

  def test_simplify_module_dependencies(self):

    def create_module(name, dependencies=None, libraries=None):
      module = IdeaProject.Module(None, directory=name, name=name, targets=set())
      if dependencies:
        module.dependencies.update(dependencies)
      if libraries:
        for conf in libraries:
          module.libraries[conf].update(libraries[conf])
      return module

    def comparable_module(module):
      jar_set = set()
      for conf, jars in module.libraries.items():
        jar_set.update((conf, jar) for jar in jars)
      return module.name, frozenset(module.dependencies), frozenset(jar_set)

    def assert_modules_equal(one, two):
      self.assertSetEqual(set(map(comparable_module, one)),
                          set(map(comparable_module, two)))

    def assert_simplifies_to(expected, modules):
      IdeaProject._simplify_module_dependency_graph(modules, prune_libraries=True)
      assert_modules_equal(expected, modules)

    assert_simplifies_to(
      expected=[
        create_module('one', {'two'}),
        create_module('two', {'three'}),
        create_module('three', {'four'}),
        create_module('four'),
      ],
      modules=[
        create_module('one', {'two', 'three', 'four'}),
        create_module('two', {'three', 'four'}),
        create_module('three', {'four'}),
        create_module('four'),
      ],
    )

    assert_simplifies_to(
      expected=[
        create_module('one', {'two'}, {'default': set()}),
        create_module('two', {'three'}, {'default': {'foo.jar', 'bar.jar'}}),
        create_module('three', {'four'}, {'default': {'hello.jar', 'apple.jar'},
                                          'sources': {'goodbye.jar'}}),
        create_module('four', set(), {'default': {'orange.jar'}}),
      ],
      modules=[
        create_module('one', {'two'}, {'default': {'foo.jar'}}),
        create_module('two', {'three'}, {'default': {'foo.jar', 'bar.jar', 'apple.jar'},
                                         'sources': {'goodbye.jar'}}),
        create_module('three', {'four'}, {'default': {'hello.jar', 'apple.jar'},
                                          'sources': {'goodbye.jar'}}),
        create_module('four', set(), {'default': {'orange.jar'}}),
      ],
    )

  def test_module_pool_no_stealing(self):
    pool = IdeaProject.ModulePool(generic_modules=('2', '1', '3'),
                                  specific_modules=('b', 'c', 'a'),
                                  steal_names=False)
    self.assertEquals('1', pool.module_for('foobar'))
    self.assertEquals('1', pool.module_for('foobar'))
    self.assertEquals('2', pool.module_for('cantaloupe'))
    self.assertEquals('3', pool.module_for('the-third-number'))
    self.assertEquals('2', pool.module_for('cantaloupe'))
    self.assertEquals('no-more-gen-modules', pool.module_for('no-more-gen-modules'))
    self.assertEquals('no-more-gen-modules', pool.module_for('no-more-gen-modules'))
    with self.assertRaises(IdeaProject.ModulePool.NoAvailableModules):
      pool.module_for('this-will-explode', create_if_necessary=False)

  def test_module_pool_stealing(self):
    pool = IdeaProject.ModulePool(generic_modules=('2', '1', '3'),
                                  specific_modules=('b', 'c', 'a'),
                                  steal_names=True)
    self.assertEquals('1', pool.module_for('foobar'))
    self.assertEquals('1', pool.module_for('foobar'))
    self.assertEquals('2', pool.module_for('cantaloupe'))
    self.assertEquals('3', pool.module_for('the-third-number'))
    self.assertEquals('2', pool.module_for('cantaloupe'))
    # The specific modules are stored in an unordered set, so we can't depend on the order.
    no_more = pool.module_for('no-more-gen-modules')
    self.assertIn(no_more, 'abc')
    self.assertEquals(no_more, pool.module_for('no-more-gen-modules'))
    self.assertIn(pool.module_for('this-will-not-explode'), 'abc')
    self.assertNotEquals(no_more, pool.module_for('this-will-not-explode'))

  def test_module_pool_preferential(self):
    pool = IdeaProject.ModulePool(generic_modules=('2', '1', '3'),
                                  specific_modules=('b', 'c', 'a'),
                                  steal_names=True)
    self.assertEquals('1', pool.module_for('foobar'))
    self.assertEquals('c', pool.module_for('c'))
    self.assertEquals('2', pool.module_for('the-third-module'))
    self.assertEquals('3', pool.module_for('the-third-number'))
    self.assertEquals('a', pool.module_for('a'))
    self.assertEquals('b', pool.module_for('process-of-elimination'))
    self.assertEquals('c', pool.module_for('c'))
    self.assertEquals('had-to-make-a-new-one', pool.module_for('had-to-make-a-new-one'))
    # 'b' has been stolen, and there are no specific or generic modules left, so this forces a new
    # generic module to be generated.
    self.assertEquals('gen-0000', pool.module_for('b'))
