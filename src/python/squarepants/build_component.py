#!/usr/bin/env python2.7

import getpass
import logging
import os
import re
import sys
from abc import ABCMeta, abstractmethod, abstractproperty
from collections import defaultdict, namedtuple, OrderedDict
from textwrap import dedent

from generation_context import GenerationContext
from generation_utils import GenerationUtils
from target_template import Target


logger = logging.getLogger(__name__)


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

    # There is a bug in Target.jar_library.format(). See test_target_template.py
    #return Target.jar_library.format(
    #  name=target_name,
    #  jars=sorted(set(jar_deps)),
    #  symbols=pom_file.properties if pom_file else None,
    #  file_name=pom_file.path if pom_file else None,
    #)
    jar_library = dedent('''
        jar_library(name='{name}',
          jars=[{jars}
          ],
        )
      ''').format(name=target_name,
                  jars=','.join('\n{}{}'.format(' '*4, jar) for jar in sorted(set(jar_deps))))
    if pom_file:
      jar_library = GenerationUtils.symbol_substitution(pom_file.properties, jar_library)
    return GenerationUtils.autoindent(jar_library)


class MainClassComponent(BuildComponent):
  """Generates a jvm_binary if the pom.xml specifies a main class."""

  @property
  def exists(self):
    return True if self.pom.mainclass else False

  def generate(self):
    main_class = self.pom.mainclass
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
    extra_fingerprint_files = []
    app_manifest = 'app-manifest.yaml'
    if os.path.exists(os.path.join(os.path.dirname(self.pom.path), app_manifest)):
      extra_fingerprint_files.append(app_manifest)
    fingerprint_target = self.create_project_target(
      Target.fingerprint,
      name='extra-files',
      sources=extra_fingerprint_files,
      dependencies=None,
    )
    return self.create_project_target(Target.jvm_binary,
      name=self.pom.default_target_name,
      main=main_class,
      basename=self.pom.artifact_id,
      dependencies=dependencies,
      manifest_entries=manifest_entries,
      deploy_excludes=deploy_excludes,
      platform=self.get_jvm_platform_name(),
      shading_rules=self.pom.shading_rules or None,
    ) + signed_jar_target + fingerprint_target


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

  @property
  def _proto_sources(self):
    return "rglobs('*.proto')"

  def generate_target_arguments(self):
    args = super(MainProtobufLibraryComponent, self).generate_target_arguments()
    #  If there is no src/main/java:lib target, then we don't need to tack
    # on a uniqifying suffix, this is the only artifact that will be published for this
    # package
    artifactId_suffix = ('-proto' if MainJavaLibraryComponent(self.pom).exists else '')
    dependencies = self._deps + [self.jar_target_spec, ':{}'.format(self._proto_sources_name)]
    args.update({
      'sources': self._proto_sources,
      'imports': [],
      'dependencies': format_dependency_list(dependencies),
      'platform': self.get_jvm_platform_name(),
      'groupId' : self.pom.deps_from_pom.group_id,
      'artifactId' : self.pom.deps_from_pom.artifact_id + artifactId_suffix,
    })
    return args

  @property
  def _proto_sources_name(self):
    return self.gen_context.infer_target_name(self.directory, 'proto-sources')

  @property
  def proto_resources_contents(self):
    return self.format_project(
      Target.resources,
      name=self._proto_sources_name,
      sources=self._proto_sources,
    )

  @property
  def wire_proto_path_contents(self):
    return self.format_project(
      Target.wire_proto_path,
      name=self.gen_context.infer_target_name(self.directory, 'path'),
      sources=self._proto_sources,
      dependencies=format_dependency_list(find_wire_proto_paths(self._deps)),
    )

  def generate_subdirectory_code(self):
    return super(MainProtobufLibraryComponent, self).generate_subdirectory_code() \
           + self.wire_proto_path_contents + self.proto_resources_contents


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
  def artifactId_suffix(self):
    return ''

  @property
  def _deps(self):
    """Dependencies that get injected into the generated target's dependency list."""
    return self.pom.lib_deps

  def generate_target_arguments(self):
    args = super(MainJavaLibraryComponent, self).generate_target_arguments()
    library_deps = self._deps + [self.jar_target_spec]
    module_path = os.path.dirname(self.pom.path)
    if self.pom.mainclass:
      spec_name = self.gen_context.infer_target_name(module_path, 'extra-files')
      library_deps.append(self.gen_context.format_spec(path=module_path, name=spec_name))
    artifactId = self.pom.deps_from_pom.artifact_id + self.artifactId_suffix
    args.update({
      'sources': "rglobs('*.java')",
      'dependencies': format_dependency_list(library_deps),
      'resources': self.pom.resources,
      'groupId': self.pom.deps_from_pom.group_id,
      'artifactId': artifactId,
      'platform': self.get_jvm_platform_name(),
    })
    return args


class TestJavaLibraryComponent(MainJavaLibraryComponent):
  """Generates junit_tests for src/test/java."""

  INTEGRATION_TEST_PATTERN=re.compile(r'.*IT.java')

  @property
  def artifactId_suffix(self):
    return '-test'

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
    common_args = dict(
      cwd=self.pom.directory,
      extra_env_vars=self.pom.java_options.test_env_vars or None,
      extra_jvm_options=self.pom.java_options.test_jvm_args or None,
      platform=self.get_jvm_platform_test_name(),
      dependencies=["':{}'".format(self.gen_context.infer_target_name(self.directory, 'lib'))],
    )

    test_target = self.format_project(Target.junit_tests,
      name=self.gen_context.infer_target_name(self.directory, 'test'),
      sources="rglobs('*Test.java')",
      **common_args
    )

    test_target += self.format_project(Target.junit_tests,
      name=self.gen_context.infer_target_name(self.directory, 'integration-tests'),
      sources="rglobs('*IT.java')",
      tags=['integration'],
      **common_args
    )

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
    deps = filter(self.has_project_target, ['proto',])
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

  @property
  def _proto_sources(self):
    return "from_target(':proto-source-set')"

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


class JooqGenComponent(BuildComponent):

  class JdbcConfig(namedtuple('JdbcConfig', ['url', 'user', 'password'])):
    """Stores information contained in the JDBC stanza for jooq configuration."""

    class MissingConfigError(ValueError):
      """Thrown if there is missing config information."""

    @classmethod
    def from_config_tree(cls, tree):
      """Creates a JdbcConfig database object by parsing the input tree.

      :param :class:`etree.ElementTree.Element` tree: The jooq config tree.
      :rtype JooqGenComponent.JdbcConfig:
      :raises: :class:`JooqGenComponent.JdbcConfig.MissingConfigError` if necessary data is missing.
      """
      tag_prefix = tree.tag[:tree.tag.rfind('}')+1]
      jdbc_prefix = './{0}jdbc/{0}'.format(tag_prefix)
      jdbc_nodes = [tree.find('{}{}'.format(jdbc_prefix, tag)) for tag in cls._fields]
      for name, node in zip(cls._fields, jdbc_nodes):
        if node is None:
          raise cls.MissingConfigError('jOOQ config xml is missing the "{}" tag.'.format(name))
      return cls(*(node.text for node in jdbc_nodes))

  _jooq_target_deps = [
    '3rdparty:org.jooq.jool',
    '3rdparty:org.jooq.jooq',
    '3rdparty:org.jooq.jooq-codegen',
    '3rdparty:org.jooq.jooq-meta',
    'dbmigrate/src/main/java:lib',
  ]

  @property
  def exists(self):
    return self.pom.jooq_info.config_tree is not None

  def generate(self):
    config_data = self._dedent_xml(self.pom.jooq_config)
    config_data = '<configuration>{tail}'.format(tail=config_data[config_data.find('\n'):])
    config_data = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n{body}'.format(
      body=config_data,
    )

    try:
      symbols = dict(self.pom.properties)
      # NB(gmalmquist): We switched to using build_symbols for dynamic properties,
      # however that only works in BUILD files, and this is raw xml. So we have to
      # explicitly define the dynamic properites.
      basedir = os.path.abspath(self.pom.directory)
      symbols.update({
        'basedir': basedir,
        'project.basedir': basedir,
        'project.baseUri': 'file://{}'.format(os.path.realpath(basedir)),
        'project.build.directory': os.path.join(basedir, 'target'),
        'user.name': getpass.getuser(),
      })
      config_data = GenerationUtils.symbol_substitution(symbols, config_data,
                                                        symbols_name=self.pom.path,
                                                        fail_on_missing=True)
    except GenerationUtils.MissingSymbolError as e:
      logger.debug('{} Skipping jooq target generation.'.format(e))
      return ''

    config_path = os.path.join(self.pom.directory, self.gen_context.jooq_config_file)
    with open(config_path, 'w+') as f:
      f.write(config_data.strip())

    setup_target = None
    if not self.pom.jooq_info.skip_setup:
      try:
        setup_target = self._generate_setup_target()
      except self.JdbcConfig.MissingConfigError as e:
        logger.debug('Skipping jooq target generation for {} due to missing jdbc config.\n{}'
                     .format(self.pom.path, e))
        return ''

    jooq_target_deps = list(self._jooq_target_deps)
    if setup_target:
      sql_name = self.gen_context.infer_target_name(self.pom.directory, 'jooq-sql-setup')
      jooq_target_deps.append(':{}'.format(sql_name))

    targets = [
      self.create_project_target(
        Target.jvm_prep_command,
        name='jooq',
        goal='jooq',
        mainclass='org.jooq.util.GenerationTool',
        args=[
          config_path,
        ],
        dependencies=format_dependency_list(jooq_target_deps),
      )
    ]
    if setup_target:
      targets.append(setup_target)
    return '\n'.join(targets)

  def _generate_setup_target(self):
    database = self.JdbcConfig.from_config_tree(self.pom.jooq_config_tree)
    jdbc_prefixes_and_types = [
      ('jdbc:mysql:', 'sql:mysql'),
      ('jdbc:postgresql:', 'sql:postgres'),
    ]
    database_type = None
    for url_prefix, jdbc_type in jdbc_prefixes_and_types:
      if database.url.startswith(url_prefix):
        database_type = jdbc_type
        break
    if database_type is None:
      raise ValueError('Unable to infer jdbc database type from url "{}".'.format(database.url))

    return self.create_project_target(
      Target.jvm_prep_command,
      name='jooq-sql-setup',
      goal='jooq',
      mainclass='com.squareup.dbmigrate.tools.Migrator',
      args=[
        '--url="{}"'.format(database.url),
        '--type="{}"'.format(database_type),
        '--username="{}"'.format(database.user or ''),
        '--password="{}"'.format(database.password or ''),
        '--migrations-dir="{}/${{squareup.migrationsPath}}"'.format(self.pom.directory),
        '--clean',
      ],
      dependencies=[
        'dbmigrate/src/main/java:lib',
      ],
    )

  def _dedent_xml(self, blob):
    pattern = re.compile('^[ ]*')
    lines = blob.rstrip().splitlines()
    indent = sys.maxint
    for i, line in enumerate(lines):
      spaces = pattern.match(line)
      group = spaces.group()
      if not group:
        continue
      if len(group) < indent:
        indent = len(group)
      elif i == len(lines)-1 and indent < len(group):
        indent = len(group)
    return '\n'.join(line[min(indent, len(pattern.match(line).group())):] for line in lines)



VALID_SPEC_PATTERN = re.compile(r'[^:A-Za-z0-9_/.-]')
WIRE_PROTO_PATH_PATTERN = re.compile(r'^[a-z_]+[(]name[ ]*=[ ]*[\'"]path[\'"]')

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


def split_specs_by_category(specs, categories_pattern):
  """Splits the list of specs into a map of (category -> specs in that category).

  :param list specs: The list of dependency specs.
  :param categories_pattern: A compiled regular expression for determining the spec category.
  :return: A map of (category -> list of specs that match that category.
  """
  specs_by_type = defaultdict(list)
  for spec in specs:
    specs_by_type[categories_pattern.match(spec).lastgroup].append(spec)
  return specs_by_type


def format_dependency_list(specs):
  """Sorts a dependency list, organizing 3rdparty dependencies separately.

  We put 3rdparty dependencies at the top of the dependency list in the order they originally appear
  in from the pom file they are parsed from. This is an attempt to be consistent in the classpath
  ordering between Maven and Pants for resolving conflicts when fully-qualified class names collide.

  Other dependency specs are sorted normally.

  :param list specs: List of specs to oragnize and format.
  :return: Appropriately sorted list of formatted specs.
  """
  specs = OrderedDict((spec, True) for spec in filter(None, map(normalize_spec, specs)))
  specs_by_category = split_specs_by_category(
    specs,
    categories_pattern=re.compile(r'(?P<local>^:)|(?P<thirdparty>^3rdparty)|(?P<other>)'),
  )
  # Use an OrderedDict instead of an OrderedSet to avoid a dependency on twitter commons.
  results = (specs_by_category['thirdparty'] + sorted(specs_by_category['local'])
             + sorted(specs_by_category['other']))
  return ["'{}'".format(spec) for spec in results]


def split_spec(spec):
  """Given a spec, returns a (directory_name, spec_name) tuple.

  The spec is allowed to be in the form 'directory:name', or just the implicit 'directory'.
  """
  try:
    path, name = spec.split(':', 1)
  except ValueError:
    path, name = spec, ''
  return path, name or os.path.basename(path)


def get_proto_path_spec_name(directory):
  """Given a directory, get the name of the wire_proto_path target if present.

  :param directory: The directory to check for wire_proto_path targets in.
  :return: A tuple in the form (string spec_name, bool target_is_present)
  """
  handwritten = os.path.join(directory, 'BUILD')
  if not os.path.exists(handwritten):
    return 'path', True
  with open(handwritten, 'r') as f:
    for line in f:
      if WIRE_PROTO_PATH_PATTERN.match(line):
        return 'path', True
  return 'aux-path', '/raw-protos/' in directory


def find_wire_proto_paths(dependencies):
  for dep in dependencies:
    dep = normalize_spec(dep)
    directory, name = split_spec(dep)
    if directory.endswith('/proto'):
      spec_name, spec_found = get_proto_path_spec_name(directory)
      if spec_found:
        yield '{directory}:{name}'.format(directory=directory, name=spec_name)


# Order matters here. This determines the order that targets and subdirectory BUILD files
# will be generated, for each project.
BuildComponent.TYPE_LIST = [
  MainClassComponent,
  MainResourcesComponent,
  TestResourcesComponent,
  MainProtobufLibraryComponent,
  MainExternalProtosComponent,
  TestProtobufLibraryComponent,
  TestExternalProtosComponent,
  MainJavaLibraryComponent,
  PlaceholderLibraryComponent,
  TestJavaLibraryComponent,
  PlaceholderTestComponent,
  JooqGenComponent,
]
