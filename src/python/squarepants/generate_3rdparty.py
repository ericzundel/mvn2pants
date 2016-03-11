#!/usr/bin/python
# Used to automatically pull in external dependencies defined in Maven into Pants' 3rdparty BUILD

import logging
import os
import sys
from collections import defaultdict, namedtuple
from textwrap import dedent

from pom_utils import PomUtils
from generation_utils import GenerationUtils
from target_template import Target
from pom_file import PomFile

logger = logging.getLogger(__name__)


# Exclude targets handled already in 3rdparty/BUILD... It would be nice to be able to figure this out dynamically
_excludes = [
              #'com.google.guava.guava',
            ]


class ArtifactId(namedtuple('Id', ['org', 'name', 'rev'])):

  def contains(self, other):
    """Checks whether the other id is "contained" by this id.

    For example, if this id is (org='foobar', name=None, rev=None), this method will return True
    as long as other.org == 'foobar'.

    However, if this id is (org='foobar', name='hello', rev=1.2), this method will return True if
    and only if this id is the same as the other id.

    :param ArtifactId other: The other Id to check.
    :return: Whether the other id matches the elements of this id which are not None.
    :rtype: bool
    """
    for a, b in zip(self, other):
      if a is not None and a != b:
        return False
    return True


class ThirdPartyBuildGenerator(object):

  # Sets of artifact coordinates to keep in separated managed dependencies. This allows downstream
  # projects to use alternate versions of these artifacts, while still using the core managed
  # dependencies that are used by the rest of the repository.
  _disjoint_artifact_sets = {
    'managed-hbase': [
      ArtifactId('org.apache.hbase', None, None),
      ArtifactId('org.apache.hadoop', None, None),
    ],
  }

  @classmethod
  def _compute_dependencies(self):
    return PomUtils.dependency_management_finder().find_dependencies('parents/base/pom.xml')

  @classmethod
  def _get_artifact_set(cls, id):
    for name, artifacts in cls._disjoint_artifact_sets.items():
      if any(artifact.contains(id) for artifact in artifacts):
        return name
    return None

  @classmethod
  def _substitute_symbols(cls, s):
    return GenerationUtils.symbol_substitution(PomFile('parents/base/pom.xml').properties, s)

  def __init__(self, dependencies=None):
    if dependencies is None:
      dependencies = self._compute_dependencies()
    self._deps = dependencies

  class Artifact(object):
    """Represents a single external dependency artifact (such as a jar or a pom file)."""

    def __init__(self, dep):
      self.groupId = dep['groupId']
      self.artifactId = dep['artifactId']
      self.version = dep['version']
      self.classifier = dep.get('classifier')
      self.type_ = dep.get('type', None)
      self.force = None
      self._exclusions = dep.get('exclusions')

    @property
    def jar_excludes(self):
      if not self._exclusions:
        return None
      return ["exclude(org='{groupId}', name='{artifactId}')".format(**jar)
              for jar in self._exclusions]

    @property
    def name(self):
      parts = [self.groupId, self.artifactId]
      if self.classifier:
        parts.append(self.classifier)
      if self.type_ and self.type_ != 'jar':
        parts.append(self.type_)
      return '.'.join(parts)

    @property
    def id(self):
      return ArtifactId(self.groupId, self.artifactId, self.version)

    def format(self):
      return Target.sjar.format(org=self.groupId,
                                name=self.artifactId,
                                rev=self.version,
                                classifier=self.classifier,
                                type_=self.type_,
                                force=self.force,
                                excludes=self.jar_excludes)

  class ManagedLibrary(object):
    """Stores the data and formats the BUILD target for a jar_library()."""

    def __init__(self, name, artifacts, universal):
      """
      :param string name: The build file name.
      :param list artifacts: The list of Artifacts this library contains.
      :param bool universal: Whether this library should be part of the global list, or whether it should
        be isolated from the core dependencies (ie due to a version conflict).
      """
      self.name = name
      self.artifacts = artifacts
      self.universal = universal
      self.managed_dependencies = None

    @property
    def has_body(self):
      """Whether this library has contents that should be written to a BUILD file as a target."""
      return not self.universal or len(self.artifacts) != 1

    @property
    def spec(self):
      """The spec name of this target, formatted with quotes for inclusion in an artifacts list."""
      return "':{}'".format(self.name)

    def format_reference(self):
      """How this target should be referenced in a list of artifacts."""
      if self.has_body:
        return self.spec
      return self.artifacts[0].format()

    def format_body(self):
      """The body of the target (ie jar_library(...)) for inclusion in a build file.

      If this library has no body, this returns the emptystring.
      """
      if not self.has_body:
        return ''
      management = ''
      if self.managed_dependencies:
        management = "\n  managed_dependencies=':{}',".format(self.managed_dependencies.name)
      return GenerationUtils.autoindent(ThirdPartyBuildGenerator._substitute_symbols(dedent('''
        jar_library(name='{name}',
          jars=[
            {jars},
          ],{management}
        )
      ''').format(
        name=self.name,
        jars=',\n    '.join(jar.format() for jar in self.artifacts),
        management=management,
      )))

  class ManagedDependencies(object):
    """Stores the data and formats the BUILD target for a managed_jar_dependencies target."""

    def __init__(self, name, parent=None, generate_libraries=True):
      """
      :param string name: The build file name of this target.
      :param string parent: The build file name of the parent managed_dependences object (if any).
      :param bool generate_libraries: Whether this target should generate jar_library() targets for
        each artifact it references. (If true, this is formatted as a managed_jar_libraries target
        instead of a managed_jar_dependencies object).
      """
      self.name = name
      self.parent = parent
      self.libraries = []
      self.generate_libraries = generate_libraries

    def add(self, library):
      """Adds the library to the list of artifacts.

      Also sets the library's managed_dependencies target to this object.
      """
      library.managed_dependencies = self
      self.libraries.append(library)

    def _formatted_jars(self):
      for jar in self.libraries:
        yield jar.format_reference() if self.generate_libraries else jar.spec

    @property
    def _type_explanation(self):
      if self.generate_libraries:
        return 'This target pins artifact versions, and also generates jar_library() targets.'
      return 'This target pins artifact versions, but does not generate jar_library() targets.'

    def format(self):
      """Generates a formatted string for inclusion in a BUILD file."""
      references = sorted(self._formatted_jars())
      return GenerationUtils.autoindent(ThirdPartyBuildGenerator._substitute_symbols(dedent('''
        # {type_explanation}
        managed_jar_{type_}(name='{name}',
          artifacts=[{artifacts}
          ],{parent}
        )
      ''').format(
        name=self.name,
        artifacts=''.join('\n    {},'.format(s) for s in references),
        parent='' if not self.parent else "\n  dependencies=[':{}'],".format(self.parent),
        type_='libraries' if self.generate_libraries else 'dependencies',
        type_explanation=self._type_explanation,
      )))

  def generate(self):
    header = dedent('''
      # Automatically generated by {0}

    ''').lstrip().format(os.path.basename(sys.argv[0]))
    artifacts_by_id = defaultdict(list)
    versions_by_name = defaultdict(set)
    for dep in self._deps:
      artifact = "{groupId}.{artifactId}".format(groupId=dep['groupId'] ,
                                                 artifactId=dep['artifactId'],)
      if artifact in _excludes:
        logger.debug("skipping " + artifact)
        continue
      artifact = self.Artifact(dep)
      artifacts_by_id[artifact.id].append(artifact)
      versions_by_name[artifact.name].add(artifact.version)

    global_name = 'managed'
    default_name = 'managed-core'
    managed_dependencies_by_name = {
      default_name: self.ManagedDependencies(default_name, generate_libraries=False),
      global_name: self.ManagedDependencies(global_name, generate_libraries=True),
    }

    for artifact_id, artifact_list in sorted(artifacts_by_id.items()):
      if len(artifact_list) == 1:
        artifact_name = next(iter(artifact_list)).name
      else:
        artifact_name = '{0}.{1}'.format(artifact_id.org, artifact_id.name)
      name_buffer = [artifact_name]
      version_count = len(versions_by_name[artifact_name])
      managed = False
      if version_count > 1:
        # NB(gmalmquist): In practice, this isn't currently in-use in our repo. Which is a good
        # thing. (As of writing 2016-01-27).
        # pants normally complains about 2 artifact names with different versions,
        # like com.squareup.okhttp.mockwebserver, but we sometimes use multiple versions.
        name_buffer.append('-{0}'.format(artifact_id.rev))
        for artifact in artifact_list:
          artifact.force = True
      else:
        managed = True

      library_name = ''.join(name_buffer)
      logger.debug("Adding {jars} as {name}.".format(
        jars=', '.join(jar.name for jar in artifact_list),
        name=library_name))

      if managed:
        management_name = self._get_artifact_set(artifact_id) or default_name
      else:
        management_name = 'managed-{}'.format(library_name)

      if management_name not in managed_dependencies_by_name:
        managed_dependencies_by_name[management_name] = self.ManagedDependencies(
          name=management_name,
          parent=default_name,
          generate_libraries=not managed,
        )
      add_to = [management_name]
      if managed:
        add_to.append(global_name)
      for management_name in add_to:
        managed_dependencies_by_name[management_name].add(self.ManagedLibrary(
          name=library_name,
          artifacts=artifact_list,
          universal=managed,
        ))

    if set(managed_dependencies_by_name) == {global_name, default_name}:
      # If there are no special-case managed dependencies, we only need the single global target.
      managed_dependencies_by_name.pop(default_name)

    managed_dependencies = sorted(managed_dependencies_by_name.values(),
                                  key=lambda m: (-len(m.libraries), m.name))

    parts = []
    parts.append(header)
    parts.extend(deps.format() for deps in managed_dependencies)
    for deps in managed_dependencies:
      if deps.generate_libraries:
        parts.extend(sorted(filter(None, (jar.format_body() for jar in deps.libraries))))
    return ''.join(parts)


def main():
  """Test driver that spits out <dependencyManagement> contents.
     Run from ~/Development/java
  """
  print(ThirdPartyBuildGenerator().generate())


if __name__ == "__main__":
  PomUtils.parse_common_args(sys.argv[1:])
  main()
