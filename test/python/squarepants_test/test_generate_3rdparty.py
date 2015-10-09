# Tests for code in squarepants/src/main/python/squarepants/generate_3rdparty.py
#
# Run with:
# ./pants test squarepants/src/test/python/squarepants_test:generate_3rdparty

import unittest2 as unittest
from collections import namedtuple

from squarepants.generate_3rdparty import ThirdPartyBuildGenerator


DependencySet = namedtuple('DependencySet', ['dependency_list', 'dependency_string'])


def _sanitize_build_contents(text):
  """Strip leading/trailing whitespace, empty lines, and line comments."""
  lines = text.split('\n')
  lines = (line[:line.rfind('#')] for line in lines)
  lines = (line.strip() for line in lines)
  lines = (line for line in lines if line)
  return '\n'.join(lines)


def dependency_set_test(dependency_set_factory):
  def inner(self):
    dependency_set = dependency_set_factory(self)
    generator = ThirdPartyBuildGenerator(dependency_set.dependency_list)
    result = generator.generate()
    self.assertEquals(_sanitize_build_contents(dependency_set.dependency_string),
                      _sanitize_build_contents(result),
                      'Generated code does not match expectations!\n'
                      '\nExpected:\n{expected}\n'
                      '\nReceived:\n{received}'.format(expected=dependency_set.dependency_string,
                                                       received=result))
  return inner


class GenerateThirdPartyTest(unittest.TestCase):

  @dependency_set_test
  def test_simple_jar(self):
    return DependencySet(dependency_list=[{
      'groupId': 'com.squareup',
      'artifactId': 'simple-example',
      'version': '1.0',
    }], dependency_string = '''
      jar_library(name='com.squareup.simple-example',
        jars=[
          sjar(org='com.squareup', name='simple-example', rev='1.0',)
        ],
      )
    ''')

  @dependency_set_test
  def test_two_classifiers(self):
    return DependencySet(dependency_list=[{
      'groupId': 'org.foobar',
      'artifactId': 'artifact-name',
      'version': '1.2.3',
      'classifier': 'one',
    }, {
      'groupId': 'org.foobar',
      'artifactId': 'artifact-name',
      'version': '1.2.3',
      'classifier': 'two',
    }], dependency_string = '''
      jar_library(name='org.foobar.artifact-name',
        jars=[
          sjar(org='org.foobar', name='artifact-name', rev='1.2.3', classifier='one',),
          sjar(org='org.foobar', name='artifact-name', rev='1.2.3', classifier='two',)
        ],
      )
    ''')

  @dependency_set_test
  def test_two_libraries(self):
    return DependencySet(dependency_list=[{
      'groupId': 'org.foobar.a',
      'artifactId': 'artifact-name',
      'version': '1.2.3',
      'classifier': 'one',
    }, {
      'groupId': 'org.foobar.b',
      'artifactId': 'artifact-name',
      'version': '1.2.3',
      'classifier': 'two',
    }], dependency_string = '''
      jar_library(name='org.foobar.a.artifact-name',
        jars=[
          sjar(org='org.foobar.a', name='artifact-name', rev='1.2.3', classifier='one',)
        ],
      )
      jar_library(name='org.foobar.b.artifact-name',
        jars=[
          sjar(org='org.foobar.b', name='artifact-name', rev='1.2.3', classifier='two',)
        ],
      )
    ''')

  @dependency_set_test
  def test_versions_and_classifiers(self):
    return DependencySet(dependency_list=[{
      'groupId': 'org.foobar',
      'artifactId': 'hello',
      'version': '1.2.3',
      'classifier': 'one',
    }, {
      'groupId': 'org.foobar',
      'artifactId': 'hello',
      'version': '1.2.3',
      'classifier': 'two',
    }, {
      'groupId': 'org.foobar',
      'artifactId': 'hello',
      'version': '3.4.5.1',
    }], dependency_string = '''
      jar_library(name='org.foobar.hello-1.2.3',
        jars=[
          sjar(org='org.foobar', name='hello', rev='1.2.3', classifier='one',
               force=True,),
          sjar(org='org.foobar', name='hello', rev='1.2.3', classifier='two',
               force=True,)
        ],
      )
      jar_library(name='org.foobar.hello-3.4.5.1',
        jars=[
          sjar(org='org.foobar', name='hello', rev='3.4.5.1',
               force=True,)
        ],
      )
    ''')
