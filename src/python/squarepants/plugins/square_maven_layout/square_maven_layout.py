# coding=utf-8
# Copyright 2014 Pants project contributors (see CONTRIBUTORS.md).
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import (nested_scopes, generators, division, absolute_import, with_statement,
                        print_function, unicode_literals)

import os

from pants.backend.codegen.targets.java_protobuf_library import JavaProtobufLibrary
from pants.backend.codegen.targets.java_wire_library import JavaWireLibrary
from pants.backend.codegen.targets.jaxb_library import JaxbLibrary
from pants.backend.jvm.targets.jar_library import JarLibrary
from pants.backend.jvm.targets.java_tests import JavaTests
from pants.backend.jvm.targets.jvm_binary import JvmBinary
from pants.backend.jvm.targets.unpacked_jars import UnpackedJars
from pants.backend.maven_layout.maven_layout import maven_layout
from pants.base.source_root import SourceRoot

def square_maven_layout(parse_context, basedir=''):
  """Sets up typical maven project source roots for all built-in pants target types.

  See maven_layout() defined in the pants source code. Appends additional roots and targets
  to the stock version.

  :param string basedir: Instead of using this BUILD file's directory as
    the base of the source tree, use a subdirectory. E.g., instead of
    expecting to find java files in ``src/main/java``, expect them in
    ``**basedir**/src/main/java``.
  """
  def root(path, *types):
    SourceRoot.register_mutable(os.path.join(parse_context.rel_path, basedir, path), *types)

  # Use the stock maven_layout to get started
  maven_layout(parse_context, basedir=basedir)

  # Add additional targets to existing source roots
  root('src/main/java', JarLibrary, JavaTests)
  root('src/main/resources', JaxbLibrary)

  root('src/test/java', JarLibrary, JvmBinary)
  root('src/test/resources', JaxbLibrary)

  # Add additional source roots
  root('src/main/proto', JavaProtobufLibrary, JarLibrary, UnpackedJars)
  root('src/test/proto', JavaProtobufLibrary, JarLibrary, UnpackedJars)
  root('src/main/wire_proto', JavaWireLibrary, JarLibrary, UnpackedJars)
  root('src/test/wire_proto', JavaWireLibrary, JarLibrary, UnpackedJars)
