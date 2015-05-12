#!/usr/bin/python
#
# Given a pom.xml file, turn it into a BUILD file.
#
# This script generates BUILD.gen files and BUILD.aux files.
# BUILD.gen files are generated where no BUILD file exists, filling the same purpose as a
#   handwritten BUILD file would.
# BUILD.aux files are generated /beside/ handwritten BUILD files. All their target names have the
#   'aux-' prefix to avoid collision. The purpose of these is to provide an easy way to maintain
#   dependencies in handwritten BUILD files, simply by referencing the generated dependency list in
#   the adjacent BUILD.aux file. This alleviates the amount of manual work that has to be done to
#   keep handwritten up to date with changin pom.xml's. All target types in BUILD.aux's are forced
#   to be dependencies(), resources(), or jar_library(), to prevent overlapping sources.
#   BUILD.aux files are excluded from the command line when invoking ./pants, but are still pulled
#   in when normal BUILD files reference them in their dependencies.
#

import logging
import sys
import os.path

from pom_handlers import DepsFromPom
from pom_utils import PomUtils
from target_template import Target


_BUILD_FILE_NAME="BUILD.gen"
_AUX_BUILD_FILE_NAME="BUILD.aux"
_HAND_WRITTEN_BUILD_FILE_NAME="BUILD"
_TARGET_ANNOTATION_PROCESSOR = "annotation_processor"
_TARGET_JAVA_LIBRARY = "java_library"
_TARGET_PROTOBUF_LIBRARY = "java_protobuf_library"
_TARGET_WIRE_LIBRARY = "java_wire_library"
_TARGET_JUNIT_TESTS = "junit_tests"
_TARGET_RESOURCES = "resources"
# These directories won't be considered as targets for regular projects.
_EXCLUDE_PROJECT_TARGETS=[
  'parents/external-protos',
]

logger = logging.getLogger(__name__)

class PomToBuild():

  def __init__(self):
    pass

  def write_sources_BUILD(self, pom_dir, path, target_type, target_name, deps,
      group_id=None, artifact_id=None,
      jar_deps=[], resources=None, pom_properties=None):
    """Writes the BUILD file that contains the source file references.
    """
    glob_map = {
      _TARGET_JAVA_LIBRARY: '*.java',
      _TARGET_ANNOTATION_PROCESSOR: '*.java',
      _TARGET_JUNIT_TESTS: '*.java',
      _TARGET_PROTOBUF_LIBRARY: '*.proto',
      _TARGET_WIRE_LIBRARY: '*.proto',
      _TARGET_RESOURCES: '*',
    }
    pom_properties = pom_properties or {}
    if target_type not in glob_map:
      raise Exception("I can't handle target_type: {0}".format(target_type))
    glob = glob_map[target_type]

    # testing-support is a <scope>test</scope> dependency declared in parents/base/pom.xml.
    # To work right in pants, projects that directly used this would declare it in pom.xml, but
    # that would be a big change.  We also considered adding it to parent/base/BUILD but then
    # test-support classes would get into shaded jars so manually adding it to all test targets
    # is the next best thing.
    if target_type == _TARGET_JUNIT_TESTS:
      deps.append("'testing-support/src/main/java:lib'")

    build_file_path = os.path.join(pom_dir, path)
    if resources is None or target_type == _TARGET_RESOURCES:
      resources = []
    exclude_build = ", exclude=[globs('BUILD*')]" if target_type == _TARGET_RESOURCES else ''
    sources = "rglobs('{expression}'{exclude})".format(expression=glob, exclude=exclude_build)
    jar_contents = self.format_jar_deps(jar_deps, build_file_path)
    jar_target = ("    ':{jar_files}',\n"
                  .format(jar_files=infer_target_name(build_file_path, 'jar_files'))
                                    if jar_contents else '')

    # Special logic to handle external-protos directory.
    # This directory contains protobuf definitions that  live in another repo. The .proto
    # files get bundled up into a single all-protos artifact that we download and extract out
    # the protos we want using unpacked_jars()
    external_proto_contents = ''
    if pom_dir.startswith('external-protos/'):
      include_patterns = []
      versioned_jar_library = ''
      for pattern in pom_properties['external-protos.mask'].split(','):
        include_patterns.append("    '{0}'".format(pattern))
      if 'external-protos.version' in pom_properties:
        libraries = "[':versioned-all-protos']"
        versioned_jar_library = Target.get_template('jar_library').format(
          name="versioned-all-protos",
          jars="[jar(org='com.squareup.protos', name='all-protos', rev='{version}'),]"
          .format(version=pom_properties['external-protos.version'])
        )
      else:
        # TODO(zundel): Need to get properties from the parent poms, then we could fill
        # this in with the above section. for now, use the target from a hand-written build BUILD
        libraries = "['parents/external-protos:latest-all-protos']"
      external_proto_contents = Target.get_template('unpacked_jars').format(
        name='proto-source-set',
        libraries=libraries,
        include_patterns='[\n{0}\n  ]'.format(",\n".join(include_patterns)),
      ) + versioned_jar_library
      # Override sources with a reference to the source set
      sources = "from_target(':proto-source-set')"

    contents = ""
    if self._print_headers:
      contents = """# {filepath}
# Automatically generated by {gen_script}
""".format(filepath=infer_build_name(build_file_path), gen_script=os.path.basename(sys.argv[0]))

    if target_type == _TARGET_JUNIT_TESTS:
      # Tack on a java_library target
      contents += Target.get_template('junit_tests').format(
          name=infer_target_name(build_file_path, 'test'),
          sources=sources,
          dependencies=["':{lib}',".format(lib=infer_target_name(build_file_path, 'lib'))],
      )

      contents += Target.get_template('java_library').format(
        name=infer_target_name(build_file_path, 'lib'),
        sources=sources,
        resources=resources,
        dependencies=self.format_deps(_TARGET_JAVA_LIBRARY, deps, jar_target),
        groupId=group_id,
        artifactId=artifact_id,
      )
      contents += self.format_jar_deps(jar_deps, build_file_path)
    else:
      contents += Target.get_template(target_type).format(
        name=infer_target_name(build_file_path, target_name),
        sources=sources,
        resources=resources,
        dependencies=self.format_deps(target_type, deps, jar_target),
        libraries="['{0}']".format(jar_target) if jar_target else [],
        groupId=group_id,
        artifactId=artifact_id,
      )
      contents += self.format_jar_deps(jar_deps, build_file_path)
    contents += external_proto_contents
    write_build_file(build_file_path, contents)

  def format_jar_deps(self, jar_deps, build_file_path):
    """Given a list of jar dependencies, format a jar_library target.

    :param jar_deps: - <jar> dependency names to add to the jar_library.
    :param build_file_path: directory to the BUILD file to create.
    :returns: A jar_library declaration.
    :rtype: string
    """
    if not jar_deps:
      return ''

    return Target.jar_library.format(
      name=infer_target_name(build_file_path, 'jar_files'),
      jars=sorted(set(jar_deps)),
    )

  def format_deps(self, target_type, deps, jar_target):
    """deps - an array of <depencency> tags as a dictionary
       returns newline separated references suitable to be included in the BUILD file dependencies
       of a target.
    """
    if target_type == _TARGET_RESOURCES:
      return ''
    deps = sorted(set(deps or []))
    if jar_target:
      deps.append(jar_target)
    return deps


  def format_top_level_BUILD(self, pom_dir, path, target_name):
    """Formats a pants target for a specific target type """

    return Target.dependencies.format(
      name=infer_target_name(pom_dir, target_name),
      dependencies=["'{pom_dir}/{path}:{target_name}'"
      .format(pom_dir=pom_dir, path=path, target_name=target_name)],
    )

  def make_target_if_dir_exists(self, pom_dir, path, target_type, target_name, deps,
      group_id=None, artifact_id=None, jar_deps=None,
      resources=None, pom_properties=None):
    """Checks to see if a directory exists, and if so, formats a pants target for the code in it"""
    if pom_dir in _EXCLUDE_PROJECT_TARGETS:
      return ""
    # HACK HACK HACK: for external-protos, the src/main/protos dir does not exist.  We need to make it
    # just to hold our BUILD.gen file.
    subdir = os.path.join(pom_dir, path)
    is_external_protos = target_type == _TARGET_PROTOBUF_LIBRARY and 'external-protos.mask' in pom_properties
    if (is_external_protos
        and not path.startswith('src/test/')  # an empty src/test confuses maven proto plugin to generate code into 'generated-test-sources'
        and not os.path.exists(subdir)):
      os.makedirs(subdir)
    if os.path.isdir(subdir) and (is_external_protos or os.listdir(subdir)):
      self.write_sources_BUILD(pom_dir, path, target_type, target_name, deps, group_id,
                               artifact_id, jar_deps, resources, pom_properties)
      return self.format_top_level_BUILD(pom_dir, path, target_name)
    return ""

  def convert_pom(self, pom_file_name, rootdir=None, print_headers=True):
    """returns the contents of a BUILD file that corresponds to a module pom.xml file.
       pom_file_name - path to the pom.xml to convert
    """

    if not os.path.exists(pom_file_name) or not os.path.isfile(pom_file_name):
      raise IOError("Couldn't find plain pom.xml file at {0}".format(pom_file_name))

    self._print_headers = print_headers

    deps_from_pom = DepsFromPom(PomUtils.pom_provides_target(),
                                rootdir=rootdir,
                                exclude_project_targets=_EXCLUDE_PROJECT_TARGETS)
    aggregate_lib_deps, aggregate_test_deps = deps_from_pom.get(pom_file_name)
    group_id = deps_from_pom.group_id
    artifact_id = deps_from_pom.artifact_id
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

    pom_dir = os.path.dirname(pom_file_name)
    target_name = os.path.split(pom_dir)[1]
    if pom_dir.startswith("./"):
      pom_dir = pom_dir[2:]

    contents = ""
    if self._print_headers:
      contents = """# {filepath}
# Automatically generated by {gen_script}
""".format(filepath=infer_build_name(pom_dir), gen_script=os.path.basename(sys.argv[0]))

    # tack on a jvm_binary target if a main class is specified in the pom
    # <properties>
    #   <project.mainclass>com.squareup.service.container.exemplar.ExemplarApp</project.mainclass>
    # </properties>
    main_class = deps_from_pom.get_property('project.mainclass')
    if main_class:
      main_path = main_class.replace('.','/')
      contents += Target.get_template('jvm_binary').format(
        name=infer_target_name(pom_dir, target_name),
        main=main_class,
        basename=deps_from_pom.artifact_id,
        main_source=main_path,
        dependencies=["':{name}'".format(name=infer_target_name(pom_dir, 'lib'))],
        group_id=group_id, artifact_id=artifact_id,
      )

    # tack on the targets
    resources = ""
    test_resources = ""
    res_path = 'src/main/resources'
    res_contents = self.make_target_if_dir_exists(pom_dir, res_path, _TARGET_RESOURCES, "resources", deps=lib_deps,
                               group_id=group_id, artifact_id=artifact_id,
                               pom_properties=deps_from_pom.properties)
    if res_contents:
      resources = "'{pom_dir}/{path}:resources'".format(pom_dir=pom_dir, path=res_path)

    test_res_path = "src/test/resources"
    test_res_contents = self.make_target_if_dir_exists(pom_dir, test_res_path, _TARGET_RESOURCES, "resources", deps=[],
                               group_id=group_id, artifact_id=artifact_id,
                               pom_properties=deps_from_pom.properties)
    if test_res_contents:
      test_resources = "'{pom_dir}/{path}:resources'".format(pom_dir=pom_dir, path=test_res_path)

    proto_path = 'src/main/proto'
    proto_contents = self.make_target_if_dir_exists(
        pom_dir, proto_path, _TARGET_PROTOBUF_LIBRARY, "proto", deps=lib_deps,
        group_id=group_id, artifact_id=artifact_id,
        jar_deps=lib_jar_deps,
        pom_properties=deps_from_pom.properties)
    if proto_contents:
      lib_deps.append("'{pom_dir}/{path}:proto'".format(pom_dir=pom_dir, path=proto_path))

    wire_proto_path =  'src/main/wire_proto'
    wire_contents = self.make_target_if_dir_exists(
      pom_dir, wire_proto_path, _TARGET_WIRE_LIBRARY, "wire_proto", deps=lib_deps,
      group_id=group_id, artifact_id=artifact_id,
      jar_deps=lib_jar_deps,
      pom_properties=deps_from_pom.properties)
    if wire_contents:
      lib_deps.append("'{pom_dir}/{path}:wire_proto'".format(pom_dir=pom_dir, path=wire_proto_path))

    test_proto_path = 'src/test/proto'
    test_proto_contents = self.make_target_if_dir_exists(
      pom_dir, test_proto_path, _TARGET_PROTOBUF_LIBRARY, "proto", deps=lib_deps + test_deps,
      group_id=group_id, artifact_id=artifact_id,
      pom_properties=deps_from_pom.properties)

    if test_proto_contents:
      test_deps.append("'{pom_dir}/{path}:proto'".format(pom_dir=pom_dir, path=test_proto_path))

    test_wire_proto_path = 'src/test/wire_proto'
    test_wire_contents = self.make_target_if_dir_exists(
      pom_dir, test_wire_proto_path, _TARGET_WIRE_LIBRARY, "wire_proto", deps=lib_deps + test_deps,
      group_id=group_id, artifact_id=artifact_id,
      pom_properties=deps_from_pom.properties)
    if test_wire_contents:
      test_deps.append("'{pom_dir}/{path}:wire_proto'".format(pom_dir=pom_dir,
                                                              path=test_wire_proto_path))
    java_path = 'src/main/java'
    java_contents = self.make_target_if_dir_exists(pom_dir, java_path, _TARGET_JAVA_LIBRARY,
                                               "lib", deps=lib_deps,
                                               group_id=group_id, artifact_id=artifact_id,
                                               jar_deps=lib_jar_deps, resources=resources,
                                               pom_properties=deps_from_pom.properties)

    if java_contents:
      test_deps.append("'{pom_dir}/{path}:lib'".format(pom_dir=pom_dir, path=java_path))
    else:
      java_contents += "target(name='{name}')".format(name=infer_target_name(pom_dir, 'lib'))

    test_contents = self.make_target_if_dir_exists(pom_dir, "src/test/java", _TARGET_JUNIT_TESTS,
                                               "test", lib_deps + test_deps,
                                               jar_deps=lib_jar_deps + test_jar_deps,
                                               group_id=group_id, artifact_id=artifact_id,
                                               resources=test_resources,
                                               pom_properties=deps_from_pom.properties)

    contents += proto_contents + wire_contents + java_contents + test_contents
    write_build_file(pom_dir, contents)

def is_aux(directory):
  return os.path.exists(os.path.join(directory, _HAND_WRITTEN_BUILD_FILE_NAME))

def infer_target_name(directory, name):
  if name.startswith('aux-'):
    return name # Already aux'd, don't want to do again.
  if is_aux(directory):
    return 'aux-{name}'.format(name=name)
  return name

def infer_build_name(directory):
  if is_aux(directory):
    return os.path.join(directory, _AUX_BUILD_FILE_NAME)
  return os.path.join(directory, _BUILD_FILE_NAME)

def write_build_file(path, contents):
  """Conditionally Write the BUILD file out to the filesystem"""
  outfile_name = infer_build_name(path)
  outfile = open(outfile_name, 'w')
  outfile.write(contents)
  outfile.close()

def main(poms):
  for pom_file_name in poms:
    PomToBuild().convert_pom(pom_file_name)

if __name__ == "__main__":
  args = PomUtils.parse_common_args(sys.argv[1:])
  poms = []
  if (len(args) > 0):
    main(args)
  else:
    print "usage: {0} path/to/pom.xml".format(os.path.basename(sys.argv[0]))
    PomUtils.common_usage()
    sys.exit(1)
