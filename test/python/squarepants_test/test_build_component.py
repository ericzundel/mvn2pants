# Tests for code in squarepants/src/main/python/squarepants/build_component.py
#
# Run with:
# ./pants test squarepants/src/test/python/squarepants_test:build_component

import os
from textwrap import dedent
import unittest2 as unittest

from squarepants.build_component import JarFilesMixin
from squarepants.file_utils import temporary_dir
from squarepants.pom_file import PomFile
from squarepants.pom_utils import PomUtils


class BuildComponentTest(unittest.TestCase):

  def setUp(self):
    self.maxDiff = None
    self._wd = os.getcwd()
    PomUtils.reset_caches()

  def tearDown(self):
    # Restore the working directory
    os.chdir(self._wd)

  def test_format_jar_deps(self):
    # Dependencies should be sorted in alphabetical order
    self.assertEquals(dedent('''
                            jar_library(name='jar_files',
                              jars=[
                                'bar',
                                'baz',
                                'foo'
                              ],
                            )
                            '''),
                      JarFilesMixin.format_jar_library('jar_files', ["'foo'", "'bar'", "'baz'"]))
    # Duplicates should be suppressed
    self.assertEquals(dedent('''
                            jar_library(name='jar_files',
                              jars=[
                                'baz',
                                'foo'
                              ],
                            )
                            '''),
                      JarFilesMixin.format_jar_library('jar_files', ["'foo'", "'foo'", "'baz'"]))

    # jar() entries shouldn't be truncated.
    # NB(zundel): this was a problem when this method was implemented with with Target.jar_format()
    self.assertEquals(dedent('''
                            jar_library(name='jar_files',
                              jars=[
                                jar(org='square', name='foobar'),
                                jar(org='square', name='qux', excludes=(org='com.example', name='cruft')),
                                jar(org='square', name='zzz')
                              ],
                            )
                            '''),
                      JarFilesMixin.format_jar_library('jar_files', [
                        "jar(org='square', name='qux', excludes=(org='com.example', name='cruft'))",
                        "jar(org='square', name='foobar')",
                        "jar(org='square', name='zzz')"
                      ],))

  def test_format_jar_deps_symbols(self):
    with temporary_dir() as temp_path:
      parent_pom_contents = """<?xml version="1.0" encoding="UTF-8"?>
                <project>
                  <groupId>com.example</groupId>
                  <artifactId>mock-parent</artifactId>
                  <version>HEAD-SNAPSHOT</version>

                  <properties>
                    <foo>1.2.3</foo>
                  </properties>

                </project>
                """
      mock_parent_pom_filename = os.path.join(temp_path, 'pom.xml')
      with open(mock_parent_pom_filename, 'w') as f:
        f.write(parent_pom_contents)

      mock_path = os.path.join(temp_path, 'mock-project')
      os.mkdir(mock_path)
      mock_pom_filename = os.path.join(mock_path, 'pom.xml')
      pom_contents = """<?xml version="1.0" encoding="UTF-8"?>
              <project>
                <groupId>com.example</groupId>
                <artifactId>mock</artifactId>
                <version>HEAD-SNAPSHOT</version>

                <parent>
                  <groupId>com.example</groupId>
                  <artifactId>mock-project</artifactId>
                  <version>HEAD-SNAPSHOT</version>
                  <relativePath>../pom.xml</relativePath>
                </parent>
              </project>
              """
      with open(mock_pom_filename, 'w') as f:
        f.write(pom_contents)

      mock_pom_file = PomFile(mock_pom_filename)
      formatted_library = JarFilesMixin.format_jar_library('jar_files',
        ["jar(org='square', name='foobar', rev='${foo}')"],
        pom_file=mock_pom_file)
      self.assertEquals(dedent('''
                               jar_library(name='jar_files',
                                 jars=[
                                   jar(org='square', name='foobar', rev='1.2.3')
                                 ],
                               )
                               '''), formatted_library)

