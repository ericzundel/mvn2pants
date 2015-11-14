# coding=utf-8
# Copyright 2015 Square, Inc.

from pants.goal.task_registrar import TaskRegistrar as task
from pants.build_graph.build_file_aliases import BuildFileAliases

from squarepants.plugins.jar_manifest.tasks.jar_manifest import JarManifestTask

def register_goals():
  task(name='jar-manifest', action=JarManifestTask, serialize=False).install().with_description('Build a manifest of all artifact jars and add to resources')
