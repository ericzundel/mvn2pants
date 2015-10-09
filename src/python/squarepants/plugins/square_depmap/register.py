# coding=utf-8
# Copyright 2015 Square, Inc.

from pants.goal.task_registrar import TaskRegistrar as task
from pants.build_graph.build_file_aliases import BuildFileAliases

from squarepants.plugins.square_depmap.tasks.square_depmap import SquareDepmap

def register_goals():
  task(name='sq-depmap', action=SquareDepmap).install('sq-depmap').with_description(
    'Generates a visualization of the dependency graph of the target arguments using graphviz dot.'
  )
