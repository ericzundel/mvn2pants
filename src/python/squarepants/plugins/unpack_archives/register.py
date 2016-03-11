# coding=utf-8
# Copyright 2015 Pants project contributors (see CONTRIBUTORS.md).
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from pants.goal.goal import Goal
from pants.goal.task_registrar import TaskRegistrar as task
from pants.build_graph.build_file_aliases import BuildFileAliases

from squarepants.plugins.unpack_archives.targets.unpacked_archives import UnpackedArchives
from squarepants.plugins.unpack_archives.tasks.unpack_archives import UnpackArchives

def build_file_aliases():
  return BuildFileAliases(
    targets={
      'unpacked_archives': UnpackedArchives,
    }
  )

def register_goals():
  task(name='unpack-archives', action=UnpackArchives).install('resolve', after='unpack-jars')
