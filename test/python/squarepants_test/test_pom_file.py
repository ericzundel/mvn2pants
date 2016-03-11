# Tests for code in squarepants/src/main/python/squarepants/pom_file.py
#
# Run with:
# ./pants test squarepants/src/test/python/squarepants_test:pom_file

import os
import pytest
import re
import unittest2 as unittest
from xml.etree import ElementTree

from squarepants.file_utils import temporary_dir, temporary_file
from squarepants.pom_file import PomFile
from squarepants.pom_utils import PomUtils


class BuildComponentTest(unittest.TestCase):

  def setUp(self):
    self.maxDiff = None
    self._wd = os.getcwd()
    PomUtils.reset_caches()

  def XXXtest_simple_pom_file(self):
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

      self.assertEquals(mock_path, mock_pom_file.properties['project.basedir'])
      self.assertEquals('1.2.3', mock_pom_file.properties['foo'])
      parent_pom_file = mock_pom_file.parent
      self.assertEquals(temp_path, parent_pom_file.properties['project.basedir'])


  # NB(zundel): I think this is a bug: You can't pull the properties out of a PomFile object,
  # only its parent?
  @pytest.mark.xfail
  def test_no_parent(self):
    # make sure properties are substituted
    with temporary_file() as mock_pom_filename:
      pom_contents = """<?xml version="1.0" encoding="UTF-8"?>
          <project>
            <groupId>com.example</groupId>
            <artifactId>mock</artifactId>
            <version>HEAD-SNAPSHOT</version>

            <properties>
              <foo>1.2.3</foo>
            </properties>

          </project>
          """
      with open(mock_pom_filename, 'w') as f:
        f.write(pom_contents)
      mock_pom_file = PomFile(mock_pom_filename)

      self.assertEquals(None, mock_pom_file.parent)
      self.assertEquals('1.2.3', mock_pom_file.properties['foo'])

  def _find_node_text(self, tree, path):
    prefix = tree.tag[:tree.tag.rfind('}')+1]
    path = ['{0}{1}'.format(prefix, tag) for tag in path]
    return tree.find('/'.join(['.'] + path)).text

  def test_inject_schema_exclusion_noop(self):
    tree = ElementTree.fromstring('''
<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<configuration>
    <generator>
        <database>
            <excludes> SCHEMA_VERSION  </excludes>
        </database>
    </generator>
</configuration>'''.strip())
    PomFile._inject_jooq_schema_exclusion(tree)
    self.assertEquals(' SCHEMA_VERSION  ',
                      self._find_node_text(tree, ('generator', 'database', 'excludes')))

  def test_inject_schema_new_tag(self):
    tree = ElementTree.fromstring('''
<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<configuration>
    <generator>
        <database>
        </database>
    </generator>
</configuration>'''.strip())
    PomFile._inject_jooq_schema_exclusion(tree)
    self.assertEquals('SCHEMA_VERSION',
                      self._find_node_text(tree, ('generator', 'database', 'excludes')))

  def test_inject_schema_simple(self):
    tree = ElementTree.fromstring('''
<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<configuration>
    <generator>
        <database>
          <excludes>
          </excludes>
        </database>
    </generator>
</configuration>'''.strip())
    PomFile._inject_jooq_schema_exclusion(tree)
    self.assertEquals('SCHEMA_VERSION',
                      self._find_node_text(tree, ('generator', 'database', 'excludes')))

  def test_inject_schema_concatenate(self):
    tree = ElementTree.fromstring('''
<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<configuration>
    <generator>
        <database>
          <excludes>
          SOME_TABLE
          </excludes>
        </database>
    </generator>
</configuration>'''.strip())
    PomFile._inject_jooq_schema_exclusion(tree)
    self.assertEquals('SOME_TABLE|SCHEMA_VERSION',
                      re.sub(r'\s+', '', self._find_node_text(tree, ('generator', 'database',
                                                                     'excludes'))))


  def test_merge_jooq_config(self):
    tree_one = ElementTree.fromstring('''
<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<configuration>
    <generator>
        <name>org.jooq.util.DefaultGenerator</name>
        <generate>
            <deprecated>false</deprecated>
        </generate>
        <target>
            <directory>squarepants/src/test/java</directory>
            <packageName>com.squareup.squarepants.integration.jooq.model</packageName>
        </target>
        <database>
            <name>org.jooq.util.mysql.MySQLDatabase</name>
            <inputSchema>squarepants_jooq_integration_test</inputSchema>
            <excludes>
                GOLD_FISH
            </excludes>
            <outputSchema>exemplardb</outputSchema>
            <recordVersionFields>version</recordVersionFields>
        </database>
    </generator>
    <jdbc>
        <driver>com.mysql.jdbc.Driver</driver>
        <url>jdbc:mysql://localhost/squarepants_jooq_integration_test</url>
        <user>root</user>
        <password />
    </jdbc>
</configuration>'''.strip())
    tree_two = ElementTree.fromstring('''
<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<configuration>
    <generator>
        <name>replacement generator</name>
        <target>
            <packageName>my package</packageName>
        </target>
        <database>
            <name>cool database class</name>
            <excludes>
                HELLO_THERE
            </excludes>
            <outputSchema>hellodb</outputSchema>
        </database>
    </generator>
    <jdbc>
        <driver>my driver</driver>
    </jdbc>
</configuration>'''.strip())
    merged = PomFile._merge_jooq_config(tree_one, tree_two)
    self.assertEquals('replacement generator',
                      self._find_node_text(merged, ('generator', 'name')))
    self.assertEquals('my package',
                      self._find_node_text(merged, ('generator', 'target', 'packageName')))
    self.assertEquals('squarepants/src/test/java',
                      self._find_node_text(merged, ('generator', 'target', 'directory')))
    self.assertEquals('cool database class',
                      self._find_node_text(merged, ('generator', 'database', 'name')))
    self.assertEquals('version', self._find_node_text(merged, ('generator', 'database',
                                                               'recordVersionFields')))
    self.assertEquals('hellodb',
                      self._find_node_text(merged, ('generator', 'database', 'outputSchema')))
    self.assertEquals('my driver',
                      self._find_node_text(merged, ('jdbc', 'driver')))
    self.assertEquals('root',
                      self._find_node_text(merged, ('jdbc', 'user')))
