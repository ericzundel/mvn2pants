# Tests for code in squarepants/src/main/python/squarepants/pom_handlers.py
#
# Run with:
# ./pants test squarepants/src/test/python/squarepants_test:pom_handlers

import os
import pytest
from textwrap import dedent
import unittest2 as unittest
import xml.sax
import logging

import squarepants.pom_handlers
from squarepants.pom_utils import PomUtils
from squarepants.file_utils import temporary_dir


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
          <classifier>shaded</classifier>
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

  def setUp(self):
    PomUtils.reset_caches()
    logging.basicConfig()

  def test_pom_content_handler(self):
    handler =  squarepants.pom_handlers.PomContentHandler()
    xml.sax.parseString(ROOT_POM, handler)
    self.assertEquals('com.example', handler.groupId)
    self.assertEquals('top', handler.artifactId)
    self.assertEquals('FOO', handler.properties['prop.foo'])
    self.assertEquals('BAR', handler.properties['prop.bar'])
    self.assertEquals('${prop.foo}-BAZ', handler.properties['prop.baz'])

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

    # This one has property substitution which doesn't occur until DependencyInfo processes it.
    self.assertEquals({u'groupId' : 'com.squareup.nonmaven.hdfgroup.hdf-java',
                       u'artifactId' : 'jhdf5',
                       u'version' : '${jhdf5.version}',
                       u'exclusions' : []
                      }, handler.dependencies[2])

    self.assertEquals({ u'groupId' : 'io.dropwizard',
                        u'artifactId' : 'dropwizard-auth',
                        u'version' : '4.5.6',
                        u'classifier' : 'shaded',
                        u'exclusions' : [
                          {
                            u'groupId' : 'io.dropwizard',
                            u'artifactId' : 'dropwizard-core'
                          }
                        ]
                      }, handler.dependencies[3])

  def test_dependency_finder(self):
    with temporary_dir() as tmpdir:
      with open(os.path.join(tmpdir, 'pom.xml') , 'w') as pomfile:
        pomfile.write(DEPENDENCY_POM)
      df = squarepants.pom_handlers.DependencyInfo('pom.xml', rootdir=tmpdir)
      self.assertEquals('com.example', df.groupId)
      self.assertEquals('service', df.artifactId)
      self.assertEquals('2.3.4', df.properties['jhdf5.version'])

      self.assertEquals(4, len(df.dependencies))
      self.assertEquals({u'groupId' : 'com.example',
                         u'artifactId' : 'parent',
                         u'relativePath' : '../pom.xml',
                         u'version' : 'HEAD-SNAPSHOT',
                         }, df.dependencies[0])
      self.assertEquals({u'groupId' : 'com.google.guava',
                         u'artifactId' : 'guava',
                         u'exclusions' : []
                        }, df.dependencies[1])
      # this one has property substitution which doesn't occur until DependencyInfo
      self.assertEquals({u'groupId' : 'com.squareup.nonmaven.hdfgroup.hdf-java',
                         u'artifactId' : 'jhdf5',
                         u'version' : '2.3.4',
                         u'exclusions' : []
                        }, df.dependencies[2])

      self.assertEquals({ u'groupId' : 'io.dropwizard',
                          u'artifactId' : 'dropwizard-auth',
                          u'version' : '4.5.6',
                          u'classifier' : 'shaded',
                          u'exclusions' : [
                            {
                              u'groupId' : 'io.dropwizard',
                              u'artifactId' : 'dropwizard-core'
                            }
                          ]
                        }, df.dependencies[3])


  def test_dependency_managment_finder(self):
    with temporary_dir() as tmpdir:
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

  def test_include_parent_deps(self):
    with temporary_dir() as tmpdir:
      with open(os.path.join(tmpdir, 'pom.xml') , 'w') as pomfile:
        pomfile.write(dedent('''<?xml version="1.0" encoding="UTF-8"?>
          <project xmlns="http://maven.apache.org/POM/4.0.0"
          xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
          xsi:schemaLocation="http://maven.apache.org/POM/4.0.0
               http://maven.apache.org/xsd/maven-4.0.0.xsd">

            <groupId>com.example</groupId>
            <artifactId>base</artifactId>
            <description>A generic Square module.</description>
            <version>HEAD-SNAPSHOT</version>
            <dependencies>
              <dependency>
                <groupId>com.example</groupId>
                <artifactId>parent-dep</artifactId>
                <version>HEAD-SNAPSHOT</version>
              </dependency>
                <groupId>com.example</groupId>
                <artifactId>child-dep</artifactId>
                <version>OVERRIDDEN-VERSION</version>
              <dependency>
              </dependency>
            </dependencies>
          </project>
        '''))
      child_path_name = os.path.join(tmpdir, 'child')
      os.mkdir(child_path_name)
      child_pom_name = os.path.join(child_path_name, 'pom.xml')
      with open(child_pom_name, 'w') as child_pomfile:
        child_pomfile.write(dedent('''<?xml version="1.0" encoding="UTF-8"?>
          <project xmlns="http://maven.apache.org/POM/4.0.0"
          xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
          xsi:schemaLocation="http://maven.apache.org/POM/4.0.0
               http://maven.apache.org/xsd/maven-4.0.0.xsd">

            <groupId>com.example</groupId>
            <artifactId>child</artifactId>
            <description>A generic Square module.</description>
            <version>HEAD-SNAPSHOT</version>

            <parent>
              <groupId>com.example</groupId>
              <artifactId>parent</artifactId>
              <version>HEAD-SNAPSHOT</version>
              <relativePath>../pom.xml</relativePath>
            </parent>

            <dependencies>
              <dependency>
                <groupId>com.example</groupId>
                <artifactId>child-dep</artifactId>
                <version>HEAD-SNAPSHOT</version>
              </dependency>
            </dependencies>
          </project>
        '''))

      child2_path_name = os.path.join(tmpdir, 'child2')
      os.mkdir(child2_path_name)
      child2_pom_name = os.path.join(child2_path_name, 'pom.xml')
      with open(child2_pom_name, 'w') as child2_pomfile:
        child2_pomfile.write(dedent('''<?xml version="1.0" encoding="UTF-8"?>
            <project xmlns="http://maven.apache.org/POM/4.0.0"
            xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
            xsi:schemaLocation="http://maven.apache.org/POM/4.0.0
                 http://maven.apache.org/xsd/maven-4.0.0.xsd">

              <groupId>com.example</groupId>
              <artifactId>child</artifactId>
              <description>A generic Square module.</description>
              <version>HEAD-SNAPSHOT</version>

              <parent>
                <groupId>com.example</groupId>
                <artifactId>child</artifactId>
                <version>HEAD-SNAPSHOT</version>
                <relativePath>../child/pom.xml</relativePath>
              </parent>

              <dependencies>
                <dependency>
                  <groupId>com.example</groupId>
                  <artifactId>child2-dep</artifactId>
                  <version>HEAD-SNAPSHOT</version>
                </dependency>
              </dependencies>
            </project>
          '''))

      df = squarepants.pom_handlers.DependencyInfo('child2/pom.xml', rootdir=tmpdir)

      self.assertEquals({u'groupId' : 'com.example',
                         u'artifactId' : 'child',
                         u'relativePath' : '../child/pom.xml',
                         u'version' : 'HEAD-SNAPSHOT',
                         }, df.dependencies[0])
      self.assertEquals({u'groupId' : 'com.example',
                         u'artifactId' : 'child2-dep',
                         u'version' : 'HEAD-SNAPSHOT',
                         u'exclusions' : []
                        }, df.dependencies[1])
      self.assertEquals({u'groupId' : 'com.example',
                         u'artifactId' : 'parent',
                         u'relativePath' : '../pom.xml',
                         u'version' : 'HEAD-SNAPSHOT',
                         }, df.dependencies[2])
      self.assertEquals({u'groupId' : 'com.example',
                         u'artifactId' : 'child-dep',
                         u'version' : 'HEAD-SNAPSHOT',
                         u'exclusions' : []
                        }, df.dependencies[3])
      self.assertEquals({u'groupId' : 'com.example',
                         u'artifactId' : 'parent-dep',
                         u'version' : 'HEAD-SNAPSHOT',
                         u'exclusions' : []
                        }, df.dependencies[4])

      self.assertEquals(5, len(df.dependencies))

  def test_dependency_finder_parent_properties(self):
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
      df = squarepants.pom_handlers.DependencyInfo('child/pom.xml', rootdir=tmpdir)
      self.assertEquals('FOO', df.properties['base.prop'])
      self.assertEquals('BAR', df.properties['child.prop1'])
      self.assertEquals('base is FOO', df.properties['child.prop2'])
      self.assertEquals('CHILD', df.properties['base.overridden'])

  def test_type_test_jar(self):
    with temporary_dir() as tmpdir:
      with open(os.path.join(tmpdir, 'pom.xml') , 'w') as pomfile:
        pomfile.write(dedent('''<?xml version="1.0" encoding="UTF-8"?>
        <project xmlns="http://maven.apache.org/POM/4.0.0"
        xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
        xsi:schemaLocation="http://maven.apache.org/POM/4.0.0
             http://maven.apache.org/xsd/maven-4.0.0.xsd">

          <groupId>com.example</groupId>
          <artifactId>base</artifactId>
          <description>A generic Square module.</description>
          <version>HEAD-SNAPSHOT</version>
          <dependencies>
            <dependency>
              <groupId>com.example</groupId>
              <artifactId>dep1</artifactId>
              <type>foo</type>
              <version>1.0</version>
            </dependency>
            <dependency>
              <groupId>com.example</groupId>
              <artifactId>dep2</artifactId>
              <type>test-jar</type>
              <version>1.2.3</version>
            </dependency>
          </dependencies>
        </project>
      '''))

      # TODO(Eric Ayers): Right now, our builds expect a file in <rootdir>/parents/base/pom.xml
      os.makedirs(os.path.join(tmpdir, 'parents', 'base'))
      with open(os.path.join(tmpdir, 'parents', 'base', 'pom.xml'), 'w') as dep_mgmt_pom:
        dep_mgmt_pom.write(DEPENDENCY_MANAGEMENT_POM)

      df = squarepants.pom_handlers.DependencyInfo('pom.xml', rootdir=tmpdir)
      self.assertEquals({u'groupId' : 'com.example',
                         u'artifactId' : 'dep1',
                         u'type' : 'foo',
                         u'exclusions' : [],
                         u'version' : '1.0'
                         }, df.dependencies[0])
      self.assertEquals({u'groupId' : 'com.example',
                         u'artifactId' : 'dep2',
                         u'type' : 'test-jar',
                         u'exclusions' : [],
                         u'version' : '1.2.3'
                         }, df.dependencies[1])
      self.assertEquals(2, len(df.dependencies))

      deps_from_pom = squarepants.pom_handlers.DepsFromPom(PomUtils.pom_provides_target(),
                                                           rootdir=tmpdir)
      refs = deps_from_pom.build_pants_refs(df.dependencies)
      self.assertEquals("sjar(org='com.example', name='dep1', rev='1.0', ext='foo',)", refs[0])
      # type test-jar gets transformed into a 'tests' classifier
      self.assertEquals("sjar(org='com.example', name='dep2', rev='1.2.3', classifier='tests',)", refs[1])
      self.assertEquals(2, len(refs))

  def test_wire_info(self):
    with temporary_dir() as tmpdir:
      with open(os.path.join(tmpdir, 'pom.xml'), 'w') as pomfile:
        pomfile.write(dedent('''<?xml version="1.0" encoding="UTF-8"?>
            <project xmlns="http://maven.apache.org/POM/4.0.0"
                xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
                xsi:schemaLocation="http://maven.apache.org/POM/4.0.0 http://maven.apache.org/xsd/maven-4.0.0.xsd">
              <modelVersion>4.0.0</modelVersion>
              <build>
                <plugins>
                  <plugin>
                    <groupId>org.apache.maven.plugins</groupId>
                    <artifactId>maven-dependency-plugin</artifactId>
                    <executions>
                      <execution>
                        <id>unpack</id>
                        <phase>initialize</phase>
                        <goals>
                          <goal>unpack</goal>
                        </goals>
                        <configuration>
                          <artifactItems>
                            <artifactItem>
                              <groupId>com.squareup.protos</groupId>
                              <artifactId>all-protos</artifactId>
                              <overWrite>true</overWrite>
                              <outputDirectory>${project.build.directory}/../src/main/wire_proto</outputDirectory>
                              <includes>squareup/xp/validation.proto,squareup/xp/oauth/**,squareup/xp/v1/common.proto,squareup/xp/v1/http.proto</includes>
                            </artifactItem>
                            <artifactItem>
                              <groupId>com.google.protobuf</groupId>
                              <artifactId>protobuf-java</artifactId>
                              <overWrite>true</overWrite>
                              <outputDirectory>${project.build.directory}/../src/main/wire_proto</outputDirectory>
                              <includes>**/descriptor.proto</includes>
                            </artifactItem>
                          </artifactItems>
                        </configuration>
                      </execution>
                    </executions>
                  </plugin>
                  <plugin>
                    <groupId>com.squareup.wire</groupId>
                    <artifactId>wire-maven-plugin</artifactId>
                    <executions>
                      <execution>
                        <goals>
                          <goal>generate-sources</goal>
                        </goals>
                        <phase>generate-sources</phase>
                      </execution>
                    </executions>
                    <configuration>
                      <noOptions>true</noOptions>
                      <serviceFactory>com.squareup.wire.java.SimpleServiceFactory</serviceFactory>
                      <serviceFactory>com.squareup.wire.java.SimpleServiceFactory</serviceFactory>
                      <protoFiles>
                        <protoFile>squareup/protobuf/rpc/rpc.proto</protoFile>
                        <protoFile>squareup/sake/wire_format.proto</protoFile>
                      </protoFiles>
                      <roots>
                        <root>squareup.franklin.settings.UnlinkSmsRequest</root>
                        <root>squareup.franklin.settings.VerifyEmailRequest</root>
                      </roots>
                    </configuration>
                  </plugin>
                </plugins>
              </build>
            </project>
        '''))
      wf = squarepants.pom_handlers.WireInfo.from_pom('pom.xml', rootdir=tmpdir)
      self.assertEquals(True, wf.no_options)
      self.assertEquals(['squareup/protobuf/rpc/rpc.proto', 'squareup/sake/wire_format.proto'], wf.protos)
      self.assertEquals(['squareup.franklin.settings.UnlinkSmsRequest', 'squareup.franklin.settings.VerifyEmailRequest'], wf.roots)
      self.assertEquals([], wf.enum_options)
      self.assertEquals('com.squareup.wire.java.SimpleServiceFactory', wf.service_factory)
      self.assertEquals(None, wf.registry_class)
      self.assertEquals(set([('com.squareup.protos', 'all-protos',), ('com.google.protobuf', 'protobuf-java',),]), set(wf.artifacts))
      self.assertEquals('**/descriptor.proto', wf.artifacts[('com.google.protobuf', 'protobuf-java',)]['includes'])

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

  def test_parse_shading_rules(self):
    def assert_rule_text(expected, from_pattern, to_pattern):
      received = squarepants.pom_handlers.ShadingInfo.Rule(from_pattern, to_pattern).text
      self.assertEquals(expected, received)

    assert_rule_text("shading_relocate_package('com.foobar.example', shade_prefix='potato.')",
                     'com.foobar.example.', 'potato.com.foobar.example.')

    assert_rule_text("shading_relocate('com.foobar.example.**', 'org.faabor.elpmaxe.@1')",
                     'com.foobar.example.', 'org.faabor.elpmaxe.')

    assert_rule_text("shading_relocate('com.foo.bar.Main', 'org.bar.foo.Sane')",
                     'com.foo.bar.Main', 'org.bar.foo.Sane')
