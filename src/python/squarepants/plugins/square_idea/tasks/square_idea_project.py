# coding=utf-8

from __future__ import (absolute_import, division, generators, nested_scopes, print_function,
                        unicode_literals, with_statement)

import logging
import os
import shutil
from collections import defaultdict, namedtuple
from xml.etree import ElementTree

from twitter.common.collections import OrderedSet

from pants.base.build_environment import get_buildroot
from pants.base.exceptions import TaskError
from pants.base.generator import Generator, TemplateData
from pants.base.revision import Revision
from pants.scm.git import Git
from pants.util.dirutil import safe_mkdir
from pants.util.memo import memoized_method, memoized_property
from pants.util.osutil import get_os_name, known_os_names, normalize_os_name, OS_ALIASES

from squarepants.graph_util import Graph


logger = logging.getLogger(__name__)


_TARGET_TYPE_HIERARCHY = {
  type_: index for index, type_ in enumerate(('TEST_RESOURCE', 'TEST', 'RESOURCE', 'SOURCE'))
}

# HACK! (gmalmquist): This is a terrible hack to get pants to recognize OSX as an operating system
# alias for 'darwin'; it updates a global variable when this file is loaded! We need a patch in
# open-source pants to update dict to fix it for-real.
OS_ALIASES['darwin'].update({'osx'})


class IdeaProject(object):
  """Constructs data for an IntelliJ project."""

  AnnotationProcessing = namedtuple('AnnotationProcessing', [
    'enabled',
    'sources_dir',
    'test_sources_dir',
    'processors',
    'codegen_processors',
  ])

  annotation_processing_relative_path = '.pants-idea-generated'
  annotation_processing_relative_to_content_root = True

  class ModulePool(object):

    class NoAvailableModules(TaskError):
      pass

    @classmethod
    def generic_name(cls, index):
      return 'gen-{:0>4d}'.format(index)

    def __init__(self, specific_modules, generic_modules, steal_names=None):
      self._specific_available_modules = set(specific_modules)
      self._generic_available_modules = list(reversed(sorted(generic_modules)))
      self._assigned_modules = set()
      self._module_mapping = {}
      self._next_generic_index = 0

      if steal_names is None:
        steal_names = True
      self._steal_names = steal_names

    def unassigned_modules(self):
      unused = set(self._specific_available_modules)
      unused.update(self._generic_available_modules)
      return unused

    def assigned_modules(self):
      return set(self._assigned_modules)

    def _next_generic_name(self):
      name = None
      while (name is None or name in self._assigned_modules
             or name in self._generic_available_modules):
        name = self.generic_name(self._next_generic_index)
        self._next_generic_index += 1
      return name

    def module_for(self, module_name, use_specific=None, create_if_necessary=True):
      if use_specific is None:
        use_specific = self._steal_names
      if module_name in self._module_mapping:
        # If already assigned, use that.
        return self._module_mapping[module_name]
      if module_name in self._specific_available_modules:
        # If there's an unassigned module that happens to match our name, just use that.
        self._module_mapping[module_name] = module_name
        self._specific_available_modules.remove(module_name)
        self._assigned_modules.add(module_name)
        return module_name
      if self._generic_available_modules:
        # Assign a generic module.
        generic = self._generic_available_modules.pop()
        self._module_mapping[module_name] = generic
        self._assigned_modules.add(generic)
        return generic
      if use_specific and self._specific_available_modules:
        # Fallback on stealing someone else's module name. This creates misleading module names!
        specific = self._specific_available_modules.pop()
        self._module_mapping[module_name] = specific
        self._assigned_modules.add(specific)
        return specific
      if create_if_necessary:
        # Last resort -- create a new module. Will require an IntelliJ restart =(
        if module_name not in self._assigned_modules:
          # Make a new module named after ourselves.
          self._module_mapping[module_name] = module_name
          self._assigned_modules.add(module_name)
          return module_name
        # Looks like our specific name was stolen by someone else.
        generic = self._next_generic_name()
        self._module_mapping[module_name] = generic
        self._assigned_modules.add(generic)
        return generic
      raise self.NoAvailableModules('No modules are left in the pool to assign to "{}".'
                                    .format(module_name))

  class Module(object):
    """Represents a module in an IntelliJ project."""

    @classmethod
    def directory_to_name(cls, path, project=None):
      """Infers a hyphen-delimited module name from a system/directory/path.

      :param string path: The filesystem path of the directory.
      :param project: The IdeaProject which contains this module. If given, this is used to
        determine the module name in the event that it was remapped by the module pool. The project
        should always be provided in the normal flow of this task; it is only unspecified in unit
        testing.
      :return: The string representing the inferred module name.
      """
      inferred_name = os.path.relpath(path, get_buildroot()).replace(os.sep, '-')
      if project and inferred_name.startswith(os.path.basename(project.pants_workdir)):
        return project.module_pool.module_for(inferred_name)
      return inferred_name

    def __init__(self, project, directory, targets, name=None):
      """

      :param IdeaProject project:
      :param str directory: directory where the module is defined
      :param targets: list of targets from the export file to included as dependencies
      :type: list of dict
      :param str name: Manually override the module name, otherwise derives the name from directory
      """
      self.project = project
      self.directory = directory
      self.targets = targets
      self.dependencies = set()
      self.dependees = set()
      self.libraries = defaultdict(OrderedSet)
      self.excludes = set()
      self.annotation_processing_dependencies = set()
      self.name = name or self.directory_to_name(directory, project)

    @memoized_property
    def filename(self):
      return '{}.iml'.format(self.name)

    @property
    def output_directory(self):
      return os.path.join(os.path.dirname(self.project.output_directory),
                          '_out_{}'.format(self.name))

    @property
    def jar_path(self):
      return os.path.join(self.project.workdir,
                          'aops/artifacts/{module}_jar/{module}.jar'.format(module=self.name))

    @memoized_property
    def defined_annotation_processors(self):
      processors = set()
      for target in self.targets:
        if target['pants_target_type'] == 'annotation_processor':
          real_target = self.project.context.build_graph.get_target_from_spec(target['spec'])
          processors.update(real_target.processors)
      return processors

    def annotation_processing_output(self, source_type):
      relative_path = IdeaProject.annotation_processing_relative_path
      if IdeaProject.annotation_processing_relative_to_content_root:
        path = os.path.join(self.directory, relative_path, source_type)
      else:
        path = os.path.join(self.output_directory, 'production', relative_path, source_type)
      return os.path.normpath(path)

    @property
    def annotation_processing_sources_dir(self):
      return self.annotation_processing_output(self.project.annotation_processing.sources_dir)

    @property
    def annotation_processing_test_sources_dir(self):
      return self.annotation_processing_output(self.project.annotation_processing.test_sources_dir)

    def _transitive_graph_search(self, adjacency_func):
      frontier = list(adjacency_func(self))
      visited = set()
      while frontier:
        vertex = frontier.pop()
        if vertex in visited:
          continue
        visited.add(vertex)
        for adjacent in adjacency_func(self.project.modules_by_name[vertex]):
          if adjacent not in visited:
            frontier.append(adjacent)
      return visited

    def transitive_dependees(self):
      return self._transitive_graph_search(lambda module: module.dependees)

    def transitive_dependencies(self):
      return self._transitive_graph_search(lambda module: module.dependencies)

    def dependencies_template_data(self):
      return [TemplateData(
          name=dep,
          scope=self.project.get_module_dependency_scope(self.name,
                                                         self.directory_to_name(dep, self.project)))
              for dep in sorted(self.dependencies)]

  @classmethod
  def root_repo_name(cls):
    return os.path.basename(get_buildroot())

  @classmethod
  def load_all_module_directories(cls):
    return cls._load_all_module_directories_from_xml(os.path.join(get_buildroot(), 'pom.xml'))

  @classmethod
  def _load_all_module_directories_from_xml(cls, path):
    tree = ElementTree.parse(path)
    root = tree.getroot()
    tag = root.tag
    if not tag.endswith('project'):
      raise ValueError('Unable to find <project> tag in {path}.'.format(path=path))
    prefix = tag[:-len('project')]
    module_elements = root.find('{}modules'.format(prefix)).findall('{}module'.format(prefix))
    return {element.text.strip() for element in module_elements}

  @classmethod
  def _content_type(cls, target_data):
    """Gets the content type suitable for use in a IntelliJ content root description.

    :param target_data: The json blob of target data.
    :return: The string representing the content type (eg, "java-source").
    """
    language = 'java'
    if 'python_interpreter' in target_data:
      language = 'python'
    target_type = target_data['target_type']
    if target_type == 'TEST':
      return None
    # TODO(gm): scala? js? go?
    return '{language}-{type_}'.format(language=language,
                                       type_=target_type.lower().replace('_', '-'))

  @classmethod
  def _is_test(cls, target_data):
    """Returns true if the target json blob should be marked as a test."""
    return target_data['target_type'] == 'TEST'

  @classmethod
  def common_prefix(cls, strings):
    """Finds the longest common prefix between all the input strings.

    :param strings: List of "strings", where the strings are actually allowed to be any iterables
      that support slicing and equality checks (e.g. tuples, lists, actual strings, etc).
    """
    prefix = None
    for string in strings:
      if prefix is None:
        prefix = string
        continue
      if string[:len(prefix)] != prefix: # Avoiding startswith to work with lists also.
        for i in range(min(len(prefix), len(string))):
          if prefix[i] != string[i]:
            prefix = prefix[:i]
            break
        if i+1 < len(prefix):
          prefix = prefix[:i+1]
    return prefix

  @classmethod
  def find_closest_maven_module(cls, path):
    """Searches up through the parent directories looking for maven modules.

    :return: The first directory it finds which contains a pom.xml, or None.
    """
    path = os.path.normpath(path)
    path = os.path.relpath(path)
    pom_file = os.path.join(path, 'pom.xml')
    last_path = path
    while os.path.exists(path) and not os.path.exists(pom_file):
      path = os.path.dirname(path)
      if path == last_path:
        return None
      pom_file = os.path.join(path, 'pom.xml')
    return path

  @classmethod
  def infer_processor_name(cls, index, processors):
    """Creates a name for this group of annotation processors.

    This is used to pick the processor name that is displayed in the Annotation Processing pane
    in IntelliJ under Project -> Build, Execution, Deployment -> Compiler -> Annotation Processing.
    :param int index: The natural number indicating which processor this is. The order is fairly
      arbitrary, but stable.
    :param string processors: The list of processors -- aka the fully-qualified classnames of each
      processor.
    :return: A unique and as readable-as-possible name for this group of annotation processors.
    """
    if len(processors) == 1:
      # Use the simple class name if there's just one processor.
      processor_name, = processors
      if processor_name and '.' in processor_name:
        simple_name = processor_name[processor_name.rfind('.')+1:]
        if simple_name and simple_name[0] != simple_name[0].lower():
          processor_name = simple_name
    else:
      processor_name = cls.common_prefix(processors)
      if processor_name and processor_name[-1] == '.':
        processor_name = processor_name[:-1]
    if not processor_name:
      processor_name = '-'.join(processors)
    if not processor_name:
      processor_name = 'DefaultAnnotationProcessing'
    return '{0}-{1}'.format(index, processor_name)

  @classmethod
  def _simplify_module_dependency_graph(cls, modules, modules_by_name=None, prune_libraries=False):
    """Removes forward dependency edges and redundant library dependencies.

    This simplifies the dependency graph as much as possible, to make IntelliJ less like to get
    confused, to make the graph more space efficient, and to make it cleaner and more readable by
    humans.

    :param list modules: List of modules to simplify the dependencies of.
    :param dict modules_by_name: Map of names to their corresponding modules. If not specified, it
      will simply be computed from the list of modules.
    :param bool prune_libraries: If true, omits library dependencies that are already referenced
      transitively. This won't affect the set of libraries that a module depends on, but it may
      affect the order they appear on the classpath.
    """
    if not modules_by_name:
      modules_by_name = {module.name: module for module in modules}
    edges = set()
    for module in modules:
      edges.update(Graph.Edge(module.name, dependency) for dependency in module.dependencies)
    graph = Graph(vertices={module.name for module in modules}, edges=edges)
    dependency_closure = {}
    # Process dependencies before dependees.
    for module_name in reversed(graph.topological_ordering(stable=True)):
      module = modules_by_name[module_name]
      dependency_closure[module_name] = set()
      direct_dependencies = sorted(module.dependencies) # Sort for stability.
      # Remove any direct dependencies which are already pulled in by our transitive dependencies.
      for dependency in direct_dependencies:
        if any(dependency in dependency_closure[other] for other in module.dependencies):
          logger.debug('Removing redundant dependency {} -> {}.'.format(module_name, dependency))
          module.dependencies.remove(dependency)
        else:
          dependency_closure[module_name].update(dependency_closure[dependency])
          dependency_closure[module_name].add(dependency)
      if prune_libraries:
        # Remove any libraries which are already pulled in by our transitive dependencies.
        transitive_libraries = defaultdict(set)
        for dep_name in dependency_closure[module_name]:
          dependency = modules_by_name[dep_name]
          for conf, jars in dependency.libraries.items():
            transitive_libraries[conf].update(jars)
        for conf in transitive_libraries:
          module.libraries[conf] -= transitive_libraries[conf]

  def __init__(self, export_json, output_directory, workdir, context, maven_style=True,
               exclude_folders=None, annotation_processing=None, bash=None, java_encoding=None,
               java_maximum_heap_size=None, pants_workdir=None, generate_root_module=None,
               prune_libraries=False, module_pool=None, debug_port=None, 
               provided_module_dependencies=None):
    self.blob = export_json
    self.maven_style = maven_style
    self.global_excludes = map(os.path.abspath, exclude_folders or ())
    self.context = context
    self.workdir = workdir
    self.output_directory = output_directory or os.path.abspath('.')
    self.annotation_processing = annotation_processing
    self.bash = bash
    self.java_encoding = java_encoding
    self.java_maximum_heap_size = java_maximum_heap_size
    self.pants_workdir = pants_workdir or '.pants.d'
    self.generate_root_module = generate_root_module
    self.prune_libraries = prune_libraries
    self.module_pool = module_pool or self.ModulePool((),())
    self.annotation_processing_jars = set()
    self.debug_port = debug_port
    self.provided_module_dependencies = provided_module_dependencies or {}
    self._setup_modules()

  def _setup_modules(self):
    targets_by_source_root = self.targets_by_source_root
    self.modules = [self.Module(self, module_dir, targets_by_source_root[module_dir])
                    for module_dir in sorted(targets_by_source_root)]
    self.loaded_module_directories = {os.path.relpath(module.directory) for module in self.modules}
    loaded_module_names = {m.name for m in self.modules}
    self.modules.extend(self._create_synthetic_annotation_processing_modules())
    self.placeholder_modules = {module for module in self.load_all_module_directories()
                                if self.Module.directory_to_name(module, self) not in loaded_module_names}
    for module_dir in self.placeholder_modules:
      self.modules.append(self.Module(self, module_dir, set()))
    self.placeholder_modules.update(name for name in self.module_pool.unassigned_modules())
    for module_dir in self.module_pool.unassigned_modules():
      self.modules.append(self.Module(self, '.pants.d/_fake', set(), name=module_dir))
    self._compute_module_dependencies()
    self.all_module_directories = {os.path.relpath(module.directory) for module in self.modules}
    self._check_for_direct_cycles()
    self._simplify_module_dependency_graph(self.modules, self.modules_by_name, self.prune_libraries)

  @memoized_method
  def _maven_excludes(self, path, recurse_up=True, recurse_down=True):
    """We need to exclude the maven-generated 'target/' directories.

    These directories may be found alongside any pom.xml, and cause problems for pants and intellij
    because they sometimes get picked up as (duplicate) sources.

    :param string path: A directory where we should check for pom.xml's and target directories. This
      method recursively traverses up the path's parent directories looking for targets.
    :param bool recurse_up: Whether to recursively check for target/ excludes in parent directories.
    :param bool recurse_down: Whether to check for target/ excludes in the file tree below path/.
    :return: A set of target directories to exclude.
    """
    excludes = set()
    if path and os.path.exists(path):
      if os.path.isdir(path):
        target = os.path.join(path, 'target')
        if os.path.exists(os.path.join(path, 'pom.xml')):
          excludes.add(os.path.abspath(target))
      parent = os.path.dirname(path)
      if recurse_up and parent != path:
        excludes.update(self._maven_excludes(parent, recurse_up=True, recurse_down=False))
      if recurse_down:
        for (dirpath, dirnames, filenames) in os.walk(path):
          if 'pom.xml' in filenames:
            excludes.add(os.path.abspath(os.path.join(dirpath, 'target')))
    return excludes

  def _check_for_direct_cycles(self):
    """Checks for direct cycles between modules, and breaks them with a warning.

    Because of the way we manage proto paths, we can get circular dependencies between the various
    raw-protos directories. This isn't a problem when running pants itself, because there are no
    cycles at the fine-grained target level. And this really isn't a problem in IntelliJ either,
    because as far as IntelliJ is concerned, the raw-protos directories don't *do* anything. So we
    can safely break these cycles and not worry about them any further.
    """
    for module in self.modules:
      for dependency in tuple(module.dependencies):
        if module.name in self.modules_by_name[dependency].dependencies:
          self.context.log.warn('Direct dependency cycle detected between {} and {}; breaking it. '
                                'This is expected and probably harmless for raw-protos modules.'
                                .format(module.name, dependency))
          module.dependencies.remove(dependency)

  def _handle_system_specific_libraries(self, libraries):
    general_confs = {'default', 'sources', 'javadoc'}
    specific_confs = set(libraries) - general_confs
    os_name = normalize_os_name(get_os_name())

    for conf in specific_confs:
      for name in known_os_names():
        if name in conf.lower() and normalize_os_name(name) == os_name:
          # Assume this conf actually represents libraries that should be mapped to 'default' on
          # this system.
          libraries['default'].update(libraries[conf])

  def _compute_module_and_library_dependencies(self, target):
    """Given the target spec, compute its module dependencies and libraries.

    :param dict target: The json blob of target data.
    :return: a tuple of the form (set of module names, dictionary of conf -> set of libraries).
    """
    collected_libraries = defaultdict(OrderedSet)
    collected_modules = set()

    def collect_libraries(target_spec):
      """Adds any libraries this target has to the collected_libraries dictionary.

      Skips targets that aren't jar_libraries.
      :param str target_spec: The target's spec.
      :return: True if the target is a jar_library, False otherwise.
      """
      if self.blob['targets'][target_spec].get('pants_target_type') != 'jar_library':
        return False
      for library_name in self.blob['targets'][target_spec]['libraries']:
        for conf, path in self.blob['libraries'][library_name].items():
          collected_libraries[conf].add(path)
      return True

    def collect_dependencies(target_spec):
      """Adds this targets libraries and its module to the collected libraries and modules.

      May return a list of more target specs that should be collected.
      :param target_spec: The target's spec.
      :return: An iterable of dependencies whose transitive dependencies should be collected, in the
        event that this target has dependencies but cannot be associated with its own module.
      """
      if collect_libraries(target_spec):
        return ()
      if target_spec not in self.module_names_by_target:
        # This represents a target that is neither a jar_library nor a target that has sources.
        # In other words, it is simply a target() object or equivalent, and exists only as an
        # intermediate node in the dependency chain. We collapse this chain by recursing through
        # its dependencies.
        return self.blob['targets'][target_spec]['targets']
      # This is a "normal" dependency, so we make this module dependent on the module which contians
      # the target_dependency.
      dependency = self.module_names_by_target[target_spec]
      collected_modules.add(dependency)
      return ()

    visited = set()

    def should_skip(path, vertex):
      if vertex in visited:
        # This represents either a cycle or a diamond dependency.
        if vertex in path:
          logger.warn('Skipping cycle involving {spec}.{trace}\n  {spec}'.format(
            spec=vertex,
            trace=''.join('\n  {} ->'.format(n) for n in path)
          ))
        return True
      return False

    for target_dependency in target.get('targets', ()):
      # Performs a graph search to include the (possibly transitive) dependencies of targets which
      # don't specify libraries or sources.
      frontier = {((), target_dependency)} # (path, vertex) tuples. The paths are for logging.
      while frontier:
        path, next = frontier.pop()
        if should_skip(path, next):
          continue
        visited.add(next)
        next_path = path + (next,)
        for dep in collect_dependencies(next):
          if not should_skip(next_path, dep):
            frontier.add((next_path, dep))

    self._handle_system_specific_libraries(collected_libraries)
    return collected_modules, collected_libraries

  def _compute_module_dependencies(self):
    for module, target in self.modules_and_targets:
      collected_modules, collected_libraries = self._compute_module_and_library_dependencies(target)
      module.dependencies.update(m for m in collected_modules if m != module.name)
      for other in collected_modules:
        if other != module.name:
          module.dependencies.add(other)
          self.modules_by_name[other].dependees.add(module.name)
      for conf, libraries in collected_libraries.items():
        module.libraries[conf].update(libraries)
    for module in self.modules:
      for dependency in module.dependencies:
        dep = self.modules_by_name[dependency]
        if dep.defined_annotation_processors:
          module.libraries['default'].add(dep.jar_path)
          self.annotation_processing_jars.add(dep.jar_path)

  @memoized_property
  def modules_by_name(self):
    return {module.name: module for module in self.modules}

  @memoized_property
  def module_names_by_target(self):
    module_names_by_target = {}
    for module, target in self.modules_and_targets:
      module_names_by_target[target['spec']] = module.name
    return module_names_by_target

  @memoized_property
  def module_names(self):
    return { module.name for module in self.modules }

  @property
  def modules_and_targets(self):
    for module in self.modules:
      for target in module.targets:
        yield module, target

  @property
  def targets_by_source_root(self):
    targets_by_module = defaultdict(list)
    for target_spec, target_data in self.blob['targets'].items():
      if not target_data.get('roots'):
        continue
      target_data['spec'] = target_spec
      root_dir = os.sep.join(self.common_prefix(root['source_root'].split(os.sep)
                                                 for root in target_data['roots']))
      if self.maven_style:
        parts = root_dir.split(os.sep)
        if 'src' in parts:
          root_dir = os.sep.join(parts[:parts.index('src')])
      targets_by_module[root_dir].append(target_data)
    return targets_by_module

  @property
  def annotation_processing_template(self):
    classpath = []
    if 'libraries' in self.blob:
      classpath = [lib['default'] for lib in self.blob['libraries'].values() if lib.get('default')]
    return TemplateData(
      enabled=self.annotation_processing.enabled,
      # Paths where code generated from annotation processors goes, relative to the content root of
      # each module.
      rel_source_output_dir=os.path.join(self.annotation_processing_relative_path,
                                         self.annotation_processing.sources_dir),
      rel_test_source_output_dir=os.path.join(self.annotation_processing_relative_path,
                                              self.annotation_processing.test_sources_dir),
      default_annotation_processor=True,
      processors=[{'class_name' : processor}
                  for processor in self.annotation_processing.processors],
      classpath=classpath,
      profiles=list(self._generate_annotation_processor_profile_templates()),
      relative_to_content_root=self.annotation_processing_relative_to_content_root,
    )

  @memoized_property
  def project_template(self):
    target_levels = {Revision.lenient(platform['target_level'])
                     for platform in self.blob['jvm_platforms']['platforms'].values()}
    lang_level = max(target_levels) if target_levels else Revision(1, 8)

    configured_project = TemplateData(
      root_dir=get_buildroot(),
      outdir=self.output_directory,
      git_root=Git.detect_worktree(),
      modules=self.module_templates_by_filename.values(),
      java=TemplateData(
        encoding=self.java_encoding,
        maximum_heap_size=self.java_maximum_heap_size,
        jdk='{0}.{1}'.format(*lang_level.components[:2]),
        language_level='JDK_{0}_{1}'.format(*lang_level.components[:2]),
      ),
      resource_extensions=[],
      scala=None,
      checkstyle_classpath=';'.join([]),
      debug_port=self.debug_port,
      annotation_processing=self.annotation_processing_template,
      extra_components=[],
      junit_tests=self._junit_tests_config(),
      global_junit_vm_parameters=' '.join(self.global_junit_jvm_options),
    )
    return configured_project

  @memoized_property
  def module_templates_by_filename(self):
    return dict(self._generate_module_templates())

  @property
  def global_junit_jvm_options(self):
    # NB(gmalmquist): This is a hacky way to get at the [jvm.test.junit] 'options' option.
    return self.context.options.for_scope('jvm.test.junit').get('options') or ()

  def _junit_tests_config(self):
    junit_tests = []
    for module, target in self.modules_and_targets:
      if target.get('pants_target_type') != 'java_tests':
        continue
      # NB(gmalmquist): The export goal doesn't give us enough info about junit tests currently, so
      # we have to extract the info from the actual target graph.
      pants_target = self.context.build_graph.get_target_from_spec(target.get('spec'))
      working_directory = (os.path.abspath(pants_target.cwd) if pants_target.cwd
                           else module.directory)
      test_directory = os.path.join(get_buildroot(), pants_target.payload.sources.rel_path)

      jvm_options = OrderedSet(['-ea'])
      jvm_options.update(pants_target.payload.extra_jvm_options)
      jvm_options.update(self.global_junit_jvm_options)

      junit_tests.append(TemplateData(
        module_name=module.name,
        test_name='All in {}'.format(os.path.relpath(module.directory, get_buildroot())),
        test_directory=test_directory,
        working_directory=working_directory,
        vm_parameters=' '.join(jvm_options),
      ))
    return junit_tests

  def _generate_annotation_processor_profile_templates(self):
    """Computes data for annotation processing profiles.

    These go into the project.ipr in the <annotationProcessing>, in blocks that look like:

    <profile default="false" name="others" enabled="true">
      <sourceOutputDir name="../../../generated">
      <sourceTestOutputDir name="../../../generated_tests">
      <processor name="com.squareup.integration.persistence.criteriabuilders.codegen.SourceProcessor" />
      <processorPath useClasspath="true">
        <entry name="path-to-jar-file.jar" />
      </processorPath>
      <!-- Modules which use this profile. -->
      <module name="franklin" />
    </profile>
    """
    internal_processors = set(self.annotation_processing.codegen_processors)
    global_processors = set(self.annotation_processing.processors)
    for annotation_module in self.modules:
      if not annotation_module.defined_annotation_processors:
        continue
      # We only need to explicitly define annotation processors which generate code. Other kinds of
      # annotation processing occur implicitly.
      if any(p in internal_processors for p in annotation_module.defined_annotation_processors):
        for module_name in annotation_module.transitive_dependees():
          annotated_module =  self.modules_by_name[module_name]
          annotated_module.annotation_processing_dependencies.add(annotation_module)

    all_libraries = set()
    if 'libraries' in self.blob:
      all_libraries = {lib['default'] for lib in self.blob['libraries'].values()
                       if lib.get('default')}

    modules_by_profile = defaultdict(set) # Profiles are sets of annotation processors.
    libraries_by_profile = defaultdict(OrderedSet)
    for module in self.modules:
      profile = frozenset(module.annotation_processing_dependencies)
      modules_by_profile[profile].add(module)
      libraries_by_profile[profile].update(module.libraries['default'])
      for dependency in module.transitive_dependencies():
        libraries_by_profile[profile].update(self.modules_by_name[dependency].libraries['default'])

    for index, profile in enumerate(sorted(modules_by_profile, key=len)):
      processors = sorted(reduce(set.union, [m.defined_annotation_processors for m in profile],
                                 global_processors))
      processor_name = self.infer_processor_name(index, processors)
      enabled = modules_by_profile[profile] and processors

      # NB(gmalmquist):
      # We have to take the union of all libraries defined in the json blob, and all libraries in
      # the transitive dependency graph of the module. The former is to pick up global autovalue
      # libraries, and the latter is to pick up annotation processing jars that we've injected for
      # intellij's benefit after getting the export blob. The vast majority of these will be
      # identical; ironically, in most cases we probably only care about the ones which are
      # different between the two sets (so an xor might be more appropriate), but I don't know
      # whether that is universally the case so this is safer.
      processor_libraries = sorted(set.union(all_libraries, libraries_by_profile[profile]))
      yield TemplateData(
        name=processor_name,
        enabled='true' if enabled else 'false',
        processors=processors,
        modules=sorted(module.name for module in modules_by_profile[profile]),
        classpath=processor_libraries,
      )

  def _create_synthetic_annotation_processing_modules(self):
    yield self.Module(self, os.path.join(self.workdir, 'annotation-processing-code'), [],
                      name='annotation-processing-code')

  def _setup_annotation_processing_dependencies(self):
    requested_codegen_processors = set(self.annotation_processing.codegen_processors)
    codegenerators = set()
    for module in self.modules:
      if any(p in requested_codegen_processors for p in module.defined_annotation_processors):
        codegenerators.add(module.name)

    annotation_processing_code = self.modules_by_name['annotation-processing-code']
    annotation_processing_code.dependencies.update(codegenerators)

    transitive_codegenerators = set()
    for name in codegenerators:
      if name in transitive_codegenerators:
        continue
      module = self.modules_by_name[name]
      transitive_codegenerators.update(module.transitive_dependencies())
    transitive_codegenerators.update(codegenerators)

    for module in self.modules:
      if module != annotation_processing_code and module.name not in transitive_codegenerators:
        module.dependencies.add(annotation_processing_code.name)
    return annotation_processing_code

  def _generate_module_templates(self):
    annotation_processing_code = self._setup_annotation_processing_dependencies()
    language_level = 'JDK_1_8' # Default.

    for module in sorted(self.modules, key=lambda m: m.directory):
      if module.name == annotation_processing_code.name:
        continue
      module.excludes.update(self._maven_excludes(module.directory))
      sources_by_root = {}
      for target_data in module.targets:
        language_level = self._java_language_level(target_data)
        for root in target_data['roots']:
          source_root = root['source_root']
          package_prefix = root['package_prefix']
          if not source_root.startswith(module.directory):
            continue
          maven_excludes = self._maven_excludes(os.path.relpath(source_root, get_buildroot()))
          module.excludes.update(maven_excludes)
          if self.maven_style:
            # Truncate source root, so that targets are listed under src/test/** rather than
            # src/test/com/foobar/package1/*, src/test/com/foobar/package2/* individually.
            package_path_suffix = '{}{}'.format(os.sep, package_prefix.replace('.', os.sep))
            if source_root.endswith(package_path_suffix) and \
                            len(module.directory) < len(source_root) - len(package_path_suffix):
              source_root = source_root[:-len(package_path_suffix)]
              package_prefix = None
            if '/src/test/' in '/{}/'.format(source_root):
              # Infer test target type by the presence of src/test in the path.
              if target_data['target_type'] == 'RESOURCE':
                target_data['target_type'] = 'TEST_RESOURCE'
              elif target_data['target_type'] == 'SOURCE':
                target_data['target_type'] = 'TEST'
          if source_root in sources_by_root:
            # If a target already claimed this source root, pick a single winner based on type.
            previous = _TARGET_TYPE_HIERARCHY.get(sources_by_root[source_root].raw_target_type, -1)
            current = _TARGET_TYPE_HIERARCHY.get(target_data['target_type'], -1)
            if previous < current:
              continue
          sources_by_root[source_root] = (TemplateData(
            path=source_root,
            package_prefix=package_prefix,
            is_test='true' if self._is_test(target_data) else 'false',
            content_type=self._content_type(target_data),
            raw_target_type=target_data['target_type'],
          ))
      sources = sources_by_root.values()

      content_roots = []
      main_content_root = dict(
        root_dir=module.directory if module.directory not in self.placeholder_modules else None,
        sources=[],
        exclude_paths=[],
      )
      if module.targets:
        main_content_root['sources'].extend(sources)
        main_content_root['exclude_paths'].extend(target_data.get('excludes', ()))

      module_group = self._infer_parent_module(module)

      python = any(target.get('python_interpreter') for target in module.targets)
      external_libraries = TemplateData(**{conf: list(jars)
                                           for conf, jars in module.libraries.items()})

      safe_mkdir(os.path.join(module.output_directory, 'production'))
      safe_mkdir(os.path.join(module.output_directory, 'test'))

      if module.targets:
        safe_mkdir(module.annotation_processing_sources_dir, clean=True)
        safe_mkdir(module.annotation_processing_test_sources_dir, clean=True)

        main_content_root['sources'].extend([
          TemplateData(
            path=module.annotation_processing_sources_dir,
            is_test='false',
            content_type='java-source',
          ),
          TemplateData(
            path=module.annotation_processing_test_sources_dir,
            is_test='true',
            content_type=None,
          ),
        ])

      if main_content_root['sources']:
        content_roots.append(TemplateData(**main_content_root))

      yield module.filename, TemplateData(
        name=module.name,
        path='$PROJECT_DIR$/{}'.format(module.filename),
        content_roots=content_roots,
        bash=self.bash,
        python=python,
        scala=False, # NB(gmalmquist): We don't use Scala, change this if we ever do.
        internal_jars=[], # NB(gmalmquist): These two fields seem to be extraneous.
        internal_source_jars=[],
        external_libraries=external_libraries,
        extra_components=[],
        exclude_folders=sorted(module.excludes | set(self.global_excludes)),
        java_language_level=language_level,
        module_dependencies=module.dependencies_template_data(),
        group=module_group,
        make_jar=module.defined_annotation_processors,
        compile_output=module.output_directory,
      )

    # NB(gmalmquist): This module used to be where all code generated from annotation processors
    # lived. That's not longer the case; each module now houses its own generated annotation
    # processing code (which is markedly less hacky).
    #
    # This module is still used as a way to pull in dependencies on annotation processors that live
    # inside the repo, but doesn't define any content roots.
    yield 'annotation-processing-code.iml', TemplateData(
      root_dir=self.workdir,
      path='$PROJECT_DIR$/annotation-processing-code.iml',
      content_roots=[],
      python=False,
      scala=False,
      java_language_level='JDK_1_7',
      group=self._maybe_repo_prefix('.pants.d'),
      exclude_folders=self.global_excludes,
      module_dependencies=sorted(annotation_processing_code.dependencies_template_data()),
      external_libraries=TemplateData(default=sorted(m.jar_path for m in self.modules
                                                     if m.defined_annotation_processors)),
    )
    root_module_dir = get_buildroot()
    if not self.generate_root_module:
      # Redirect the root module's directory to an empty folder.
      root_module_dir = os.path.join(self.workdir, 'dummy')
      shutil.rmtree(root_module_dir, ignore_errors=True)
      os.makedirs(root_module_dir)
    yield 'java.iml', TemplateData(
      root_dir=root_module_dir,
      path='$PROJECT_DIR$/{}.iml'.format(self.root_repo_name()),
      content_roots=[],
      python=False,
      scala=False,
      java_language_level='JDK_1_8',
      group=None if self.generate_root_module else 'placeholder',
      annotation_processing=None,
      exclude_folders=list(self._maven_excludes(root_module_dir, recurse_up=False)),
      module_dependencies=[],
      external_libraries=[],
    )

  def _maybe_repo_prefix(self, group):
    if self.generate_root_module:
      if not group:
        return self.root_repo_name()
      return os.path.join(self.root_repo_name(), group)
    return group or None

  def _infer_parent_module(self, module):
    if module.directory in self.placeholder_modules or module.name in self.placeholder_modules:
      return 'placeholder'
    if os.path.abspath(module.directory).startswith(self.pants_workdir):
      return self._maybe_repo_prefix('.pants.d')
    buildroot = os.path.abspath(get_buildroot())
    path = os.path.dirname(os.path.relpath(module.directory, buildroot))
    if not path:
      # We're a root-level module, so group us by our own name. This causes all the root-level
      # level projects to be organized in the same block, instead of having two separate blocks
      # of alphabetized projects, with half of them bolded at the bottom. The downside is that it
      # causes root-level modules to be nested inside an empty node with the same name as them in
      # the project view, so you get a directory structure that looks like:
      # * my-module/my-module/src/main/foo
      # But this seems nicer than the alternative. If I'm wrong about this, to change it back just
      # pass None or '' to this function instead of the module name.
      return self._maybe_repo_prefix(module.name)
    # Check if we're under a module. If we are, we don't want to set a group- IntelliJ will properly
    # nest things automatically.
    parent_path = path
    while parent_path:
      if parent_path in self.loaded_module_directories:
        return None
      parent_path = os.path.dirname(parent_path)
    # If we're not at the root-level and we aren't under a module, set the group to the parent
    # directory.
    return self._maybe_repo_prefix(path)

  def _java_language_level(self, target_data):
    if 'platform' not in target_data:
      return None
    target_platform = target_data['platform']
    platforms = self.blob['jvm_platforms']['platforms']
    if target_platform in platforms:
      target_source_level = platforms[target_platform]['source_level']
      return 'JDK_{0}_{1}'.format(*target_source_level.split('.'))
    return None

  def get_module_dependency_scope(self, module_name, dependent_module_name):
    """Sets the value for the scope of the module dependency between a module and a dependency.

    A scope can be a normal compile and runtime dependency, or PROVIDED, meaning that the dependency
    is not inherited transitively.

    For now, this is retrieved from a config setting, but eventually should be discovered by
    looking at an attribute or type of a target.
    """
    overrides = self.provided_module_dependencies
    for key in overrides.keys():
      if module_name.startswith(key):
        if dependent_module_name.startswith(overrides.get(key)):
          self.context.log.info('Setting scope to Provided for {} -> {}'
                                .format(module_name, dependent_module_name))
          return 'PROVIDED'
    return ''
