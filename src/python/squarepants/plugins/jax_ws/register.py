# coding=utf-8
# Copyright 2015 Pants project contributors (see CONTRIBUTORS.md).
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from pants.goal.goal import Goal
from pants.goal.task_registrar import TaskRegistrar as task
from pants.build_graph.build_file_aliases import BuildFileAliases

from squarepants.plugins.jax_ws.targets.jax_ws_library import JaxWsLibrary
from squarepants.plugins.jax_ws.tasks.jax_ws_gen import JaxWsGen

def build_file_aliases():
  return BuildFileAliases(
    targets={
      'jax_ws_library': JaxWsLibrary,
    }
  )

def register_goals():
  Goal.register('jax-ws-gen', 'Generated code for jax-ws xml templates.')
  task(name='jax-ws-gen', action=JaxWsGen).install('gen')
