# Tests for code in squarepants/src/main/python/squarepants/plugins/copy_resources/tasks/copy_resource_jars
#
# Run with:
# ./pants test squarepants/src/test/python/squarepants_test/plugins:copy_resources

from pants.backend.jvm.targets.jar_dependency import JarDependency
from pants.backend.jvm.targets.jar_library import JarLibrary
from pants_test.tasks.task_test_base import TaskTestBase

from squarepants.plugins.link_resources_jars.targets.resources_jar import ResourcesJar
from squarepants.plugins.link_resources_jars.tasks.link_resources_jars import LinkResourcesJars


class CopyResourcesTest(TaskTestBase):

  @classmethod
  def task_type(cls):
    return LinkResourcesJars

  def test_resources_jar_target(self):
    jar = JarDependency(org='foo', name='bar', rev='1.2.3')
    lib = self.make_target(spec='test/foo-library', target_type=JarLibrary, jars=[jar])
    resource_jar = self.make_target(spec='test/copy-resources', target_type=ResourcesJar,
      dependencies=[lib], dest='foo.jar')
    self.assertEquals('foo.jar', resource_jar.payload.dest)
