# coding=utf-8
# Copyright 2015 Pants project contributors (see CONTRIBUTORS.md).
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from pants.goal.task_registrar import TaskRegistrar as task
from pants.build_graph.build_file_aliases import BuildFileAliases

from squarepants.plugins.sake_wire_codegen.targets.wire_proto_path import WireProtoPath
from squarepants.plugins.sake_wire_codegen.targets.sake_wire_library import SakeWireLibrary
from squarepants.plugins.sake_wire_codegen.tasks.sake_wire_codegen import SakeWireCodegen

def build_file_aliases():
  return BuildFileAliases(
    targets={
      'wire_proto_path': WireProtoPath,
      'sake_wire_library': SakeWireLibrary,
    }
  )

def register_goals():
  task(name='sake-wire-codegen', action=SakeWireCodegen).install('gen')
