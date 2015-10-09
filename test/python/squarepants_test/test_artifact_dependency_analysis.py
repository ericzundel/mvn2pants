# Tests for code in squarepants/src/main/python/squarepants/artifact_dependency_analysis
#
# Run with:
# ./pants test squarepants/src/test/python/squarepants_test:artifact_dependency_analysis

from collections import namedtuple
from contextlib import contextmanager
import os
import subprocess
import unittest2 as unittest

from squarepants.artifact_dependency_analysis import ArtifactDependencyAnalysis
from squarepants.pom_utils import PomUtils
from squarepants.file_utils import temporary_dir


RunResult = namedtuple('RunResult', ['returncode', 'stdout', 'stderr'])


class ArtifactDependencyAnalysisTest(unittest.TestCase):

  def setUp(self):
    self._orig_wd = os.getcwd()
    os.chdir(self.REPO_ROOT)
    PomUtils.reset_caches()

  def tearDown(self):
    os.chdir(self._orig_wd)

  # NB(zundel): assumes this file lives at squarepants/src/test/python/squarepants_test
  REPO_ROOT=(os.path.abspath('{}/../../../../../'.format(os.path.dirname(__file__))))

  def run_cmd(self, cmd):
    process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    stdout, stderr = process.communicate()
    return RunResult(stderr=stderr, stdout=stdout, returncode=process.returncode)

  @contextmanager
  def make_sample_repo(self):
    with temporary_dir() as tmpdir:
      with open(os.path.join(tmpdir, 'pom.xml'), 'w') as root_pom:
        root_pom_data = """<?xml version='1.0' encoding='UTF-8'?>
<project xsi:schemaLocation='http://maven.apache.org/POM/4.0.0 http://maven.apache.org/xsd/maven-4.0.0.xsd' xmlns='http://maven.apache.org/POM/4.0.0' xmlns:xsi='http://www.w3.org/2001/XMLSchema-instance'>
  <modelVersion>4.0.0</modelVersion>

  <groupId>com.squareup.foo</groupId>
  <artifactId>all</artifactId>
  <version>HEAD-SNAPSHOT</version>

  <modules>
    <module>foo-service</module>
  </modules>
</project>
"""
        root_pom.write(root_pom_data)

      os.makedirs(os.path.join(tmpdir, 'parents', 'base'))
      with open(os.path.join(tmpdir, 'parents', 'base', 'pom.xml'), 'w') as base_pom_file:
        base_pom_data = """<?xml version='1.0' encoding='UTF-8'?>
<project xsi:schemaLocation='http://maven.apache.org/POM/4.0.0 http://maven.apache.org/xsd/maven-4.0.0.xsd' xmlns='http://maven.apache.org/POM/4.0.0' xmlns:xsi='http://www.w3.org/2001/XMLSchema-instance'>
  <modelVersion>4.0.0</modelVersion>

  <groupId>com.squareup.foo</groupId>
  <artifactId>foo-base</artifactId>
  <version>HEAD-SNAPSHOT</version>

  <dependencyManagement>
  </dependencyManagement>
</project>
"""
        base_pom_file.write(base_pom_data)
      os.mkdir(os.path.join(tmpdir, 'foo-service'))
      with open(os.path.join(tmpdir, 'foo-service', 'pom.xml'), 'w') as pom_file:
        pom_data = """<?xml version='1.0' encoding='UTF-8'?>
<project xsi:schemaLocation='http://maven.apache.org/POM/4.0.0 http://maven.apache.org/xsd/maven-4.0.0.xsd' xmlns='http://maven.apache.org/POM/4.0.0' xmlns:xsi='http://www.w3.org/2001/XMLSchema-instance'>
  <modelVersion>4.0.0</modelVersion>

  <groupId>com.squareup.foo</groupId>
  <artifactId>foo-service</artifactId>
  <version>HEAD-SNAPSHOT</version>

  <parent>
    <groupId>com.squareup.foo</groupId>
    <artifactId>foo-base</artifactId>
    <version>HEAD-SNAPSHOT</version>
    <relativePath>../parents/base/pom.xml</relativePath>
  </parent>

  <dependencies>
    <dependency>
      <groupId>com.squareup.service</groupId>
      <artifactId>container</artifactId>
      <version>1.2.3</version>
    </dependency>
  </dependencies>
</project>
"""
        pom_file.write(pom_data)
      yield tmpdir

  def test_produced_artifacts(self):
    with self.make_sample_repo() as sample_repo:
      self.assertEquals(set( [('com.squareup.foo', 'all'),
                              ('com.squareup.foo', 'foo-base'),
                              ('com.squareup.foo', 'foo-service')]),
                        ArtifactDependencyAnalysis(sample_repo).produced_artifacts)

  def test_consumed_artifacts(self):
    with self.make_sample_repo() as sample_repo:
      consumed_artifacts = ArtifactDependencyAnalysis(sample_repo).consumed_artifacts
      # Why is consumed_artifacts returning foo-base as consumed?
      # Why doesn't it return the service container artifact?
      # In debugging, it looks like foo-service isn't returning it as a dependency.
      self.assertEquals(set([('com.squareup.service', 'container'),
                             ('com.squareup.foo', 'foo-base')]),
                        consumed_artifacts)

  # A simple test that just makes sure the class compiles and runs in the Java repo
  def test_one_repo(self):
    ArtifactDependencyAnalysis.print_repo_summary(os.path.abspath(self.REPO_ROOT))

  # A simple test that make sures the class compiles and runs
  def test_two_repos(self):
    with self.make_sample_repo() as sample_repo:
      ArtifactDependencyAnalysis.print_repo_comparison(os.path.abspath(self.REPO_ROOT), sample_repo)

  def test_cmd_line_no_args(self):
    run_result = self.run_cmd(['squarepants/bin/analyze-repo-artifacts'])
    self.assertEquals(0, run_result.returncode, msg=run_result.stderr)
    self.assertIn('org.hibernate.javax.persistence', run_result.stdout)

  def test_cmd_line_summary(self):
    run_result = self.run_cmd(['{}/squarepants/bin/analyze-repo-artifacts'.format(self.REPO_ROOT),
                              '--repo-dir={}'.format(self.REPO_ROOT)])
    self.assertEquals(0, run_result.returncode, msg=run_result.stderr)
    self.assertIn('org.hibernate.javax.persistence', run_result.stdout)

  def test_cmd_line_compare(self):
    with self.make_sample_repo() as sample_repo:
      run_result = self.run_cmd(['squarepants/bin/analyze-repo-artifacts',
                                 '--repo-dir=.',
                                 '--other-repo-dir={}'.format(sample_repo)])
      self.assertEquals(0, run_result.returncode, msg=run_result.stderr)
      self.assertIn('com.squareup.service, container', run_result.stdout)


  @contextmanager
  def make_other_repo(self):
    with temporary_dir() as tmpdir:
      with open(os.path.join(tmpdir, 'pom.xml'), 'w') as root_pom:
        root_pom_data = """<?xml version='1.0' encoding='UTF-8'?>
<project xsi:schemaLocation='http://maven.apache.org/POM/4.0.0 http://maven.apache.org/xsd/maven-4.0.0.xsd' xmlns='http://maven.apache.org/POM/4.0.0' xmlns:xsi='http://www.w3.org/2001/XMLSchema-instance'>
  <modelVersion>4.0.0</modelVersion>

  <groupId>com.squareup.bar</groupId>
  <artifactId>all</artifactId>
  <version>HEAD-SNAPSHOT</version>

  <modules>
    <module>bar-service</module>
  </modules>
</project>
"""
        root_pom.write(root_pom_data)

      os.makedirs(os.path.join(tmpdir, 'parents', 'base'))
      with open(os.path.join(tmpdir, 'parents', 'base', 'pom.xml'), 'w') as base_pom_file:
        base_pom_data = """<?xml version='1.0' encoding='UTF-8'?>
<project xsi:schemaLocation='http://maven.apache.org/POM/4.0.0 http://maven.apache.org/xsd/maven-4.0.0.xsd' xmlns='http://maven.apache.org/POM/4.0.0' xmlns:xsi='http://www.w3.org/2001/XMLSchema-instance'>
  <modelVersion>4.0.0</modelVersion>

  <groupId>com.squareup.foo</groupId>
  <artifactId>bar-base</artifactId>
  <version>HEAD-SNAPSHOT</version>

  <dependencyManagement>
  </dependencyManagement>
</project>
"""
        base_pom_file.write(base_pom_data)
      os.mkdir(os.path.join(tmpdir, 'bar-service'))
      with open(os.path.join(tmpdir, 'bar-service', 'pom.xml'), 'w') as pom_file:
        pom_data = """<?xml version='1.0' encoding='UTF-8'?>
<project xsi:schemaLocation='http://maven.apache.org/POM/4.0.0 http://maven.apache.org/xsd/maven-4.0.0.xsd' xmlns='http://maven.apache.org/POM/4.0.0' xmlns:xsi='http://www.w3.org/2001/XMLSchema-instance'>
  <modelVersion>4.0.0</modelVersion>

  <groupId>com.squareup.foo</groupId>
  <artifactId>foo-service</artifactId>
  <version>HEAD-SNAPSHOT</version>

  <parent>
    <groupId>com.squareup.foo</groupId>
    <artifactId>bar-base</artifactId>
    <version>HEAD-SNAPSHOT</version>
    <relativePath>../parents/base/pom.xml</relativePath>
  </parent>

  <dependencies>
    <dependency>
      <groupId>com.squareup.foo</groupId>
      <artifactId>foo-service</artifactId>
      <version>1.2.3</version>
    </dependency>
  </dependencies>
</project>
"""
        pom_file.write(pom_data)
      yield tmpdir

  def test_two_repos_not_java(self):
    with self.make_sample_repo() as sample_repo:
      with self.make_other_repo() as other_repo:
        run_result = self.run_cmd(['squarepants/bin/analyze-repo-artifacts',
                                   '--repo-dir={sample_repo}'.format(sample_repo=sample_repo),
                                   '--other-repo-dir={other_repo}'.format(other_repo=other_repo)])
        self.assertEquals(0, run_result.returncode, msg=run_result.stderr)
        self.assertIn("com.squareup.foo, foo-service", run_result.stdout)



