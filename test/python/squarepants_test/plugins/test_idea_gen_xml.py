# Tests for code in squarepants/src/main/python/squarepants/plugins/square_idea/tasks/square_idea.py
#
# Run with:
# ./pants test squarepants/src/test/python/squarepants_test/plugins:idea_gen_xml

import os
import pkgutil
from xml.etree import ElementTree

from pants.backend.jvm.subsystems.jvm import JVM
from pants.backend.jvm.targets.java_library import JavaLibrary
from pants.base.build_environment import get_buildroot
from pants.base.generator import Generator, TemplateData
from pants.build_graph.build_file_aliases import BuildFileAliases
from pants_test.tasks.task_test_base import TaskTestBase

from squarepants.file_utils import temporary_dir, touch
from squarepants.plugins.square_idea.tasks.square_idea import SquareIdea


class IdeaGenXml(TaskTestBase):

  @classmethod
  def task_type(cls):
    return SquareIdea

  @property
  def alias_groups(self):
    return BuildFileAliases(
        targets={
          'java_library': JavaLibrary,
        },
    )

  def setUp(self):
    super(IdeaGenXml, self).setUp()
    self._oldwd = os.getcwd()
    os.chdir(get_buildroot())

  def tearDown(self):
    if self._oldwd:
      os.chdir(self._oldwd)
    super(IdeaGenXml, self).setUp()

  def _load(self, name):
    return pkgutil.get_data(__package__, os.path.join('test_data', name))

  def _check_tree_contains(self, one, two):
    if one.tag != two.tag:
      return False
    for key, value in two.attrib.items():
      if one.attrib.get(key, '') != two.attrib.get(key, ''):
        return False
    for child_two in two:
      found_match = False
      for child_one in one:
        if self._check_tree_contains(child_one, child_two):
          found_match = True
          break
      if not found_match:
        return False
    return True

  def _assert_tree_contains(self, xml_tree_file, xml_subtree_file, **format_kwargs):
    one = ElementTree.parse(xml_tree_file)
    root_one = one.getroot()
    data = self._load(xml_subtree_file)
    if format_kwargs:
      data = data.format(**format_kwargs)
      print(data)
    root_two = ElementTree.fromstring(data)
    self.assertTrue(self._check_tree_contains(root_one, root_two),
                    'The second tree is not a subset of the first tree.\n{one}\n\n{div}\n\n{two}\n'
                    .format(one=ElementTree.tostring(root_one),
                            two=ElementTree.tostring(root_two),
                            div='='*20))

  def test_meta_equal(self):
    self.assertTrue(self._check_tree_contains(
      ElementTree.fromstring('<a><b/></a>'),
      ElementTree.fromstring('<a><b></b></a>'),
    ))

  def test_meta_unequal(self):
    self.assertFalse(self._check_tree_contains(
      ElementTree.fromstring('<a><b/></a>'),
      ElementTree.fromstring('<b><a></a></b>'),
    ))
    self.assertFalse(self._check_tree_contains(
      ElementTree.fromstring('<a><b/></a>'),
      ElementTree.fromstring('<b><b/></b>'),
    ))

  def test_meta_subset(self):
    self.assertTrue(self._check_tree_contains(
      ElementTree.fromstring('<a><b/></a>'),
      ElementTree.fromstring('<a></a>'),
    ))
    self.assertTrue(self._check_tree_contains(
      ElementTree.fromstring('<a><b><c/></b></a>'),
      ElementTree.fromstring('<a><b/></a>'),
    ))
    self.assertFalse(self._check_tree_contains(
      ElementTree.fromstring('<a><b><c/></b></a>'),
      ElementTree.fromstring('<a><b><c/><d/></b></a>'),
    ))
    self.assertTrue(self._check_tree_contains(
      ElementTree.fromstring('<a><b><c/></b><b><d/><c/></b></a>'),
      ElementTree.fromstring('<a><b><c/><d/></b></a>'),
    ))

  def test_default_junit(self):
    with temporary_dir() as outdir:
      self.set_options(project_dir=outdir, merge=False)
      task = self.create_task(self.context())
      ipr = task._generate_project_file(TemplateData(
        root_dir=get_buildroot(),
        outdir=task.intellij_output_dir,
        resource_extensions=[],
        scala=None,
        checkstyle_classpath=';'.join([]),
        debug_port=None,
        extra_components=[],
        global_junit_vm_parameters='-one -two -three',
      ))
      self._assert_tree_contains(ipr, 'project_default_junit.xml')

  def test_loose_files(self):
    with temporary_dir() as outdir:
      project_name = 'foobar'
      self.set_options(project_dir=outdir, project_name=project_name, loose_files=True, merge=False,
                       libraries=False, open=False)
      with open(os.path.join(get_buildroot(), 'pom.xml'), 'w+') as f:
        f.write('<?xml version="1.0" encoding="UTF-8"?>'
                '<project><modules/></project>')

      task = self.create_task(self.context())
      task.execute()

      ipr = os.path.join(outdir, project_name, 'foobar.ipr')
      iml = os.path.join(outdir, project_name, 'java.iml')
      self._assert_tree_contains(ipr, 'project_loose_files.ipr.xml',
                                 repo=os.path.basename(get_buildroot()))
      self._assert_tree_contains(iml, 'project_loose_files.iml.xml',
                                 abs_path_to_build_root=os.path.abspath(get_buildroot()))

  def test_provided_dependency_scope(self):
    with temporary_dir() as outdir:
      project_name = 'dep-scope'
      self.set_options(project_dir=outdir, project_name=project_name, loose_files=True, merge=False,
                       libraries=False, open=False, provided_module_dependencies={'module1' : 'module2'})
      with open(os.path.join(get_buildroot(), 'pom.xml'), 'w+') as f:
        f.write('<?xml version="1.0" encoding="UTF-8"?>\n'
                '<project>\n'
                '  <modules>\n'
                '    <module>module1</module>\n'
                '    <module>module2</module>\n'
                '    <module>module3</module>\n'
                '  </modules>\n'
                '</project>\n')
        module3 = self.make_target('module3:module3', dependencies=[],
                                   target_type=JavaLibrary, sources=['Module3.java'])
        module2 = self.make_target('module2:module2', dependencies=[],
                                   target_type=JavaLibrary, sources=['Module3.java'])
        module1 = self.make_target('module1:module1', dependencies=[module2, module3],
                                   target_type=JavaLibrary, sources=['Module1.java'])

      task = self.create_task(self.context(target_roots=[module1]))
      task.execute()
      iml = os.path.join(outdir, project_name, 'module1.iml')
      self._assert_tree_contains(iml, 'project_dep_scope.iml.xml')

  def test_provided_dependency_scope_prefix(self):
    with temporary_dir() as outdir:
      project_name = 'dep-scope'
      self.set_options(project_dir=outdir, project_name=project_name, loose_files=True, merge=False,
                       libraries=False, open=False, provided_module_dependencies={'module1' : 'module2'})
      with open(os.path.join(get_buildroot(), 'pom.xml'), 'w+') as f:
        f.write('<?xml version="1.0" encoding="UTF-8"?>\n'
                '<project>\n'
                '  <modules>\n'
                '    <module>module1-aa</module>\n'
                '    <module>module2-bb</module>\n'
                '    <module>module3-cc</module>\n'
                '  </modules>\n'
                '</project>\n')
        module3 = self.make_target('module3-cc:module3-cc', dependencies=[],
                                   target_type=JavaLibrary, sources=['Module3.java'])
        module2 = self.make_target('module2-bb:module2-bb', dependencies=[],
                                   target_type=JavaLibrary, sources=['Module3.java'])
        module1 = self.make_target('module1-aa:module1-aa', dependencies=[module2, module3],
                                   target_type=JavaLibrary, sources=['Module1.java'])

      task = self.create_task(self.context(target_roots=[module1]))
      task.execute()
      iml = os.path.join(outdir, project_name, 'module1-aa.iml')
      self._assert_tree_contains(iml, 'project_dep_scope_prefix.iml.xml')

  def test_find_target_directories(self):
    with temporary_dir() as outdir:
      project_name = 'foobar'
      self.set_options(project_dir=outdir, project_name=project_name, loose_files=True, merge=False,
                       libraries=False, open=False)
      with open(os.path.join(get_buildroot(), 'pom.xml'), 'w+') as f:
        f.write('<?xml version="1.0" encoding="UTF-8"?>'
                '<project><modules/></project>')
      task = self.create_task(self.context())
      project = task._create_idea_project(outdir, None)
      with temporary_dir() as repo:
        poms = {os.path.join(repo, pom) for pom in (
          'pom.xml',
          'foobar/pom.xml',
          'foobar/child1/pom.xml',
          'foobar/child1/sub/sub/pom.xml',
          'foobar/child1/sub/marine/foo.txt',
          'foobar/child1/sub/mersible/pom.xml',
          'foobar/child2/foo.txt',
          'foobar/child3/pom.xml',
          'orange/pom.xml',
          'yellow/foo.txt',
        )}
        for pom in poms:
          touch(pom, makedirs=True)

        excludes = project._maven_excludes(os.path.join(repo, 'foobar/child1'))
        expected = {os.path.join(repo, target) for target in (
          'target',
          'foobar/target',
          'foobar/child1/target',
          'foobar/child1/sub/sub/target',
          'foobar/child1/sub/mersible/target',
        )}

        self.assertEqual(expected, set(excludes))

        excludes = project._maven_excludes(os.path.join(repo, 'foobar'))
        expected = {os.path.join(repo, target) for target in (
          'target',
          'foobar/target',
          'foobar/child1/target',
          'foobar/child1/sub/sub/target',
          'foobar/child1/sub/mersible/target',
          'foobar/child3/target'
        )}

        self.assertEqual(expected, set(excludes))

        excludes = project._maven_excludes(os.path.join(repo))
        expected = {os.path.join(repo, target) for target in (
          'target',
          'foobar/target',
          'foobar/child1/target',
          'foobar/child1/sub/sub/target',
          'foobar/child1/sub/mersible/target',
          'foobar/child3/target',
          'orange/target',
        )}

        self.assertEqual(expected, set(excludes))

  def test_debug_port_set(self):
    with temporary_dir() as outdir:
      project_name = 'debug-port-project'
      self.set_options(project_dir=outdir, project_name=project_name, merge=False,
                       libraries=False, open=False)
      self.set_options_for_scope(JVM.options_scope, debug_port=54321)
      with open(os.path.join(get_buildroot(), 'pom.xml'), 'w+') as f:
        f.write('<?xml version="1.0" encoding="UTF-8"?>'
                '<project><modules/></project>')
      task = self.create_task(self.context())
      task.execute()

      ipr = os.path.join(outdir, project_name, 'debug-port-project.ipr')
      self._assert_tree_contains(ipr, 'project_debug_port.ipr.xml',
                                 repo=os.path.basename(get_buildroot()))
