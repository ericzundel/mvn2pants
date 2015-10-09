# coding=utf-8
# Copyright 2015 Square, Inc.

from pants.goal.task_registrar import TaskRegistrar as task
from pants.build_graph.build_file_aliases import BuildFileAliases

from squarepants.plugins.compile_prep_command.targets.compile_prep_command import CompilePrepCommand
from squarepants.plugins.compile_prep_command.tasks.run_compile_prep_command import RunCompilePrepCommand

def build_file_aliases():
  return BuildFileAliases(
    targets={
      'compile_prep_command': CompilePrepCommand,
    }
  )

def register_goals():
   task(name='run_compile_prep_command', action=RunCompilePrepCommand).install('compile', first=True).with_description(
      "Run a command before compile")
