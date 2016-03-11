# coding=utf-8
# Copyright 2015 Pants project contributors (see CONTRIBUTORS.md).
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from pants.goal.goal import Goal
from pants.goal.task_registrar import TaskRegistrar as task
from pants.build_graph.build_file_aliases import BuildFileAliases

from squarepants.plugins.link_resources_jars.targets.resources_jar import ResourcesJar
from squarepants.plugins.link_resources_jars.tasks.link_resources_jars import LinkResourcesJars

def build_file_aliases():
  return BuildFileAliases(
    targets={
      'resources_jar': ResourcesJar,
    }
  )

def register_goals():
  task(name='link-resources-jars', action=LinkResourcesJars).install('gen')
