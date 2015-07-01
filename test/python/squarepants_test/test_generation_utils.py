# Tests for code in squarepants/src/main/python/squarepants/generation_utils
#
# Run with:
# ./pants goal test squarepants/src/test/python/squarepants:generation_utils

import os
from textwrap import dedent
import unittest2 as unittest

from squarepants.pom_file import PomFile
from squarepants.generation_utils import GenerationUtils
from squarepants_test.test_utils import temporary_dir, reset_caches

class GenerationUtilsTest(unittest.TestCase):

  ROOT_POM=dedent('''<?xml version="1.0" encoding="UTF-8"?>
    <project xmlns="http://maven.apache.org/POM/4.0.0"
    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
    xsi:schemaLocation="http://maven.apache.org/POM/4.0.0
         http://maven.apache.org/xsd/maven-4.0.0.xsd">

    <properties>
      <prop.foo>FOO</prop.foo>
      <prop.bar>BAR</prop.bar>
      <prop.baz>${prop.foo}-BAZ</prop.baz>
    </properties>

    <groupId>com.example</groupId>
    <artifactId>top</artifactId>
    <version>HEAD-SNAPSHOT</version>
    <description>All your base are belong to us.</description>
    <packaging>pom</packaging>

    <repositories>
      <repository>
        <id>nexus</id>
        <url>https://nexus.example.com/content/groups/public/</url>
      </repository>
    </repositories>
    <pluginRepositories>
      <pluginRepository>
        <id>square-nexus</id>
        <url>https://nexus.example.com/content/groups/public/</url>
      </pluginRepository>
    </pluginRepositories>

    <scm>
      <url>https://git.example.com/repo</url>
      <connection>scm:git:https://git.examplecom/scm/repo/java.git</connection>
      <developerConnection>scm:git:ssh://git.example.com/repo/java.git</developerConnection>
    </scm>

    <prerequisites>
      <maven>3.0.1</maven>
    </prerequisites>

    <modules>
      <module>foo</module>
      <module>bar</module>
    </modules>
    <distributionManagement>
      <repository>
        <id>deployment</id>
        <name>Internal Releases</name>
        <url>https://nexus.example.com/content/repositories/releases/</url>
      </repository>
      <snapshotRepository>
        <id>deployment</id>
        <name>Internal Snapshots</name>
        <url>https://nexus.example.com/content/content/repositories/snapshots/</url>
      </snapshotRepository>
    </distributionManagement>
  </project>''')

  def setUp(self):
    self.maxDiff = None
    self._wd = os.getcwd()
    reset_caches()

  def tearDown(self):
    # Restore the working directory
    os.chdir(self._wd)

  def test_resolve_properties(self):
    substitute = GenerationUtils.symbol_substitution
    with temporary_dir() as tmpdir:
      with open(os.path.join(tmpdir, 'pom.xml'), 'w') as root_pom_file:
        root_pom_file.write(self.ROOT_POM)
      pom_file = PomFile('pom.xml', root_directory=tmpdir)
      self.assertEquals('FOOBAR', substitute(pom_file.properties, '${prop.foo}${prop.bar}'))
      self.assertEquals('FOO-BAZ', substitute(pom_file.properties, '${prop.baz}'))
      deps = [{'key1' : 'key1-${prop.foo}'},
              {'key2' : 'key2-${prop.bar}'}]

      deps = GenerationUtils.symbol_substitution_on_dicts(pom_file.properties, deps)
      self.assertEquals([{'key1' : 'key1-FOO'},
                         {'key2' : 'key2-BAR'}],
                        deps)