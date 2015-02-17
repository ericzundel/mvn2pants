# Tests for code in squarepants/src/main/python/squarepants/pom_handlers.py
#
# Run with:
# ./pants goal test squarepants/src/test/python/squarepants:pom_handlers

import os
import pytest
import shutil
from textwrap import dedent
from tempfile import mkdtemp
import xml.sax

import squarepants.pom_handlers

import unittest2 as unittest

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

DEPENDENCY_MANAGEMENT_POM=dedent('''<?xml version="1.0" encoding="UTF-8"?>
    <project xmlns="http://maven.apache.org/POM/4.0.0"
    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
    xsi:schemaLocation="http://maven.apache.org/POM/4.0.0
         http://maven.apache.org/xsd/maven-4.0.0.xsd">

      <groupId>com.example</groupId>
      <artifactId>base</artifactId>
      <description>A generic Square module.</description>
      <version>HEAD-SNAPSHOT</version>
      <packaging>pom</packaging>

      <properties>
        <test.version>1.9.5</test.version>
      </properties>

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

      <dependencyManagement>
        <dependencies>
          <dependency>
            <groupId>com.amazonaws</groupId>
            <artifactId>aws-java-sdk</artifactId>
            <version>${test.version}</version>
          </dependency>
            <dependency>
              <groupId>io.dropwizard</groupId>
              <artifactId>dropwizard-auth</artifactId>
              <version>8.7.6</version>
              <exclusions>
                <!-- Brings in a mess of deps, including logback. -->
                <exclusion>
                  <groupId>io.dropwizard</groupId>
                  <artifactId>dropwizard-core</artifactId>
                </exclusion>
              </exclusions>
            </dependency>
        </dependencies>
      </dependencyManagement>

      <dependencies>
        <dependency>
          <groupId>com.example</groupId>
          <artifactId>testing-support</artifactId>
          <scope>test</scope>
        </dependency>
      </dependencies>

      <distributionManagement>
        <repository>
          <id>deployment</id>
          <name>Internal Releases</name>
          <url>https://nexus.example.com/content/repositories/releases/</url>
        </repository>
        <snapshotRepository>
          <id>deployment</id>
          <name>Internal Snapshots</name>
          <url>https://nexus.example.com/content/repositories/snapshots/</url>
        </snapshotRepository>
      </distributionManagement>
    </project>''')

DEPENDENCY_POM=dedent('''<?xml version="1.0" encoding="UTF-8"?>
    <project xmlns="http://maven.apache.org/POM/4.0.0"
    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
    xsi:schemaLocation="http://maven.apache.org/POM/4.0.0
         http://maven.apache.org/xsd/maven-4.0.0.xsd">

      <groupId>com.example</groupId>
      <artifactId>service</artifactId>
      <description>A generic Square module.</description>
      <version>HEAD-SNAPSHOT</version>
      <packaging>pom</packaging>

      <properties>
        <jhdf5.version>2.3.4</jhdf5.version>
      </properties>

      <parent>
        <groupId>com.example</groupId>
        <artifactId>parent</artifactId>
        <version>HEAD-SNAPSHOT</version>
        <relativePath>../pom.xml</relativePath>
      </parent>

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

      <dependencies>
        <dependency>
          <groupId>com.google.guava</groupId>
          <artifactId>guava</artifactId>
        </dependency>
        <dependency>
          <groupId>com.squareup.nonmaven.hdfgroup.hdf-java</groupId>
          <artifactId>jhdf5</artifactId>
          <version>${jhdf5.version}</version>
        </dependency>
        <dependency>
          <groupId>io.dropwizard</groupId>
          <artifactId>dropwizard-auth</artifactId>
          <version>4.5.6</version>
          <exclusions>
            <!-- Brings in a mess of deps, including logback. -->
            <exclusion>
              <groupId>io.dropwizard</groupId>
              <artifactId>dropwizard-core</artifactId>
            </exclusion>
          </exclusions>
        </dependency>
      </dependencies>
    </project>''')


class PomHandlerTest(unittest.TestCase):
  def test_pom_content_handler(self):
    handler =  squarepants.pom_handlers.PomContentHandler()
    xml.sax.parseString(ROOT_POM, handler)
    self.assertEquals('com.example', handler.groupId)
    self.assertEquals('top', handler.artifactId)
    self.assertEquals('FOO', handler.properties['prop.foo'])
    self.assertEquals('BAR', handler.properties['prop.bar'])
    self.assertEquals('${prop.foo}-BAZ', handler.properties['prop.baz'])
    self.assertEquals('FOO', handler.resolveProperties('${prop.foo}'))
    self.assertEquals('FOOBAR', handler.resolveProperties('${prop.foo}${prop.bar}'))
    self.assertEquals('FOO-BAZ', handler.resolveProperties('${prop.baz}'))
    self.assertEquals([{'key1' : 'key1-FOO'},
                       {'key2' : 'key2-BAR'}],
                      handler.resolveDependencyProperties([{'key1' : 'key1-${prop.foo}'},
                                                           {'key2' : 'key2-${prop.bar}'}]))

  def test_top_pom_content_handler(self):
    handler = squarepants.pom_handlers.TopPomContentHandler()
    xml.sax.parseString(ROOT_POM, handler)
    self.assertEquals('com.example', handler.groupId)
    self.assertEquals('top', handler.artifactId)
    self.assertEquals('FOO', handler.properties['prop.foo'])
    self.assertEquals(['foo', 'bar'], handler.modules)

  def test_dmf_pom_content_handler(self):
    handler = squarepants.pom_handlers._DMFPomContentHandler()
    xml.sax.parseString(DEPENDENCY_MANAGEMENT_POM, handler)

    self.assertEquals('com.example', handler.groupId)
    self.assertEquals('base', handler.artifactId)
    self.assertEquals(2, len(handler.dependency_management))
    self.assertEquals({u'groupId' : 'com.amazonaws',
                       u'artifactId' : 'aws-java-sdk',
                       u'version' : '${test.version}',
                       u'exclusions' : []
                      }, handler.dependency_management[0])


    self.assertEquals({ u'groupId' : 'io.dropwizard',
                        u'artifactId' : 'dropwizard-auth',
                        u'version' : '8.7.6',
                        u'exclusions' : [
                          {
                            u'groupId' : 'io.dropwizard',
                            u'artifactId' : 'dropwizard-core'
                          }
                        ]
                      }, handler.dependency_management[1])

  def test_df_pom_content_handler(self):
    handler = squarepants.pom_handlers._DFPomContentHandler()
    xml.sax.parseString(DEPENDENCY_POM, handler)

    self.assertEquals('com.example', handler.groupId)
    self.assertEquals('service', handler.artifactId)
    self.assertEquals('com.example', handler.parent['groupId'])
    self.assertEquals('parent', handler.parent['artifactId'])
    self.assertEquals(4, len(handler.dependencies))

    self.assertEquals({u'groupId' : 'com.example',
                       u'artifactId' : 'parent',
                       u'relativePath' : '../pom.xml',
                       u'version' : 'HEAD-SNAPSHOT',
                      }, handler.dependencies[0])
    self.assertEquals({u'groupId' : 'com.google.guava',
                       u'artifactId' : 'guava',
                       u'exclusions' : []
                      }, handler.dependencies[1])

    # this one has property substitution which doesn't occur until DependencyFinder
    self.assertEquals({u'groupId' : 'com.squareup.nonmaven.hdfgroup.hdf-java',
                       u'artifactId' : 'jhdf5',
                       u'version' : '${jhdf5.version}',
                       u'exclusions' : []
                      }, handler.dependencies[2])

    self.assertEquals({ u'groupId' : 'io.dropwizard',
                        u'artifactId' : 'dropwizard-auth',
                        u'version' : '4.5.6',
                        u'exclusions' : [
                          {
                            u'groupId' : 'io.dropwizard',
                            u'artifactId' : 'dropwizard-core'
                          }
                        ]
                      }, handler.dependencies[3])

  def test_dependency_finder(self):
    tmpdir = mkdtemp()
    try:
      with open(os.path.join(tmpdir, 'pom.xml') , 'w') as pomfile:
        pomfile.write(DEPENDENCY_POM)
      df = squarepants.pom_handlers.DependencyFinder(rootdir=tmpdir)
      deps = df.find_dependencies('pom.xml')

      self.assertEquals('com.example', df.groupId)
      self.assertEquals('service', df.artifactId)

      self.assertEquals(4, len(deps))
      self.assertEquals({u'groupId' : 'com.example',
                         u'artifactId' : 'parent',
                         u'relativePath' : '../pom.xml',
                         u'version' : 'HEAD-SNAPSHOT',
                         }, deps[0])
      self.assertEquals({u'groupId' : 'com.google.guava',
                         u'artifactId' : 'guava',
                         u'exclusions' : []
                        }, deps[1])
      # this one has property substitution which doesn't occur until DependencyFinder
      self.assertEquals({u'groupId' : 'com.squareup.nonmaven.hdfgroup.hdf-java',
                         u'artifactId' : 'jhdf5',
                         u'version' : '2.3.4',
                         u'exclusions' : []
                        }, deps[2])

      self.assertEquals({ u'groupId' : 'io.dropwizard',
                          u'artifactId' : 'dropwizard-auth',
                          u'version' : '4.5.6',
                          u'exclusions' : [
                            {
                              u'groupId' : 'io.dropwizard',
                              u'artifactId' : 'dropwizard-core'
                            }
                          ]
                        }, deps[3])
    finally:
      shutil.rmtree(tmpdir)


  def test_dependency_managment_finder(self):
    tmpdir = mkdtemp()
    try:
      with open(os.path.join(tmpdir, 'pom.xml') , 'w') as pomfile:
        pomfile.write(DEPENDENCY_MANAGEMENT_POM)
      dmf = squarepants.pom_handlers.DependencyManagementFinder(rootdir=tmpdir)
      deps = dmf.find_dependencies('pom.xml')

      self.assertEquals(2, len(deps))
      self.assertEquals({u'groupId' : 'com.amazonaws',
                         u'artifactId' : 'aws-java-sdk',
                         u'version' : '1.9.5',
                         u'exclusions' : []
                        }, deps[0])


      self.assertEquals({ u'groupId' : 'io.dropwizard',
                          u'artifactId' : 'dropwizard-auth',
                          u'version' : '8.7.6',
                          u'exclusions' : [
                            {
                              u'groupId' : 'io.dropwizard',
                              u'artifactId' : 'dropwizard-core'
                            }
                          ]
                        }, deps[1])

    finally:
      shutil.rmtree(tmpdir)

  @pytest.mark.xfail
  def test_pom_provides_target(self):
    # TODO(zundel): Not implemented
    raise Exception()

  @pytest.mark.xfail
  def test_deps_from_pom(self):
    # TODO(zundel): Not implemented
    raise Exception()

  @pytest.mark.xfail
  def test_local_targets(self):
    # TODO(zundel): Not implemented
    raise Exception()
