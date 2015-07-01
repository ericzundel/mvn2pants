#!/usr/bin/env python

from __future__ import print_function, with_statement

import os
import sys
from textwrap import dedent

from generation_context import GenerationContext
from pom_file import PomFile


class PomDetails(object):
  """Holds details about a pom.xml and the artifacts it references."""

  def __init__(self, pom_file_path, rootdir):
    self.project_name = os.path.dirname(os.path.relpath(pom_file_path, rootdir))
    self.path = pom_file_path
    self.pom_file = PomFile(pom_file_path, rootdir, GenerationContext())
    self.mainclass = self.pom_file.properties.get('project.mainclass')
    group_id = self.pom_file.deps_from_pom.group_id
    artifact_id = self.pom_file.deps_from_pom.artifact_id
    self.artifact = self.format_artifact(group_id, artifact_id) if group_id and artifact_id else None
    self.lib_dependencies, self.test_dependencies = self.pom_file.deps_from_pom.get(pom_file_path,
                                                                                    raw_deps=True)

  @property
  def produced_artifact(self):
    return self.artifact

  @property
  def consumed_artifacts(self):
    artifacts = set()
    for dep_list in (self.lib_dependencies, self.test_dependencies,):
      for dep in dep_list:
        if 'groupId' in dep and 'artifactId' in dep:
          artifacts.add(self.format_artifact(dep['groupId'], dep['artifactId']))
    return artifacts

  def format_artifact(self, group_id, artifact_id):
    return tuple([self.pom_file.apply_properties(item) for item in (group_id, artifact_id)])


class ArtifactDependencyAnalysis(object):
  """Analyzes the artifacts produced and consumed by repos build with Maven."""

  def __init__(self, repo_dir):
    self.repo_dir = repo_dir
    self._pom_details = {}
    self._all_poms = None

  @property
  def repo_name(self):
    return os.path.basename(self.repo_dir)

  @property
  def all_pom_paths(self):
    if self._all_poms is None:
      self._all_poms = []
      for root, dirs, files in os.walk(self.repo_dir):
        self._all_poms.extend([os.path.join(root, name) for name in files if name == 'pom.xml'])
    return self._all_poms

  @property
  def all_pom_details(self):
    return [self.pom_details(path) for path in self.all_pom_paths]

  def pom_details(self, pom_file_path):
    if pom_file_path not in self._pom_details:
      self._pom_details[pom_file_path] = PomDetails(pom_file_path, self.repo_dir)
    return self._pom_details[pom_file_path]

  @property
  def produced_artifacts(self):
    return {pom.produced_artifact for pom in self.all_pom_details if pom.artifact}

  @property
  def consumed_artifacts(self):
    return reduce(set.union, (pom.consumed_artifacts for pom in self.all_pom_details), set())

  @classmethod
  def _format_artifact_list(cls, artifacts):
    return '\n'.join('  {}, {}'.format(*artifact) for artifact in artifacts)

  @classmethod
  def print_repo_summary(cls, repo_dir):
    """Just prints a summary of the artifacts produced and consumed by the repo."""
    repo = cls(repo_dir)
    print('Artifacts Produced:')
    print(cls._format_artifact_list(repo.produced_artifacts))
    print()
    print('Artifacts Consumed:')
    print(cls._format_artifact_list(repo.consumed_artifacts))

  @classmethod
  def print_repo_comparison(cls, repo1_dir, repo2_dir):
    """Determines which artifacts are produced by one repo and consumed by the other."""
    repo1 = cls(repo1_dir)
    repo2 = cls(repo2_dir)

    print('Artifacts {} produces that {} consumes:'.format(repo1.repo_name, repo2.repo_name))
    one_to_two = set.intersection(repo1.produced_artifacts, repo2.consumed_artifacts)
    print(cls._format_artifact_list(one_to_two))

    print('Artifacts {} produces that {} consumes:'.format(repo2.repo_name, repo1.repo_name))
    two_to_one = set.intersection(repo1.consumed_artifacts, repo2.produced_artifacts)
    print(cls._format_artifact_list(two_to_one))


def clean_flag(flag):
  while flag.startswith('-'):
    flag = flag[1:]
  return flag.strip().replace('-', '_')


def split_flag(flag):
  flag = clean_flag(flag)
  if '=' in flag:
    return flag[:flag.find('=')], flag[flag.find('=')+1:]
  return flag, True

def parse_flags_and_args(raw_args):
  flags = {arg for arg in raw_args if arg.startswith('-')}
  args = [arg for arg in raw_args if arg not in flags]
  flags = dict(map(split_flag, flags))
  return args, flags


def print_usage():
  print(dedent('''
  Usage:

    - To print a summary of what artifacts a repo consumes (depends on) and produces:

        artifact_dependency_analysis.py <repo-directory>

      if <repo-directory> is omitted, the repository is assumed to be the current directory.


    - To print a comparison of the inter-relationships between two repositories (the artifacts one
      repo produces that the other consumes):

        artifact_dependency_analysis.py <repo1-directory> <repo2-directory>''').strip())


def main(*args, **flags):
  # TODO: switch to argparse.
  if any(h in flags for h in ('h', 'help', 'usage')):
    print_usage()
    return

  repo1_dir = os.path.abspath(args[0] if len(args)>0 else '.')
  repo2_dir = os.path.abspath(args[1] if len(args)>1 else None)

  if repo2_dir is None:
    ArtifactDependencyAnalysis.print_repo_summary(repo1_dir)
  else:
    ArtifactDependencyAnalysis.print_repo_comparison(repo1_dir, repo2_dir)


if __name__ == '__main__':
  args, flags = parse_flags_and_args(sys.argv[1:])
  main(*args, **flags)