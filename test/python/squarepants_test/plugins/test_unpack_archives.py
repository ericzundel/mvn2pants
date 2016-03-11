# Tests for code in squarepants/src/main/python/squarepants/plugins/unpack_archives/tasks/unpack_archives.py
#
# Run with:
# ./pants test squarepants/src/test/python/squarepants_test/plugins:unpack_archives

import os

from pants.backend.jvm.targets.jar_dependency import JarDependency
from pants.backend.jvm.targets.jar_library import JarLibrary
from pants.util.dirutil import safe_mkdtemp
from pants_test.tasks.task_test_base import TaskTestBase

from squarepants.plugins.unpack_archives.targets.unpacked_archives import UnpackedArchives
from squarepants.plugins.unpack_archives.tasks.unpack_archives import UnpackArchives


class UnpackArchivesTest(TaskTestBase):

  @classmethod
  def task_type(cls):
    return UnpackArchives

  def test_unpack_archives(self):
    library = self.make_target('foo:library', JarLibrary, jars=[
      JarDependency(org='commons-io', name='commons-io', rev='2.4'),
    ])
    tempdir = safe_mkdtemp()
    self.assertFalse(len(os.listdir(tempdir)) > 0)

    unpacked = self.make_target('foo:unpacked', UnpackedArchives, dest=tempdir, libraries=[
      'foo:library',
    ])
    ivy_settings = os.path.abspath(os.path.join('build-support', 'ivy', 'ivysettings.xml'))
    self.set_options_for_scope('ivy', ivy_settings=ivy_settings)
    task = self.create_task(self.context(target_roots=[library, unpacked]))
    task.execute()
    self.assertTrue(len(os.listdir(tempdir)) > 0)
