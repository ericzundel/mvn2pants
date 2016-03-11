# Tests for code in squarepants/src/main/python/squarepants/plugins/copy_resources/tasks/exclude_globally.py
#
# Run with:
# ./pants test squarepants/src/test/python/squarepants_test/plugins:sjar

from pants_test.tasks.task_test_base import TaskTestBase

from squarepants.plugins.sjar.exclude_globally import SJarTask, JarDependencyWithGlobalExcludes


class SJarTest(TaskTestBase):

  @classmethod
  def task_type(cls):
    return SJarTask

  def test_resources_jar_target(self):
    # HACK, you have to run this first to initialize the subsystem!
    self.set_options_for_scope('sjar', excludes=[
      {'org': 'org1', 'name': 'name1'},
      {'org': 'org2', 'name': 'name2'},
    ])

    self.create_task(self.context())
    jar = JarDependencyWithGlobalExcludes(org='foo', name='bar', rev='1.2.3')
    excludes = jar.excludes
    self.assertEquals(2, len(excludes))
    self.assertEquals(excludes[0].org, 'org1')
    self.assertEquals(excludes[0].name, 'name1')
    self.assertEquals(excludes[1].org, 'org2')
    self.assertEquals(excludes[1].name, 'name2')