#!/usr/bin/env python2.7

import copy
import os
import sys
from xml.etree import ElementTree

from generation_context import GenerationContext
from pom_handlers import (DepsFromPom, JavaOptionsInfo, WireInfo, SignedJarInfo,
                          SpecialPropertiesInfo, CachedDependencyInfos, ShadingInfo, JooqInfo)
from pom_utils import PomUtils


class PomFile(object):
  """Information holder for relevant details of a module's pom.xml."""

  class ParsingError(Exception):
    """Error parsing pom.xml."""

  def __init__(self, pom_file_path, root_directory=None, generation_context=None):
    if generation_context is None:
      generation_context = GenerationContext()
    generation_context.pom_file_cache[(pom_file_path, root_directory)] = self
    self.context = generation_context
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
    self._java_options = None
    self._parents = None
    self._shading_rules = None
    self._config_tree = None

  @classmethod
  def find(cls, pom_file_path, root_directory=None, generation_context=None):
    key = (pom_file_path, root_directory)
    if not generation_context or key not in generation_context.pom_file_cache:
      try:
        return cls(pom_file_path, root_directory, generation_context)
      except Exception as e:
        if not os.path.exists(pom_file_path):
          warning = '\nThis probably occurred because that pom file does not actually exist.'
        else:
          warning = '\nThe structure of that pom file is probably illegal or unconventional.'
        raise cls.ParsingError('Exception trying to parse {path}: {error}\n{warn}'.format(
          path=pom_file_path,
          error=str(e),
          warn=warning,
        )), None, sys.exc_info()[2]
    return generation_context.pom_file_cache[key]

  def _get_parsed_pom_data(self, generation_context):
    self.deps_from_pom = DepsFromPom(PomUtils.pom_provides_target(rootdir=self.root_directory),
      rootdir=self.root_directory,
      exclude_project_targets=generation_context.exclude_project_targets
    )
    self.wire_info = WireInfo.from_pom(self.path, self.root_directory)
    self.signed_jar_info = SignedJarInfo.from_pom(self.path, self.root_directory)
    self.java_options_info = JavaOptionsInfo.from_pom(self.path, self.root_directory)
    self.shading_info = ShadingInfo.from_pom(self.path, self.root_directory)
    self.jooq_info = JooqInfo.from_pom(self.path, self.root_directory)

  def _update_properties(self):
    self._properties.update(self.deps_from_pom.properties)
    self._properties.update(SpecialPropertiesInfo.from_pom(self.path,
                                                           self.root_directory).properties)
    # Magic maven symbols.
    basedir = os.path.abspath(self.directory)
    self._properties['basedir'] = "' + symbols.module_directory + '"
    self._properties['project.basedir'] = "' + symbols.module_directory + '"
    self._properties['project.baseUri'] = "' + symbols.module_uri + '"
    self._properties['project.build.directory'] = "' + symbols.module_target_directory + '"
    self._properties['maven.build.timestamp'] = "' + symbols.build_timestamp + '"
    self._properties['user.name'] = "' + symbols.user_name + '"

  def _initialize_dependency_lists(self):
    aggregate_lib_deps, aggregate_test_deps = self.deps_from_pom.get(self.path)
    lib_deps, test_deps, lib_jar_deps, test_jar_deps = [], [], [], []
    for dep in aggregate_lib_deps:
      if not (dep.startswith('jar(') or dep.startswith('sjar(')):
        lib_deps.append(dep)
      else:
        lib_jar_deps.append(dep)
    for dep in aggregate_test_deps:
      if not (dep.startswith('jar(') or dep.startswith('sjar(')):
        test_deps.append(dep)
      else:
        test_jar_deps.append(dep)
    self.lib_deps.extend(lib_deps)
    self.test_deps.extend(test_deps)
    self.lib_jar_deps.extend(lib_jar_deps)
    self.test_jar_deps.extend(test_jar_deps)

  def walk_pom_parents(self):
    """Returns an iterator of PomFile objects in the form self, self.parent, etc."""
    if not self._parents:
      all_parents = []
      pom = self
      while pom:
        all_parents.append(pom)
        pom = pom.parent
      self._parents = all_parents
    return self._parents

  @property
  def parent(self):
    if self.deps_from_pom.parent:
      parent_root = self.deps_from_pom.parent.root_directory
      parent_path = self.deps_from_pom.parent.source_file_name
      check_path = os.path.join(parent_root, parent_path) if parent_root else parent_path
      if not os.path.exists(check_path):
        raise self.ParsingError('Error parsing {pom}: parent pom does not exist at: {parent}.'
                                .format(pom=self.path, parent=check_path))
      return PomFile.find(parent_path, parent_root, generation_context=self.context)
    return None

  def _signed_jar_infos(self):
    for pom in self.walk_pom_parents():
      yield pom.signed_jar_info

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

  def _dedup_compile_args(self, args):
    # We try to de-dup compile arguments that don't make sense to duplicate.

    def strategy_replace(old_arg, new_arg):
      return None, new_arg

    def strategy_keep_unique(old_arg, new_arg):
      if old_arg == new_arg:
        return None, new_arg
      return old_arg, new_arg

    duplication_strategies = {
      'bootclasspath': strategy_replace,
      'lint': strategy_keep_unique,
    }

    def parse_arg(arg):
      """Return (name, value) tuple."""
      colon = arg.find(':')
      if colon > 0:
        return arg[2:colon], arg[colon+1:]
      return arg, ''

    new_args = []
    for arg in args:
      if not arg.startswith('-X'):
        new_args.append(arg)
        continue
      name, value = parse_arg(arg)
      found_duplicate = False
      for i,a in enumerate(new_args):
        if a.startswith('-X{}:'.format(name)):
          # Duplicate detected.
          found_duplicate = True
          break
      if found_duplicate:
        if name in duplication_strategies:
          old_arg, new_arg = duplication_strategies[name](a, arg)
          if old_arg is None:
            new_args.pop(i)
          if new_arg is not None:
            new_args.append(new_arg)
      else:
        new_args.append(arg)
    return new_args

  def _correct_prefixes(self, args):
    correct = []
    for arg in args:
      if arg.startswith('-C'):
        correct.append(arg)
      else:
        correct.append('-C{}'.format(arg))
    return correct

  @property
  def java_options(self):
    if not self._java_options:
      total = JavaOptionsInfo()
      total.source_level = self.java_options_info.source_level
      total.target_level = self.java_options_info.target_level
      total.compile_args = self.java_options_info.compile_args
      total.test_env_vars = dict(self.java_options_info.test_env_vars)
      total.test_jvm_args = list(self.java_options_info.test_jvm_args)

      pom = self.parent
      if pom:
        total.source_level = total.source_level or pom.java_options.source_level
        total.target_level = total.target_level or pom.java_options.target_level
        total.compile_args = pom.java_options.compile_args + total.compile_args
        total.test_env_vars.update(pom.java_options.test_env_vars)
        total.test_jvm_args.extend(pom.java_options.test_jvm_args)

      total.compile_args = self._dedup_compile_args(total.compile_args)
      total.compile_args = self._correct_prefixes(total.compile_args)
      self._java_options = total
    return self._java_options

  @classmethod
  def _merge_jooq_config(cls, one, two):
    merge_set = {'jdbc', 'properties', 'generator', 'database', 'generate', 'target'}
    merged = copy.deepcopy(one)
    frontier = [(merged, '.', child) for child in two]
    while frontier:
      parent, path, node = frontier.pop(0)
      partner = parent.find('./{}'.format(node.tag))
      stripped_tag = node.tag
      if '}' in node.tag:
        stripped_tag = node.tag[node.tag.find('}')+1:]
      if partner is None:
        # Append.
        parent.append(node)
      elif stripped_tag in merge_set:
        # Merge children.
        frontier.extend((partner, '?', kid) for kid in node)
      else:
        # Replace.
        parent.remove(partner)
        parent.append(copy.deepcopy(node))
    return merged

  @classmethod
  def _inject_jooq_schema_exclusion(cls, tree):
    table_name = 'SCHEMA_VERSION'
    prefix = tree.tag[:tree.tag.rfind('}')+1]
    node = tree.find('./{0}generator/{0}database/{0}excludes'.format(prefix))
    database = tree.find('./{0}generator/{0}database'.format(prefix))
    if node is not None:
      if node.text is None or not node.text.strip():
        node.text = table_name
      elif table_name not in node.text.upper():
        node.text += ' | {}'.format(table_name)
    elif database is not None:
      database.append(ElementTree.fromstring('<excludes>{}</excludes>'.format(table_name)))

  @property
  def jooq_config_tree(self):
    if self._config_tree is None:
      tree = None
      for pom in reversed(self.walk_pom_parents()):
        if tree is None:
          tree = pom.jooq_info.config_tree
          continue
        if pom.jooq_info.config_tree is None:
          continue
        tree = self._merge_jooq_config(tree, pom.jooq_info.config_tree)
      self._inject_jooq_schema_exclusion(tree)
      self._config_tree = tree
    return self._config_tree

  @property
  def jooq_config(self):
    return ElementTree.tostring(self.jooq_config_tree)

  @property
  def manifest_entries(self):
    entries = {}
    for info in self._signed_jar_infos():
      for key, value in info.manifest_entries.items():
        self._update_manifest_entry(entries, key, value)
    return entries

  @property
  def shading_rules(self):
    if self._shading_rules is None:
      self._shading_rules = []
      for pom in reversed(self.walk_pom_parents()):
        self._shading_rules.extend(pom.shading_info.rules)
    return self._shading_rules

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
    props = {}
    for pom in reversed(self.walk_pom_parents()):
      props.update(pom._properties)
    return props

  @property
  def mainclass(self):
    return self.deps_from_pom.get_property('project.mainclass')

  @property
  def artifact_id(self):
    return self.deps_from_pom.artifact_id
