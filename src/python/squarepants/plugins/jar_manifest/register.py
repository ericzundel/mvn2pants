# coding=utf-8
# Copyright 2015 Square, Inc.

from pants.goal.goal import Goal
from pants.goal.task_registrar import TaskRegistrar as task
from pants.build_graph.build_file_aliases import BuildFileAliases

from squarepants.plugins.jar_manifest.tasks.jar_manifest import JarManifestTask

def register_goals():
  Goal.register('jar-manifest', 'Place a text file into META-INF/ with a list of all the 3rdparty jars bundled into a binary') 
  task(name='jar-manifest', action=JarManifestTask, serialize=False).install()
