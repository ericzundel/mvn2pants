# coding=utf-8
# Copyright 2015 Pants project contributors (see CONTRIBUTORS.md).
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from pants.goal.task_registrar import TaskRegistrar as task
from pants.base.build_file_aliases import BuildFileAliases

from squarepants.plugins.copy_signed_jars.targets.signed_jars import SignedJars
from squarepants.plugins.copy_signed_jars.tasks.copy_signed_jars import CopySignedJars

def build_file_aliases():
  return BuildFileAliases.create(
    targets={
      'signed_jars': SignedJars,
    }
  )

def register_goals():
  task(name='copy_signed_jars', action=CopySignedJars).install('binary')
