# coding=utf-8
# Copyright 2015 Square, Inc.

from pants.goal.task_registrar import TaskRegistrar as task
from pants.backend.jvm.targets.jvm_prep_command import JvmPrepCommand
from pants.backend.jvm.tasks.run_jvm_prep_command import RunJvmPrepCommandBase
from pants.build_graph.build_file_aliases import BuildFileAliases


class RunJooqJvmPrepCommand(RunJvmPrepCommandBase):
  goal = 'jooq'


def register_goals():
   JvmPrepCommand.add_goal('jooq')
   task(name='jooq-jvm-prep-command', action=RunJooqJvmPrepCommand).install('jooq', first=True)
