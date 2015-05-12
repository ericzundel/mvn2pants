# coding=utf-8
# Copyright 2015 Pants project contributors (see CONTRIBUTORS.md).
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from pants.goal.task_registrar import TaskRegistrar as task
from pants.base.build_file_aliases import BuildFileAliases

from squarepants.plugins.ruby.targets.ruby_specs import RubySpecs
from squarepants.plugins.ruby.tasks.ruby_specs_run import RubySpecsRun

def build_file_aliases():
  return BuildFileAliases.create(
    targets={
      'ruby_specs': RubySpecs,
    }
  )

def register_goals():
  task(name='rspecs', action=RubySpecsRun).install('test')
