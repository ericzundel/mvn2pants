#!/usr/bin/env python2.7

from __future__ import print_function, with_statement

import argparse
import os
import sys
import xml

from pom_utils import PomUtils
from pom_handlers import _DFPomContentHandler


class PomDetails(object):
  """Holds details about a pom.xml and the artifacts it references."""

  def __init__(self, repo_dir, module_dir, dm_pom_content_handler):
    """Capture information out of the dependency section of a pom

    Note that this does not attempt to perform property substitution.

    :param string repo_dir:
    :param string module_dir:
    :param _DFPomContentHandler dm_pom_content_handler:
    :return:
    """
    self.project_name = module_dir
    self.path = os.path.join(repo_dir, module_dir, 'pom.xml')
    group_id = dm_pom_content_handler.groupId
    artifact_id = dm_pom_content_handler.artifactId
    self.artifact = self.format_artifact(group_id, artifact_id) if group_id and artifact_id else None
    self._dependencies = dm_pom_content_handler.dependencies

  @property
  def produced_artifact(self):
    return self.artifact

  @property
  def consumed_artifacts(self):
    artifacts = set()
    for dep in self._dependencies:
      if 'groupId' in dep and 'artifactId' in dep:
        artifacts.add(self.format_artifact(dep['groupId'], dep['artifactId']))
    return artifacts

  def format_artifact(self, group_id, artifact_id):
    return (group_id, artifact_id)


class RepoDetails(object):
  """Captured information from the analysis that can be stored for later comparison."""

  def __init__(self, analysis):
    self._produced_artifacts = analysis.produced_artifacts
    self._consumed_artifacts = analysis.consumed_artifacts
    self._repo_name = analysis.repo_name

  @property
  def consumed_artifacts(self):
    return self._consumed_artifacts

  @property
  def produced_artifacts(self):
    return self._produced_artifacts

  @property
  def repo_name(self):
    return self._repo_name


class ArtifactDependencyAnalysis(object):
  """Analyzes the artifacts produced and consumed by repos build with Maven.

  Note that method calls to this class may be influenced by interleaving calls to PomUtils
  which includes creating an analysis of another repo.   You should capture information from the
  analysis with the capture() method before attempting to analyze another repo or make other
  calls the the PomUtils or PomHandlers libraries.
  """

  def __init__(self, repo_dir):
    # Clear the cache before analyzing the repo
    PomUtils.reset_caches()
    self.repo_dir = repo_dir
    self._top_pom = PomUtils.top_pom_content_handler(rootdir=repo_dir)

    self._pom_details = {}
    # Parse oll of the poms for the modules [ plus the top level pom.xml ]
    module_list = self._top_pom.modules + ['']
    while len(module_list):
      module = module_list.pop()
      if module in self._pom_details.keys():
        continue
      full_source_path = os.path.join(repo_dir, module, 'pom.xml')
      pom_handler = _DFPomContentHandler()
      try:
        with open(full_source_path) as source:
          xml.sax.parse(source, pom_handler)
      except IOError:
        # assume this file has been removed for a good reason and just continue normally
        continue
      self._pom_details[module] = PomDetails(repo_dir, module, pom_handler)
      # Don't forget to also add in the parent poms
      if 'relativePath' in pom_handler.parent:
        parent_module = os.path.join(module, pom_handler.parent['relativePath'])
        if os.path.basename(parent_module) == 'pom.xml':
          parent_module = os.path.dirname(parent_module)
        parent_module =os.path.normpath(parent_module)
        if parent_module not in self._pom_details.keys():
          module_list.append(parent_module)

  @property
  def repo_name(self):
    return os.path.basename(self.repo_dir)

  def capture(self):
    """Capture the information from this analysis.

    :returns: A copy of the information from this analysis into an object that won't change
    with other access to the PomUtils library.
    :rtype: RepoDetails
    """
    return RepoDetails(self)

  @property
  def all_pom_details(self):
    return self._pom_details.values()

  def pom_details(self, pom_file_path):
    if pom_file_path not in self._pom_details:
      self._pom_details[pom_file_path] = PomDetails(pom_file_path, self.repo_dir)
    return self._pom_details[pom_file_path]

  @property
  def produced_artifacts(self):
    return {pom.produced_artifact for pom in self.all_pom_details
            if pom is not None and pom.produced_artifact is not None}

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
    print ("Analyzing repo1 {}".format(repo1_dir))
    repo1 = cls(repo1_dir).capture()
    print ("Analyzing repo2 {}".format(repo2_dir))
    repo2 = cls(repo2_dir).capture()


    print('Artifacts {} produces that {} consumes:'.format(repo1.repo_name, repo2.repo_name))
    one_to_two = set.intersection(repo1.produced_artifacts, repo2.consumed_artifacts)
    print(cls._format_artifact_list(one_to_two))

    print('Artifacts {} produces that {} consumes:'.format(repo2.repo_name, repo1.repo_name))
    two_to_one = set.intersection(repo1.consumed_artifacts, repo2.produced_artifacts)
    print(cls._format_artifact_list(two_to_one))


def main(args):
  parser = argparse.ArgumentParser("Report artifacts published by repo1 to those consumed by repo2")
  parser.add_argument('--repo-dir', metavar='REPO_DIR',
                      help='Process a summary of the artifacts this repo consumes and produces.')
  parser.add_argument('--other-repo-dir', metavar='OTHER_REPO_DIR',
                      help='Prints a comparison of the inter-relationships between --repo-dir.')
  args = parser.parse_args(args)

  repo1_dir = os.path.abspath(args.repo_dir if args.repo_dir else '.')

  if not args.other_repo_dir:
    ArtifactDependencyAnalysis.print_repo_summary(repo1_dir)
  else:
    repo2_dir = os.path.abspath(args.other_repo_dir)
    ArtifactDependencyAnalysis.print_repo_comparison(repo1_dir, repo2_dir)


if __name__ == '__main__':
  main(sys.argv[1:])
