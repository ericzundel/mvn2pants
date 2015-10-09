# coding=utf-8
# Copyright 2014 Pants project contributors (see CONTRIBUTORS.md).
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import (absolute_import, division, generators, nested_scopes, print_function,
                        unicode_literals, with_statement)

import logging
import os

from twitter.common.collections import OrderedSet

from pants.backend.codegen.tasks.simple_codegen_task import SimpleCodegenTask
from pants.backend.jvm.targets.jar_dependency import JarDependency
from pants.backend.jvm.targets.java_library import JavaLibrary
from pants.backend.jvm.tasks.jvm_tool_task_mixin import JvmToolTaskMixin
from pants.base.exceptions import TaskError
from pants.base.source_root import SourceRoot
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

    def wire_jar(name):
      # NB: this is just a default version and can be overriden in BUILD.tools
      return JarDependency(org='com.squareup.wire', name=name, rev='1.6.0')

    cls.register_jvm_tool(register,
                          'javadeps',
                          classpath=[
                            wire_jar(name='wire-runtime')
                          ],
                          classpath_spec='//:wire-runtime',
                          help='Runtime dependencies for wire-using Java code.')
    cls.register_jvm_tool(register, 'wire-compiler', classpath=[wire_jar(name='wire-compiler')])

  @classmethod
  def subsystem_dependencies(cls):
    return super(SakeWireCodegen, cls).subsystem_dependencies() + (DistributionLocator,)

  def __init__(self, *args, **kwargs):
    """Generates Java files from .proto files using the Wire protobuf compiler."""
    super(SakeWireCodegen, self).__init__(*args, **kwargs)

  @property
  def synthetic_target_type(self):
    return JavaLibrary

  def is_gentarget(self, target):
    return isinstance(target, SakeWireLibrary)

  @classmethod
  def supported_strategy_types(cls):
    return [cls.IsolatedCodegenStrategy]

  def synthetic_target_extra_dependencies(self, target):
    wire_runtime_deps_spec = self.get_options().javadeps
    return self.resolve_deps([wire_runtime_deps_spec])


  def execute_codegen(self, targets):
    # Invoke the generator once per target.  Because the wire compiler has flags that try to reduce
    # the amount of code emitted, Invoking them all together will break if one target specifies a
    # service_writer and another does not, or if one specifies roots and another does not.
    execute_java = DistributionLocator.cached().execute_java
    for target in targets:
      args = self._format_args_for_target(target)
      if args:
        # NB(zundel): execute_java() will use nailgun bt default.
        # Replace the class here with the main() to invoke for sake-wire-codegen
        result = execute_java(classpath=self.tool_classpath('wire-compiler'),
                              main='com.squareup.wire.WireCompiler',
                              args=args)
        if result != 0:
          raise TaskError('Wire compiler exited non-zero ({0})'.format(result))

  # NB(zundel): This is a pared down version of the exisiting wire plugin. We could use the
  # python 'json' library if you just want to create a glob of configuration and pass it as
  # a single file argument to the plugin
  def _format_args_for_target(self, target):
    """Calculate the arguments to pass to the command line for a single target."""

    sources = OrderedSet(target.sources_relative_to_buildroot())
    if not self.validate_sources_present(sources, [target]):
      return None
    relative_sources = OrderedSet()

    # Compute the source path relative to the 'source root' which is the path used at the
    # root of imports
    for source in sources:
      source_root = SourceRoot.find_by_path(source)
      relative_sources.add(os.path.relpath(source, source_root))

    args = ['--java_out={0}'.format(self.codegen_workdir(target))]

    if target.payload.get_field_value('no_options'):
      args.append('--no_options')

    registry_class = target.payload.registry_class
    if registry_class:
      args.append('--registry_class={0}'.format(registry_class))

    if target.payload.roots:
      args.append('--roots={0}'.format(','.join(target.payload.roots)))

    if target.payload.enum_options:
      args.append('--enum_options={0}'.format(','.join(target.payload.enum_options)))

    for path in self._calculate_proto_paths(target):
      args.append('--proto_path={0}'.format(path))

    args.extend(relative_sources)
    return args

  def _calculate_proto_paths(self, target):
    """Computes the set of paths that wire uses to lookup imported protos.

    The protos under these paths are not necessarily compiled, but they are required to compile
    the protos that were specified imported.
    :param target: the SakeWireLibrary target to compile.
    :return: an ordered set of directories to pass along to wire.
    """
    wire_proto_targets = [ t for t in target.closure() if isinstance(t, WireProtoPath)]
    proto_paths=set()
    for target in wire_proto_targets:
      proto_paths.add(SourceRoot.find(target))
    return list(proto_paths)


