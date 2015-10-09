# Tests for code in squarepants/src/main/python/squarepants/pom_handlers.py
#
# Run with:
# ./pants test squarepants/src/test/python/squarepants_test:pom_handlers

import os
import StringIO
from textwrap import dedent
import unittest

from squarepants.pom_properties import PomProperties
from squarepants.pom_utils import PomUtils
from squarepants.file_utils import temporary_dir

class TestPomProperties(unittest.TestCase):
  def setUp(self):
    PomUtils.reset_caches()

  def test_safe_property_name(self):
    pp = PomProperties()
    self.assertEquals('Foo_Bar', pp.safe_property_name('Foo Bar'))
    self.assertEquals('foo_bar', pp.safe_property_name('foo.bar'))
    self.assertEquals('foo_bar', pp.safe_property_name('foo-bar'))
    self.assertEquals('foo_bar', pp.safe_property_name('foo$bar'))

  def test_pom_properties(self):
    with temporary_dir() as tmpdir:
      with open(os.path.join(tmpdir, 'pom.xml') , 'w') as pomfile:
        pomfile.write(dedent('''<?xml version="1.0" encoding="UTF-8"?>
  <project xmlns="http://maven.apache.org/POM/4.0.0"
  xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
  xsi:schemaLocation="http://maven.apache.org/POM/4.0.0
       http://maven.apache.org/xsd/maven-4.0.0.xsd">

    <groupId>com.example</groupId>
    <artifactId>base</artifactId>
    <version>HEAD-SNAPSHOT</version>

    <properties>
      <base.prop>FOO</base.prop>
      <base.overridden>BASE</base.overridden>
    </properties>
  </project>
'''))
      child_path_name = os.path.join(tmpdir, 'child')
      os.mkdir(child_path_name)
      child_pom_name = os.path.join(child_path_name, 'pom.xml')
      with open(child_pom_name, 'w') as child_pomfile:
        child_pomfile.write(dedent('''<?xml version="1.0" encoding="UTF-8"?>
<project xmlns="http://maven.apache.org/POM/4.0.0"
xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
xsi:schemaLocation="http://maven.apache.org/POM/4.0.0 http://maven.apache.org/xsd/maven-4.0.0.xsd">

  <groupId>com.example</groupId>
  <artifactId>child</artifactId>
  <description>A generic Square module.</description>
  <version>HEAD-SNAPSHOT</version>

  <parent>
    <groupId>com.example</groupId>
    <artifactId>base</artifactId>
    <version>HEAD-SNAPSHOT</version>
    <relativePath>../pom.xml</relativePath>
  </parent>

  <properties>
    <child.prop1>BAR</child.prop1>
    <child.prop2>base is ${base.prop}</child.prop2>
    <base.overridden>CHILD</base.overridden>
  </properties>

</project>
'''))
      buffer = StringIO.StringIO()

      PomProperties().write_properties('child/pom.xml', buffer, rootdir=tmpdir)
      properties=set()
      for line in buffer.getvalue().split('\n'):
        properties.add(line)

      self.assertIn('base_prop="FOO"', properties)
      self.assertIn('child_prop1="BAR"', properties)
      self.assertIn('child_prop2="base is FOO"', properties)
      self.assertIn('base_overridden="CHILD"', properties)
      self.assertIn('project_artifactId="child"', properties)
      self.assertIn('project_groupId="com.example"', properties)
