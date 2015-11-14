# Tests for code in squarepants/src/main/python/squarepants/pom_file.py
#
# Run with:
# ./pants test squarepants/src/test/python/squarepants_test:pom_file

import os
import pytest
import unittest2 as unittest

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
