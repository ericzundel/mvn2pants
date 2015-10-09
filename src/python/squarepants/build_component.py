#!/usr/bin/env python2.7

from abc import ABCMeta, abstractmethod, abstractproperty
import os
import re

from generation_context import GenerationContext
from generation_utils import GenerationUtils
from target_template import Target
from file_utils import file_pattern_exists_in_subdir


class BuildComponent(object):
  """Represents a feature of a maven project that should generate things in BUILD files.

  For example, the MainClassComponent knows when a project should generate a jvm_binary, and
  generates the appropriate code to go in the project's top-level BUILD file.
  """
  __metaclass__ = ABCMeta

  class DuplicateTargetException(Exception):
    """Thrown when a two targets with the same name are created for the same BUILD file."""

  def __init__(self, pom_file, generation_context=None):
    """Creates a new BuildComponent for the given pom file.
    :param squarepants.pom_file.PomFile pom_file: the extracted information from a project's
      pom.xml.
    :return:
    """
    self.pom = pom_file
    self.gen_context = generation_context or GenerationContext()

  @abstractproperty
  def exists(self):
    """Whether this build component exists (should be generated) for the project pom.xml."""

  @abstractmethod
  def generate(self):
    """Generates and returns code that should be added to the top-level BUILD file for this pom.xml.

    Also creates any BUILD files for subdirectories which pertain to this component.
    """

  def get_project_target_name(self, name):
    """Convenience function to return the inferred target name appropriate for this component.

    For BUILD.gen files this will just be 'name', but for BUILD.aux's this will be name-aux.
    """
    return self.gen_context.infer_target_name(self.pom.directory, name)

  def has_project_target(self, name):
    """Whether the project-level BUILD file already has a target with the given name."""
    return self.get_project_target_name(name) in self.pom.project_target_names

  def format_project(self, target_type, **kwargs):
    return target_type.format(symbols=self.pom.properties, file_name=self.pom.path,
                              **kwargs)

  def create_project_target(self, target_type, name, **kwargs):
    """Formats and returns a target for the project-level BUILD file.

    Registers the target's name in project_target_names.
    :return: the formatted target string.
    """
    name = self.get_project_target_name(name)
    if name in self.pom.project_target_names:
      raise BuildComponent.DuplicateTargetException("Duplicate target '{name}' in {build}."
                                                    .format(name=name,
                                                            build=self.pom.directory))
    self.pom.project_target_names.add(name)
    return self.format_project(target_type, name=name, **kwargs)

  def get_jvm_platform_name(self):
    # if self.is_test:
    #   return self.get_jvm_platform_test_name()
    options = self.pom.java_options
    if not any([options.target_level, options.source_level, options.compile_args]):
      return None

    args = [GenerationUtils.symbol_substitution(self.pom.properties, arg, symbols_name=self.pom.path)
            for arg in options.compile_args]

    return self.gen_context.jvm_platform(options.target_level,
                                         options.source_level,
                                         args,)

  def get_jvm_platform_test_name(self):
    return self.get_jvm_platform_name()


class SubdirectoryComponent(BuildComponent):
  """Represents a BuildComponent whose existence is inferred from a project's directory structure.
  """
  __metaclass__ = ABCMeta

  @abstractproperty
  def subdirectory(self):
    """The subdirectory that indicates whether this component exists, relative to the project pom
    directory.
    """

  @abstractproperty
  def target_type(self):
    """The target type generated, e.g. Target.java_protobuf_library."""

  @abstractproperty
  def target_name(self):
    """The name of the generated target, e.g. 'proto'."""

  @abstractproperty
  def pom_dependency_list(self):
    """Returns the list that this target injects dependencies into.

    Eg, pom.lib_deps.
    """

  @property
  def target_spec(self):
    """The spec for the (primary) target this component generates."""
    return self.gen_context.format_spec(self.directory, self.target_name)

  def generate_subdirectory_code(self):
    """Generates and returns code for the subdirectory's BUILD file."""
    return self.format_project(self.target_type, **self.generate_target_arguments())

  def generate_target_arguments(self):
    """Generates the arguments that will be passed into the target_type.format().

    Subclasses are expected to update the arguments appropriately.
    """
    return {
      'name': self.gen_context.infer_target_name(self.directory, self.target_name),
    }

  def generate_project_dependency_code(self):
    """Generates a dependencies() target to be injected into the project BUILD file."""
    return self.create_project_target(Target.dependencies,
      name=self.target_name,
      dependencies=[self.target_spec],
    )

  @property
  def directory(self):
    """Convenience property to get the directory path relative to the working directory."""
    return os.path.join(self.pom.directory, self.subdirectory)

  @property
  def exists(self):
    subdir = self.directory
    return os.path.exists(subdir) and os.path.isdir(subdir) and os.listdir(subdir)

  def inject_generated_dependencies(self):
    """Powers the mechanism by which generated targets are injected as dependencies into other
    generated targets.

    Updates a dependency list in the PomFile, like lib_deps or test_deps, according to
    the pom_dependency_list.
    """
    if self.pom_dependency_list is not None:
      self.pom_dependency_list.append(self.target_spec)

  def generate(self):
    subdir = self.directory
    if not os.path.exists(subdir):
      os.makedirs(subdir)
    self.gen_context.write_build_file(self.directory, self.generate_subdirectory_code())
    project_code = self.generate_project_dependency_code()
    self.inject_generated_dependencies()
    return project_code


class JarFilesMixin(object):
  """Methods for BuildComponents that also generated a jar_library() that they depend on."""
  @property
  def jar_deps(self):
    """Jar dependencies from pom.xml."""
    return self.pom.lib_jar_deps

  @property
  def jar_target_contents(self):
    """Formatted jar_library() for injection into the subdirectory BUILD file."""
    return self.format_jar_library(self.gen_context.infer_target_name(self.directory, 'jar_files'),
                                   [str(s).strip() for s in self.jar_deps if s],
                                   pom_file=self.pom)

  @property
  def jar_target_spec(self):
    """Spec address for the generated jar_library()."""
    if not self.jar_target_contents:
      return ''
    return self.gen_context.format_spec(
        '', self.gen_context.infer_target_name(self.directory, 'jar_files'))

  def generate_subdirectory_code(self):
    return super(JarFilesMixin, self).generate_subdirectory_code() + self.jar_target_contents

  @classmethod
  def format_jar_library(cls, target_name, jar_deps, pom_file=None):
    """Given a list of jar dependencies, format a jar_library target.

    Exposed for testing.
    :param target_name: the target name for the jar_library.
    :param jar_deps: - <jar> dependency names to add to the jar_library.
    :returns: A jar_library declaration.
    :rtype: string
    """
    if not jar_deps:
      return ''
    return Target.jar_library.format(
      name=target_name,
      jars=sorted(set(jar_deps)),
      symbols=pom_file.properties if pom_file else None,
      file_name=pom_file.path if pom_file else None,
    )


class MainClassComponent(BuildComponent):
  """Generates a jvm_binary if the pom.xml specifies a main class."""

  @property
  def main_class(self):
    return self.pom.deps_from_pom.get_property('project.mainclass')

  @property
  def exists(self):
    return True if self.main_class else False

  def generate(self):
    main_class = self.main_class
    dependencies = [
      self.gen_context.format_spec(name=self.get_project_target_name('lib')),
    ]
    deploy_excludes = self.pom.signed_jars_formatted_excludes or None
    signed_jar_target = ''
    if deploy_excludes:
      signed_jar_target_name = '{}-signed-jars'.format(self.pom.default_target_name)
      signed_jar_target = self.create_project_target(Target.signed_jars,
         name=signed_jar_target_name,
         dependencies=self.pom.signed_jars_dependencies,
         strip_version = str(self.pom.signed_jars_strip_version),
      )
      dependencies.append(
        self.gen_context.format_spec(name=self.get_project_target_name(signed_jar_target_name))
      )
    manifest_entries = self.pom.manifest_entries or None
    return self.create_project_target(Target.jvm_binary,
      name=self.pom.default_target_name,
      main=main_class,
      basename=self.pom.deps_from_pom.artifact_id,
      dependencies=dependencies,
      manifest_entries=manifest_entries,
      deploy_excludes=deploy_excludes,
      platform=self.get_jvm_platform_name(),
      shading_rules=self.pom.shading_rules or None,
    ) + signed_jar_target


class MainResourcesComponent(SubdirectoryComponent):
  """Generates targets for src/main/resources."""

  @property
  def subdirectory(self):
    return 'src/main/resources'

  @property
  def target_type(self):
    return Target.resources

  @property
  def target_name(self):
    return 'resources'

  @property
  def pom_dependency_list(self):
    return self.pom.resources

  def generate_target_arguments(self):
    args = super(MainResourcesComponent, self).generate_target_arguments()
    args.update({
      'sources': "rglobs('*', exclude=[globs('BUILD*')])",
      'dependencies': [],
    })
    return args

  def generate_project_dependency_code(self):
    pass


class TestResourcesComponent(MainResourcesComponent):
  """Generates targets for src/test/resources."""

  @property
  def subdirectory(self):
    return 'src/test/resources'

  @property
  def pom_dependency_list(self):
    return self.pom.test_resources


class MainProtobufLibraryComponent(JarFilesMixin, SubdirectoryComponent):
  """Generates targets for src/main/proto.

  Some minor hacks in the 'exists' property of this target to deal with external-protos,
  but not nearly as bad as before.
  """

  @property
  def subdirectory(self):
    return 'src/main/proto'

  @property
  def exists(self):
    if MainExternalProtosComponent(self.pom).exists:
      return False
    return super(MainProtobufLibraryComponent, self).exists

  @property
  def target_type(self):
    return Target.java_protobuf_library

  @property
  def target_name(self):
    return 'proto'

  @property
  def pom_dependency_list(self):
    return self.pom.lib_deps

  @property
  def _deps(self):
    """Dependencies that get injected into the generated target's dependency list."""
    return self.pom.lib_deps

  def generate_target_arguments(self):
    args = super(MainProtobufLibraryComponent, self).generate_target_arguments()
    args.update({
      'sources': "rglobs('*.proto')",
      'imports': [],
      'dependencies': format_dependency_list(self._deps + [self.jar_target_spec]),
      'platform': self.get_jvm_platform_name(),
    })
    return args


class TestProtobufLibraryComponent(MainProtobufLibraryComponent):
  """Generates targets for src/test/proto."""

  @property
  def subdirectory(self):
    return 'src/test/proto'

  @property
  def pom_dependency_list(self):
    return self.pom.test_deps

  @property
  def _deps(self):
    return self.pom.lib_deps + self.pom.test_deps

  def generate_project_dependency_code(self):
    pass

  def generate_target_arguments(self):
    args = super(TestProtobufLibraryComponent, self).generate_target_arguments()
    args['platform'] = self.get_jvm_platform_test_name()
    return args


class MainWireLibraryComponent(JarFilesMixin, SubdirectoryComponent):
  """Generates targest for src/main/wire_proto."""

  def __init__(self, *vargs, **kwargs):
    super(MainWireLibraryComponent, self).__init__(*vargs, **kwargs)
    wire_info = self.pom.wire_info
    wire_include_targets = {}
    wire_include_libraries = []
    wire_include_patterns = []
    for artifact in wire_info.artifacts:
      properties = wire_info.artifacts[artifact]
      if ('includes' in properties and 'output_directory' in properties
          and 'wire_proto' in properties['output_directory']):
        if ',' in properties['includes']:
          includes = properties['includes'].split(',')
        else:
          includes = [ properties['includes'], ]
        unpack_target_name = 'wire-source-set-{count}'.format(count=len(wire_include_targets)+1)
        wire_include_libraries.append(
            "'3rdparty:{group_id}.{artifact_id}'".format(group_id=artifact[0], artifact_id=artifact[1])
        )
        wire_include_patterns.extend(["'{}'".format(pattern) for pattern in includes])
    if wire_include_libraries:
      wire_include_targets[unpack_target_name] = Target.unpacked_jars.format(
          name=unpack_target_name,
          libraries=wire_include_libraries,
          include_patterns=wire_include_patterns,
          exclude_patterns=[],
      )
    self._wire_include_targets = [self.gen_context.format_spec('', name)
                                  for name in wire_include_targets.keys()]
    self._unpacked_jar_contents = '\n'.join(sorted(wire_include_targets.values()))

  @property
  def subdirectory(self):
    return 'src/main/wire_proto'

  @property
  def target_type(self):
    return Target.java_wire_library

  @property
  def target_name(self):
    return 'wire_proto'

  @property
  def pom_dependency_list(self):
    return self.pom.lib_deps

  @property
  def _deps(self):
    """Dependencies that get injected into the generated target's dependency list."""
    return self.pom.lib_deps

  @property
  def _normalized_proto_paths(self):
    def normalize(path):
      path = GenerationUtils.symbol_substitution(self.pom.properties, path,
                                                 symbols_name=self.pom.path)
      return os.path.normpath(path)
    return map(normalize, self.pom.wire_info.proto_paths)

  @property
  def _deps_from_proto_paths(self):
    proto_paths = self._normalized_proto_paths
    directory = '{}{}'.format(os.path.normpath(self.directory), os.sep)
    proto_paths = [path for path in proto_paths
                   if not '{}{}'.format(path, os.sep).startswith(directory)]
    for path in proto_paths:
      if not os.path.exists(path):
        print('Warning: directory referenced in <protoPath>{}</protoPath> does not exist! '
              '(referenced by {})'
              .format(path, self.pom.path))
    proto_paths = filter(os.path.exists, proto_paths)
    return proto_paths

  def generate_target_arguments(self):
    args = super(MainWireLibraryComponent, self).generate_target_arguments()
    args.update({
      'sources': self.pom.wire_info.protos or "rglobs('*.proto')",
      'dependencies': format_dependency_list(self._deps + [self.jar_target_spec]
                                             + self._wire_include_targets
                                             + self._deps_from_proto_paths),
      'roots': self.pom.wire_info.roots,
      'service_factory': self.pom.wire_info.service_factory,
      'enum_options': self.pom.wire_info.enum_options,
      'no_options': self.pom.wire_info.no_options,
      'registry_class': self.pom.wire_info.registry_class,
      'platform': self.get_jvm_platform_name(),
    })
    return args

  def generate_subdirectory_code(self):
    return super(MainWireLibraryComponent, self).generate_subdirectory_code() + self._unpacked_jar_contents


class TestWireLibraryComponent(MainWireLibraryComponent):
  """Generates targets for src/test/wire_proto."""

  @property
  def subdirectory(self):
    return 'src/test/wire_proto'

  @property
  def pom_dependency_list(self):
    return self.pom.test_deps

  @property
  def _deps(self):
    return self.pom.lib_deps + self.pom.test_deps

  def generate_project_dependency_code(self):
    pass

  def generate_target_arguments(self):
    args = super(TestWireLibraryComponent, self).generate_target_arguments()
    args['platform'] = self.get_jvm_platform_test_name()
    return args



class MainJavaLibraryComponent(JarFilesMixin, SubdirectoryComponent):
  """Generates targets for src/main/java."""

  @property
  def subdirectory(self):
    return 'src/main/java'

  @property
  def target_type(self):
    return Target.java_library

  @property
  def target_name(self):
    return 'lib'

  @property
  def pom_dependency_list(self):
    return None

  @property
  def _deps(self):
    """Dependencies that get injected into the generated target's dependency list."""
    return self.pom.lib_deps

  def generate_target_arguments(self):
    args = super(MainJavaLibraryComponent, self).generate_target_arguments()
    args.update({
      'sources': "rglobs('*.java')",
      'dependencies': format_dependency_list(self._deps + [self.jar_target_spec]),
      'resources': self.pom.resources,
      'groupId': self.pom.deps_from_pom.group_id,
      'artifactId': self.pom.deps_from_pom.artifact_id,
      'platform': self.get_jvm_platform_name(),
    })
    return args


class TestJavaLibraryComponent(MainJavaLibraryComponent):
  """Generates junit_tests for src/tests/java."""

  INTEGRATION_TEST_PATTERN=re.compile(r'.*IT.java')

  @property
  def subdirectory(self):
    return 'src/test/java'

  @property
  def jar_deps(self):
    return self.pom.lib_jar_deps + self.pom.test_jar_deps

  @property
  def _deps(self):
    deps = self.pom.lib_deps + self.pom.test_deps + ["'testing-support/src/main/java:lib'"]
    main_lib = MainJavaLibraryComponent(self.pom)
    if main_lib.exists:
      deps.append(main_lib.target_spec)
    return deps

  def generate_target_arguments(self):
    args = super(TestJavaLibraryComponent, self).generate_target_arguments()
    args.update({
      'sources': "rglobs('*.java')",
      'resources': self.pom.test_resources,
      'platform': self.get_jvm_platform_test_name(),
    })
    return args

  def generate_subdirectory_code(self):
    test_target = self.format_project(Target.junit_tests,
      name=self.gen_context.infer_target_name(self.directory, 'test'),
      sources="rglobs('*Test.java')",
      cwd=self.pom.directory,
      dependencies=["':{}'".format(self.gen_context.infer_target_name(self.directory, 'lib'))],
      platform=self.get_jvm_platform_test_name(),
    )

    if file_pattern_exists_in_subdir(self.directory, self.INTEGRATION_TEST_PATTERN):
      test_target += self.format_project(Target.junit_tests,
                              name=self.gen_context.infer_target_name(self.directory,
                                                                      'integration-tests'),
                              sources="rglobs('*IT.java')",
                              cwd=self.pom.directory,
                              tags=['integration'],
                              dependencies=["':{}'".format(
                                self.gen_context.infer_target_name(self.directory, 'lib'))],
                              platform=self.get_jvm_platform_test_name())

    return test_target + super(TestJavaLibraryComponent,
                               self).generate_subdirectory_code()

  def generate_project_dependency_code(self):
    return self.create_project_target(Target.dependencies,
      name='test',
      dependencies=[self.gen_context.format_spec(self.directory, 'test')],
    )


class PlaceholderLibraryComponent(BuildComponent):
  """Generates an empty target() if there is no src/main/java."""

  @property
  def exists(self):
    return not self.has_project_target('lib')

  def generate(self):
    deps = filter(self.has_project_target, ['proto', 'wire_proto',])
    if not deps:
      return self.create_project_target(Target.placeholder, name='lib')
    else:
      return self.create_project_target(Target.dependencies,
        name='lib',
        dependencies=[self.gen_context.format_spec('', dep) for dep in deps],
      )


class ExternalProtosMixin(object):
  """Contains helper methods to accomplish the external-protos hackery."""

  def __init__(self, *vargs, **kwargs):
    super(ExternalProtosMixin, self).__init__(*vargs, **kwargs)
    self._external_protos_contents = None
    self._external_protos_arguments = None

  @property
  def is_external_protos(self):
    if not 'external-protos.mask' in self.pom.properties:
      return False
    subdir = self.directory
    if os.path.exists(subdir) and os.path.isdir(subdir) and os.listdir(subdir):
      return True
    return not self.subdirectory.startswith('src/test/')

  def _compute_external_protos(self):
    include_patterns = []
    exclude_patterns = []
    versioned_jar_library = ''
    for pattern in self.pom.properties['external-protos.mask'].split(','):
      include_patterns.append("'{0}'".format(pattern))
    for pattern in self.pom.properties['external-protos.exclude-mask'].split(','):
      if pattern:
        exclude_patterns.append("'{0}'".format(pattern))
    if 'external-protos.version' in self.pom.properties:
      libraries = ["':versioned-all-protos'",]
      versioned_jar_library = Target.jar_library.format(
        name="versioned-all-protos",
        jars=[Target.jar.format(org='com.squareup.protos', name='all-protos',
                                rev=self.pom.properties['external-protos.version'],
                                symbols=self.pom.properties,
                                file_name=self.pom.path)],
        symbols=self.pom.properties,
        file_name=self.pom.path,
      )
    else:
      # TODO(zundel): Need to get properties from the parent poms, then we could fill
      # this in with the above section. for now, use the target from a hand-written build BUILD
      libraries = ["'parents/external-protos:latest-all-protos'"]
    self._external_protos_contents = Target.unpacked_jars.format(
      name='proto-source-set',
      libraries=libraries,
      include_patterns=include_patterns,
      exclude_patterns=exclude_patterns,
    ) + versioned_jar_library
    # Override sources with a reference to the source set
    self._external_protos_arguments = {
      'sources': "from_target(':proto-source-set')"
    }

  @property
  def external_protos_contents(self):
    if self._external_protos_contents is None:
      self._compute_external_protos()
    return self._external_protos_contents

  @property
  def external_protos_arguments(self):
    if self._external_protos_arguments is None:
      self._compute_external_protos()
    return self._external_protos_arguments


class MainExternalProtosComponent(ExternalProtosMixin, MainProtobufLibraryComponent):
  """Generates src/main/proto for external-protos."""

  @property
  def exists(self):
    return self.is_external_protos

  def generate_target_arguments(self):
    args = super(MainExternalProtosComponent, self).generate_target_arguments()
    args.update(self.external_protos_arguments)
    return args

  def generate_subdirectory_code(self):
    code = super(MainExternalProtosComponent, self).generate_subdirectory_code()
    return code + self.external_protos_contents


class TestExternalProtosComponent(ExternalProtosMixin, TestProtobufLibraryComponent):
  """Generates src/test/proto for external-protos."""

  @property
  def exists(self):
    return self.is_external_protos

  def generate_target_arguments(self):
    args = super(MainExternalProtosComponent, self).generate_target_arguments()
    args.update(self.external_protos_arguments)
    return args

  def generate_subdirectory_code(self):
    code = super(MainExternalProtosComponent, self).generate_subdirectory_code()
    return code + self.external_protos_contents


class PlaceholderTestComponent(BuildComponent):
  """Generates a 'test' target that just compiles java and proto files."""

  @property
  def exists(self):
    return not self.has_project_target('test')

  def generate(self):
    return self.create_project_target(Target.dependencies,
      name=self.gen_context.infer_target_name(self.pom.directory, 'test'),
      dependencies=[':lib'],
    )


VALID_SPEC_PATTERN = re.compile(r'[^:A-Za-z0-9_/.-]')

def normalize_spec(spec):
  spec = VALID_SPEC_PATTERN.sub('', spec)
  colon = spec.rfind(':')
  if colon < 0:
    return spec
  path, name = spec[:colon], spec[colon+1:]
  if not path:
    return spec
  if not name:
    return path
  file_name = os.path.basename(path)
  if file_name == name:
    return path
  return spec


def format_dependency_list(specs):
  """Sorts a dependency list, putting 'local' dependencies at the end."""
  specs = set(filter(None, map(normalize_spec, specs)))
  local_specs = {s for s in specs if s.startswith(':')}
  global_specs = {s for s in specs if s not in local_specs}
  used = set()
  results = []
  for spec in (sorted(global_specs) + sorted(local_specs)):
    if spec not in used:
      results.append(spec)
      used.add(spec)
  return ["'{}'".format(spec) for spec in results]


# Order matters here. This determines the order that targets and subdirectory BUILD files
# will be generated, for each project.
BuildComponent.TYPE_LIST = [
  MainClassComponent,
  MainResourcesComponent,
  TestResourcesComponent,
  MainProtobufLibraryComponent,
  MainExternalProtosComponent,
  MainWireLibraryComponent,
  TestProtobufLibraryComponent,
  TestExternalProtosComponent,
  TestWireLibraryComponent,
  MainJavaLibraryComponent,
  PlaceholderLibraryComponent,
  TestJavaLibraryComponent,
  PlaceholderTestComponent,
]
