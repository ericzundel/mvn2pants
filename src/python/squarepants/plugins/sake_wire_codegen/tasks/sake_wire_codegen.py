# coding=utf-8
# Copyright 2014 Pants project contributors (see CONTRIBUTORS.md).
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import (absolute_import, division, generators, nested_scopes, print_function,
                        unicode_literals, with_statement)

import logging
import os

from twitter.common.collections import OrderedSet

from pants.backend.codegen.targets.java_wire_library import JavaWireLibrary
from pants.backend.codegen.tasks.simple_codegen_task import SimpleCodegenTask
from pants.backend.jvm.targets.jar_dependency import JarDependency
from pants.backend.jvm.targets.java_library import JavaLibrary
from pants.backend.jvm.tasks.jvm_tool_task_mixin import JvmToolTaskMixin
from pants.base.exceptions import TaskError
from pants.java.distribution.distribution import DistributionLocator

from squarepants.plugins.sake_wire_codegen.targets.sake_wire_library import SakeWireLibrary
from squarepants.plugins.sake_wire_codegen.targets.wire_proto_path import WireProtoPath

logger = logging.getLogger(__name__)


# For the SimpleCodegenTask superclass, see
# https://github.com/pantsbuild/pants/blob/master/src/python/pants/backend/codegen/tasks/simple_codegen_task.py
class SakeWireCodegen(JvmToolTaskMixin, SimpleCodegenTask):

  @classmethod
  def register_options(cls, register):
    super(SakeWireCodegen, cls).register_options(register)

    # NB: this is just a default version and can be overridden in BUILD.tools
    default_wire_runtime = [
      JarDependency(org='com.squareup.wire', name='wire-runtime', rev='2.0.0')
    ]
    default_wire_compiler = [
      JarDependency(org='com.squareup.wire', name='wire-compiler', rev='2.0.0')
    ]

    cls.register_jvm_tool(register,
                          'wire-runtime',
                          classpath=default_wire_runtime,
                          classpath_spec='//:wire-runtime',
                          help='Runtime dependencies for wire-using Java code.')
    cls.register_jvm_tool(register, 'wire-compiler', classpath=default_wire_compiler)

  @classmethod
  def subsystem_dependencies(cls):
    return super(SakeWireCodegen, cls).subsystem_dependencies() + (DistributionLocator,)

  def __init__(self, *args, **kwargs):
    """Generates Java files from .proto files using the Wire protobuf compiler."""
    super(SakeWireCodegen, self).__init__(*args, **kwargs)

  def synthetic_target_type(self, target):
    return JavaLibrary

  def is_gentarget(self, target):
    return isinstance(target, SakeWireLibrary)

  @classmethod
  def supported_strategy_types(cls):
    return [cls.IsolatedCodegenStrategy]

  def synthetic_target_extra_dependencies(self, target, target_workdir):
    wire_runtime_deps_spec = self.get_options().wire_runtime
    return self.resolve_deps([wire_runtime_deps_spec])


  def execute_codegen(self, target, target_workdir):

    execute_java = DistributionLocator.cached().execute_java
    args = self._format_args_for_target(target, target_workdir)
    if args:
      # NB(zundel): execute_java() will use nailgun bt default.
      # Replace the class here with the main() to invoke for sake-wire-codegen
      result = execute_java(classpath=self.tool_classpath('wire-compiler'),
                            main='com.squareup.sake.wire.SakeWireCodegenCli',
                            args=args)
      if result != 0:
        raise TaskError('Wire compiler exited non-zero ({0})'.format(result))

  # NB(zundel): This is a pared down version of the exisiting wire plugin. We could use the
  # python 'json' library if you just want to create a glob of configuration and pass it as
  # a single file argument to the plugin
  def _format_args_for_target(self, target, target_workdir):
    """Calculate the arguments to pass to the command line for a single target."""

    relative_proto_files = OrderedSet()
    if target.payload.proto_files:
      relative_proto_files.update(target.payload.proto_files)
    else:
      sources = OrderedSet(target.sources_relative_to_buildroot())
      if not self.validate_sources_present(sources, [target]):
        return None
      # Compute the source path relative to the 'source root' which is the path used at the
      # root of imports
      for source in sources:
        source_root = self.context.source_roots.find_by_path(source).path
        relative_proto_files.add(os.path.relpath(source, source_root))

    args = ['--generated-source-directory', target_workdir]

    for root in target.payload.roots:
      args.extend(['--root', root])

    for path in self._calculate_proto_paths(target):
      # NB(gmalmquist): This isn't a typo. The --source argument is actually a proto path.
      args.extend(['--source', path])

    for source in relative_proto_files:
      args.extend(['--proto', source])

    return args

  def _use_as_proto_path(self, target):
    types = (WireProtoPath, SakeWireCodegen, JavaWireLibrary)
    return any(isinstance(target, type_) for type_ in types)

  def _calculate_proto_paths(self, target):
    """Computes the set of paths that wire uses to lookup imported protos.

    The protos under these paths are not necessarily compiled, but they are required to compile
    the protos that were specified imported.
    :param target: the SakeWireLibrary target to compile.
    :return: an ordered set of directories to pass along to wire.
    """
    wire_proto_targets = filter(self._use_as_proto_path, target.closure())
    proto_paths=set()
    proto_paths.add(self.context.source_roots.find(target).path)
    for target in wire_proto_targets:
      for proto_source in target.payload.sources.relative_to_buildroot():
        proto_paths.add(self.context.source_roots.find_by_path(proto_source).path)
    return list(proto_paths)

  @property
  def _copy_target_attributes(self):
    """Propagate the provides attribute to the synthetic java_library() target for publishing."""
    return ['provides']
