#!/usr/bin/env python2.7

import os

from generation_context import GenerationContext
from pom_handlers import (DepsFromPom, WireInfo, SignedJarInfo, SpecialPropertiesInfo,
                          CachedDependencyInfos)
from pom_utils import PomUtils


class PomFile(object):
  """Information holder for relevant details of a module's pom.xml."""

  def __init__(self, pom_file_path, root_directory=None, generation_context=None):
    if generation_context is None:
      generation_context = GenerationContext()
    self.path = pom_file_path
    self.root_directory = root_directory
    # Get deps_from_pom, wire_info, etc.
    self._get_parsed_pom_data(generation_context)
    # These dependency lists are initially populated by the pom.xml's data, then updated by
    # build_components as they generated and inject their own dependencies.
    self.lib_deps = []
    self.test_deps = []
    self.lib_jar_deps = []
    self.test_jar_deps = []
    self.resources = []
    self.test_resources = []
    self._initialize_dependency_lists()
    # Names of targets generated for project-level BUILD file.
    self.project_target_names = set()
    # Update our properties dict with any 'special' properties (things that are conditional on
    # sys.platform, etc).
    self._properties = {}
    self._update_properties()

  def _get_parsed_pom_data(self, generation_context):
    self.deps_from_pom = DepsFromPom(PomUtils.pom_provides_target(),
      rootdir=self.root_directory,
      exclude_project_targets=generation_context.exclude_project_targets
    )
    self.wire_info = WireInfo.from_pom(self.path, self.root_directory)
    self.signed_jar_info = SignedJarInfo.from_pom(self.path, self.root_directory)

  def _update_properties(self):
    self._properties.update(self.deps_from_pom.properties)
    self._properties.update(SpecialPropertiesInfo.from_pom(self.path,
                                                           self.root_directory).properties)

  def _initialize_dependency_lists(self):
    aggregate_lib_deps, aggregate_test_deps = self.deps_from_pom.get(self.path)
    lib_deps, test_deps, lib_jar_deps, test_jar_deps = [], [], [], []
    for dep in aggregate_lib_deps:
      if dep.find('jar(') != 0:
        lib_deps.append(dep)
      else:
        lib_jar_deps.append(dep)
    for dep in aggregate_test_deps:
      if dep.find('jar(') != 0:
        test_deps.append(dep)
      else:
        test_jar_deps.append(dep)
    self.lib_deps.extend(lib_deps)
    self.test_deps.extend(test_deps)
    self.lib_jar_deps.extend(lib_jar_deps)
    self.test_jar_deps.extend(test_jar_deps)

  def _signed_jar_infos(self):
    df = CachedDependencyInfos.get(self.path, rootdir=self.root_directory)
    while df:
      yield SignedJarInfo.from_pom(df.source_file_name, df.root_directory)
      df = df.parent

  def _update_manifest_entry(self, entries, key, value):
    if key == 'Class-Path':
      paths = value.split(' ')
      for i, path in enumerate(paths):
        if os.path.dirname(path) == 'lib-signed':
          paths[i] = os.path.join('{}-signed-jars'.format(self.deps_from_pom.artifact_id),
                                  os.path.basename(path))
      if key in entries:
        for path in entries[key].split(' '):
          if path not in paths:
            paths.append(path)
      value = ' '.join(paths)
      entries[key] = value
    elif key not in entries or not entries[key]:
      entries[key] = value

  @property
  def manifest_entries(self):
    entries = {}
    for info in self._signed_jar_infos():
      for key, value in info.manifest_entries.items():
        self._update_manifest_entry(entries, key, value)
    return entries

  @property
  def signed_jars_deploy_excludes(self):
    exclude_sets = (set(info.excludes) for info in self._signed_jar_infos())
    all_excludes = reduce(set.union, exclude_sets, set())
    # TODO(gm): Pant's exclude() only supports the 'org' and 'name' parameters, not 'type_' etc.
    return sorted(artifact for artifact in all_excludes if len(artifact) == 2)

  @property
  def signed_jars_formatted_excludes(self):
    formatted = []
    for artifact in self.signed_jars_deploy_excludes:
      org, name = artifact
      if '*' in org:
        # TODO(gm): Pants's exclude() currently doesn't support wildcards in organizations.
        continue
      if name == '*':
        # TODO(gm): Wildcards in name only work if the whole name is a wildcard.
        formatted.append("exclude(org='{}')".format(org))
      elif '*' not in name:
        formatted.append("exclude(org='{}', name='{}')".format(org, name))
    return formatted

  @property
  def signed_jars_artifact_ids(self):
    return reduce(set.union, [set(info.signed_jars) for info in self._signed_jar_infos()], set())

  @property
  def signed_jars_dependencies(self):
    signed_jars = self.signed_jars_artifact_ids
    return ['3rdparty:{}'.format('.'.join(artifact))
            for artifact in self.signed_jars_deploy_excludes if artifact[1] in signed_jars]

  @property
  def signed_jars_strip_version(self):
    return any(info.strip_version for info in self._signed_jar_infos())

  @property
  def directory(self):
    return os.path.normpath(os.path.dirname(self.path))

  @property 
  def default_target_name(self):
    return os.path.basename(self.directory)

  @property 
  def properties(self):
    return self._properties
