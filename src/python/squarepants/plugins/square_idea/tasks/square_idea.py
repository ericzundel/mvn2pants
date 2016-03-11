# coding=utf-8

from __future__ import (absolute_import, division, generators, nested_scopes, print_function,
                        unicode_literals, with_statement)

import os
import pkgutil
import re
import shutil
import subprocess
import tempfile
from hashlib import sha1
from xml.dom import minidom

from pants.backend.jvm.subsystems.jvm import JVM
from pants.backend.project_info.tasks.export import ExportTask
from pants.base.generator import Generator, TemplateData
from pants.binaries import binary_util
from pants.option.custom_types import dict_option
from pants.util.dirutil import safe_mkdir, safe_walk
from pants.util.memo import memoized_method, memoized_property
from squarepants.plugins.square_idea.tasks.square_idea_project import IdeaProject

_TEMPLATE_BASEDIR = 'templates/idea'


_VERSIONS = {
  '9': '12',  # 9 and 12 are ipr/iml compatible
  '10': '12',  # 10 and 12 are ipr/iml compatible
  '11': '12',  # 11 and 12 are ipr/iml compatible
  '12': '12'
}


_SCALA_VERSION_DEFAULT = '2.9'
_SCALA_VERSIONS = {
  '2.8': 'Scala 2.8',
  _SCALA_VERSION_DEFAULT: 'Scala 2.10',
  '2.10': 'Scala 2.10',
  '2.10-virt': 'Scala 2.10 virtualized'
}


class SquareIdea(ExportTask):

  @classmethod
  def register_options(cls, register):
    super(SquareIdea, cls).register_options(register)
    register('--version', choices=sorted(list(_VERSIONS.keys())), default='11',
             help='The IntelliJ IDEA version the project config should be generated for.')
    register('--merge', action='store_true', default=False,
             help='Merge any manual customizations in existing '
                  'Intellij IDEA configuration. If False, manual customizations '
                  'will be over-written.')
    register('--open', action='store_true', default=True,
             help='Attempts to open the generated project in IDEA.')
    register('--open-with',
             help='Use the specified executable to open the generated project.')
    register('--bash', action='store_true',
             help='Adds a bash facet to the generated project configuration.')
    register('--scala-language-level',
             choices=_SCALA_VERSIONS.keys(), default=_SCALA_VERSION_DEFAULT,
             help='Set the scala language level used for IDEA linting.')
    register('--scala-maximum-heap-size-mb', type=int, default=512,
             help='Sets the maximum heap size (in megabytes) for scalac.')
    register('--fsc', action='store_true', default=False,
             help='If the project contains any scala targets this specifies the '
                  'fsc compiler should be enabled.')
    register('--java-encoding', default='UTF-8',
             help='Sets the file encoding for java files in this project.')
    register('--java-maximum-heap-size-mb', type=int, default=512,
             help='Sets the maximum heap size (in megabytes) for javac.')
    register('--exclude-maven-target', action='store_true', default=False,
             help="Exclude 'target' directories for directories containing "
                  "pom.xml files.  These directories contain generated code and"
                  "copies of files staged for deployment.")
    register('--maven-style', action='store_true', default=True,
             help="Optimize for a maven-style repo layout.")
    register('--exclude-folders', action='append',
             default=[
               '.pants.d/bootstrap',
               '.pants.d/build_invalidator',
               '.pants.d/compile',
               '.pants.d/ivy',
               '.pants.d/python',
               '.pants.d/python-setup',
               '.pants.d/resources',
               '.pants.d/reports',
               '.pants.d/run-tracker',
               '.pants.d/test'
             ],
             help='Adds folders to be excluded from the project configuration.')
    register('--exclude-patterns', action='append', default=[],
             help='Adds patterns for paths to be excluded from the project configuration.')
    register('--annotation-processing-enabled', action='store_true',
             help='Tell IntelliJ IDEA to run annotation processors.')
    register('--annotation-generated-sources-dir', default='generated', advanced=True,
             help='Directory relative to --project-dir to write annotation processor sources.')
    register('--annotation-generated-test-sources-dir', default='generated_tests', advanced=True,
             help='Directory relative to --project-dir to write annotation processor sources.')
    register('--annotation-processor', action='append', advanced=True,
             help='Add a Class name of a specific annotation processor to run for all projects.')
    register('--internal-codegen-processor', action='append', advanced=True,
             help='Adds the class name of an internally-defined annotation processor which '
                  'generates code.')
    register('--project-name',
             help='Specifies the name to use for the generated project.')
    register('--project-dir',
             help='Specifies the directory to output the generated project files to.')
    register('--project-auto-dir', default=False, action='store_true',
             help='Generate each project in a unique directory using the sha1 of the module names.')
    register('--loose-files', default=False, action='store_true',
             help='Generates a module for the root repo directory, allowing you to search and '
                  'open loose files that not associated with any of the modules you are opening '
                  '(such as the root-level pom.xml). This has the side-effect of cluttering the '
                  'project view quite a bit, which is why it is disabled by default.')
    register('--prune-libraries', default=False, action='store_true',
             help='Omits dependencies on jar artifacts that are already transitively dependend on. '
                  'This makes the external libraries for each module briefer and easier to read '
                  'through, but it may result in undesirable behavior because the order jars '
                  'appear on the classpath may change.')
    register('--module-pool', default=True, action='store_true',
             help='Reduce incidence of having to restart IntelliJ due to getting new modules by '
                  'using a "module pool", which sacrifices readability of the names of modules in '
                  '.pants.d.')
    register('--module-pool-size', type=int, default=1000,
             help='Controls the number of generated placeholder modules.')
    register('--module-pool-steal-names', default=True, action='store_true',
             help='Borrow the module name from other modules previously generated in .pants.d if '
                  'we would otherwise have to create a new module for something in .pants.d. This '
                  'may create modules with names that are extremely misleading in .pants.d, though '
                  'it has the benefit of reducing the incidence of requiring the user to restart '
                  'IntelliJ.')
    register('--provided-module_dependencies', type=dict_option,
             help='Mapping of { module_name_prefix p: module_name_prefix } where the scope of '
                  'the dependency in Module Settings should be marked as "Provided".  The names '
                  'should match the names of the .iml files.')

  @classmethod
  def task_subsystems(cls):
    return super(SquareIdea, cls).task_subsystems() + (JVM,)

  def __init__(self, *args, **kwargs):
    super(SquareIdea, self).__init__(*args, **kwargs)

    self.maven_style = self.get_options().maven_style
    self.intellij_output_dir = os.path.join(self.gen_project_workdir, 'out')
    self.nomerge = not self.get_options().merge
    self.open = self.get_options().open
    self.open_with = self.get_options().open_with
    self.bash = self.get_options().bash

    self.scala_language_level = _SCALA_VERSIONS.get(
      self.get_options().scala_language_level, None)
    self.scala_maximum_heap_size = self.get_options().scala_maximum_heap_size_mb

    self.fsc = self.get_options().fsc

    self.java_encoding = self.get_options().java_encoding
    self.java_maximum_heap_size = self.get_options().java_maximum_heap_size_mb

    idea_version = _VERSIONS[self.get_options().version]
    self.project_template = os.path.join(_TEMPLATE_BASEDIR,
                                         'project-{}.mustache'.format(idea_version))
    self.module_template = os.path.join(_TEMPLATE_BASEDIR,
                                        'module-{}.mustache'.format(idea_version))
    self.empty_module_file = os.path.join(_TEMPLATE_BASEDIR, 'empty-module.txt')

    self.project_filename = os.path.join(self.gen_project_workdir,
                                         '{}.ipr'.format(self.project_name))
    self.module_filename = os.path.join(self.gen_project_workdir,
                                        '{}.iml'.format(self.project_name))
    self.jvm = JVM.scoped_instance(self)

  @memoized_property
  def project_dir(self):
    return os.path.expanduser(self.get_options().project_dir)

  @memoized_property
  def gen_project_workdir(self):
    project_dir = self.project_dir
    if self.get_options().project_auto_dir and not self.get_options().project_name:
      hash, name = self.gen_project_name
      project_dir = os.path.join(project_dir, '_auto', hash)
    return os.path.abspath(os.path.join(project_dir, self.project_name))

  @memoized_property
  def gen_project_name(self):
    """Computes the name for the generated project, and a sha1 digest of its loaded module names.

    The project name is computed to be a comma-separated list of the top-5 alphabetically sorted
    modules which have no dependees which are also being loaded. That is, the project name is
    derived from the modules which are identified as leaf modules in the context of the modules
    being loaded.

    :return: A tuple of (modules_sha, project_name)
    """

    def get_module(target):
      return target.address.spec_path

    def is_independent(target):
      return not self.context.build_graph.dependents_of(target.address)

    all_loaded_modules = sorted({get_module(target) for target in self.context.targets()})
    hasher = sha1()
    for m in all_loaded_modules:
      hasher.update(m)
    module_sha = hasher.hexdigest()[:8]

    independents = self.context.targets(is_independent)
    modules = {IdeaProject.find_closest_maven_module(t.address.spec_path) for t in independents}
    modules = sorted(filter(None, modules))

    project_name = modules[0].replace('/', '-')
    if not (ord('a') <= ord(project_name[0].lower()) <= ord('z')):
      project_name = 'project-with-{count}-modules'.format(count=len(modules))
    elif len(modules) > 1:
      project_name = '{name}-plus-{count}'.format(name=project_name, count=len(modules)-1)

    return module_sha, project_name

  @property
  def project_name(self):
    name = self.get_options().project_name
    if name:
      return name
    if self.get_options().project_auto_dir:
      _, gen_name = self.gen_project_name
      return gen_name
    return 'new-idea-project'

  @memoized_property
  def _empty_module_data(self):
    return pkgutil.get_data(__name__, self.empty_module_file)

  def _existing_module_files(self):
    for existing_project_file in os.listdir(os.path.dirname(self.project_filename)):
      if existing_project_file.endswith('.iml'):
        yield existing_project_file

  def _create_module_pool(self, existing_modules):
    if not self.get_options().module_pool:
      return None
    module_type_pattern = re.compile(r'^(?P<generic_modules>gen-\d+$)|(?P<specific_modules>\.pants\.d-)')
    module_types = dict(generic_modules=[], specific_modules=[])
    for filename in existing_modules:
      name, _ = os.path.splitext(filename)
      m = module_type_pattern.match(name)
      if m:
        module_types[m.lastgroup].append(name)
    return IdeaProject.ModulePool(steal_names=self.get_options().module_pool_steal_names,
                                  **module_types)

  def _create_idea_project(self, outdir, module_pool):
    targets = self.context.targets()
    blob = self.generate_targets_map(targets)
    aop_sources_dir = os.path.join(self.get_options().annotation_generated_sources_dir)
    aop_tests_dir = os.path.join(self.get_options().annotation_generated_test_sources_dir)

    annotation_processing = IdeaProject.AnnotationProcessing(
      enabled=self.get_options().annotation_processing_enabled,
      sources_dir=aop_sources_dir,
      test_sources_dir=aop_tests_dir,
      processors=self.get_options().annotation_processor,
      codegen_processors=self.get_options().internal_codegen_processor,
    )

    return IdeaProject(
      blob,
      output_directory=outdir,
      workdir=self.gen_project_workdir,
      context=self.context,
      maven_style=self.get_options().maven_style,
      exclude_folders=self.get_options().exclude_folders,
      annotation_processing=annotation_processing,
      bash=self.bash,
      java_encoding=self.java_encoding,
      java_maximum_heap_size=self.java_maximum_heap_size,
      pants_workdir=self.get_options().pants_workdir,
      generate_root_module=self.get_options().loose_files,
      prune_libraries=self.get_options().prune_libraries,
      module_pool=module_pool,
      debug_port=self.jvm.get_options().debug_port,
      provided_module_dependencies=self.get_options().provided_module_dependencies,
    )

  def _generate_project_file(self, configured_project):
    existing_project_components = None
    if not self.nomerge:
      # Grab the existing components, which may include customized ones.
      existing_project_components = self._parse_xml_component_elements(self.project_filename)

    # Generate (without merging in any extra components).
    safe_mkdir(os.path.abspath(self.intellij_output_dir))

    ipr = self._generate_to_tempfile(Generator(pkgutil.get_data(__name__, self.project_template),
                                               project=configured_project))

    if not self.nomerge:
      # Get the names of the components we generated, and then delete the
      # generated files.  Clunky, but performance is not an issue, and this
      # is an easy way to get those component names from the templates.
      extra_project_components = self._get_components_to_merge(existing_project_components, ipr)
      os.remove(ipr)

      # Generate again, with the extra components.
      ipr = self._generate_to_tempfile(
        Generator(pkgutil.get_data(__name__, self.project_template),
                  project=configured_project.extend(extra_components=extra_project_components))
      )
    self.context.log.info('Generated IntelliJ project in {directory}'
                          .format(directory=self.gen_project_workdir))
    return ipr

  def _generate_module_files(self, configured_modules):
    return [(name, self._generate_to_tempfile(Generator(pkgutil.get_data(__name__, self.module_template), module=module)))
            for name, module in configured_modules.items()]

  def _copy_project_files(self, ipr, imls, existing_modules, module_pool):
    project_directory = os.path.dirname(self.project_filename)
    try:
      os.remove(self.project_filename)
      previous_project_existed = True
    except OSError:
      previous_project_existed = False

    previous_modules = existing_modules
    for existing_project_file in previous_modules:
      os.remove(os.path.join(project_directory, existing_project_file))

    current_modules = set()
    for index, (name, iml) in enumerate(imls):
      dirname, filename = os.path.split(self.module_filename)
      shutil.move(iml, os.path.join(dirname, name))
      current_modules.add(name)

    shutil.move(ipr, self.project_filename)

    added_modules = current_modules - previous_modules
    removed_modules = previous_modules - current_modules

    placeholder_module_pool_modules = map(IdeaProject.ModulePool.generic_name,
                                          range(self.get_options().module_pool_size))

    # Add fake modules for the module pool, in case it's turned on in the future.
    removed_modules.update('{}.iml'.format(i) for i in placeholder_module_pool_modules
                           if i not in module_pool.assigned_modules())

    for name in removed_modules:
      # Make placeholder modules for any removed modules. Placeholders will be generated
      # automatically for projects listed in pom.xml, but not generated modules in .pants.d. This
      # should help alleviate errors that occur if people switch between projects that use different
      # generated sources (since those are the modules that get stuck under .pants.d, and are hard
      # to pre-compute).
      path = os.path.join(os.path.dirname(self.module_filename), name)
      if not os.path.exists(path):
        with open(path, 'w+') as f:
          f.write(self._empty_module_data)

    if added_modules and previous_project_existed:
      added_names = sorted(m.rsplit('.', 1)[0] for m in added_modules)
      self.context.log.warn(
        '\nThe set of modules in the java repo has changed:\n{added}\n\n'
        'This typically happens if new modules are added to the root-level pom.xml.\n\n'
        'You probably will need to restart IntelliJ (or run this command a second time) to '
        'properly load any added modules.\n'.format(
          added=''.join('\nA    {}'.format(m) for m in added_names),
        )
      )

  def _open_project(self):
    if self.open:
      if self.open_with:
        null = open(os.devnull, 'w')
        subprocess.Popen([self.open_with, self.project_filename], stdout=null, stderr=null)
      else:
        binary_util.ui_open(self.project_filename)

  def execute(self):
    outdir = os.path.abspath(self.intellij_output_dir)
    if not os.path.exists(outdir):
      os.makedirs(outdir)

    existing_modules = set(self._existing_module_files())
    module_pool = self._create_module_pool(existing_modules)
    project = self._create_idea_project(outdir=outdir, module_pool=module_pool)
    unbuilt_aop_jars = sorted(jar for jar in project.annotation_processing_jars
                              if not os.path.exists(jar))
    if unbuilt_aop_jars:
      self.context.log.warn(
        '\nYour project may use code generated by annotation processors that live inside the repo.'
        '\n\nThis is fine, but be aware that any code generated by these annotation processors will'
        '\nshow up as red in IntelliJ before you Make a module that uses it (which causes these '
        'jars to be built).\n{}\n'.format(
          ''.join('\n  {}'.format(os.path.basename(jar)) for jar in unbuilt_aop_jars)
        )
      )
    ipr = self._generate_project_file(configured_project=project.project_template)
    imls = self._generate_module_files(configured_modules=project.module_templates_by_filename)
    self._copy_project_files(ipr, imls, existing_modules, module_pool)
    self._open_project()

  def _generate_to_tempfile(self, generator):
    """Applies the specified generator to a temp file and returns the path to that file.
    We generate into a temp file so that we don't lose any manual customizations on error."""
    (output_fd, output_path) = tempfile.mkstemp()
    with os.fdopen(output_fd, 'w') as output:
      generator.write(output)
    return output_path

  def _parse_xml_component_elements(self, path):
    """Returns a list of pairs (component_name, xml_fragment) where xml_fragment is the xml text of
    that <component> in the specified xml file."""
    if not os.path.exists(path):
      return []  # No existing components.
    dom = minidom.parse(path)
    # .ipr and .iml files both consist of <component> elements directly under a root element.
    return [(x.getAttribute('name'), x.toxml()) for x in dom.getElementsByTagName('component')]

  def _get_components_to_merge(self, mergable_components, path):
    """Returns a list of the <component> fragments in mergable_components that are not
    superceded by a <component> in the specified xml file.
    mergable_components is a list of (name, xml_fragment) pairs."""

    # As a convenience, we use _parse_xml_component_elements to get the
    # superceding component names, ignoring the generated xml fragments.
    # This is fine, since performance is not an issue.
    generated_component_names = set(
      [name for (name, _) in self._parse_xml_component_elements(path)])
    return [x[1] for x in mergable_components if x[0] not in generated_component_names]
