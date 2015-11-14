# Tests for code in squarepants/src/main/python/squarepants/plugins/staging_build/tasks/staging_build.py
#
# Run with:
# ./pants test squarepants/src/test/python/squarepants_test/plugins:staging_build

from pants.backend.jvm.targets.jvm_binary import JvmBinary
from pants.base.exceptions import TaskError
from pants_test.tasks.task_test_base import TaskTestBase

from squarepants.plugins.staging_build.tasks.staging_build import StagingBuild


# This task is hard to test - it requires human input to provide security
# credentials.  Fortunately its not very much code.
class StagingBuildTest(TaskTestBase):

  @classmethod
  def task_type(cls):
    return StagingBuild

  def test_no_target(self):
    task = self.create_task(self.context())
    with self.assertRaisesRegexp(TaskError, r'No target specified.'):
      task.execute()

  def test_multiple_targets(self):
    target1 = self.make_target('foo:bin', JvmBinary)
    target2 = self.make_target('bar:bin', JvmBinary)

    task = self.create_task(self.context(target_roots=[target1, target2]))
    with self.assertRaisesRegexp(TaskError, r'Only one target'):
      task.execute()
