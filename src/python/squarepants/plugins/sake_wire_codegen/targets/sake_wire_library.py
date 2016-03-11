# coding=utf-8
# Copyright 2015 Pants project contributors (see CONTRIBUTORS.md).
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import (absolute_import, division, generators, nested_scopes, print_function,
                        unicode_literals, with_statement)

import logging

# NB(zundel): these definitions are a part of the source from https://github.com/pantsbuild/pants
from pants.backend.jvm.targets.jvm_target import JvmTarget
from pants.base.payload import Payload
from pants.base.payload_field import PrimitiveField


logger = logging.getLogger(__name__)

class SakeWireLibrary(JvmTarget):
  """Generates a stub Java library using Wire from .proto files."""

  # NB(zundel): the 'sources' and 'dependencies' fields are defined in a superclass.
  def __init__(self,
               payload=None,
               roots=None,
               proto_files=None,
               **kwargs):
    """
    :param list roots: Passed through to the --roots option of the Wire compiler
    :param list proto_files: List of relative proto files to generated code for. If provided, this
      overrides whatever is specified in `sources`. Unlike `sources`, `proto_files` can include
      entries that do not exist on the filesystem directly under the BUILD file where this target is
      specified -- they are just relative filenames that might be located anywhere in this target's
      proto path.
    """

    # NB(zundel): The fields encapsulated this way so they can be properly fingerprinted for caching
    payload = payload or Payload()
    payload.add_fields({
      'roots': PrimitiveField(roots or []),
      'proto_files': PrimitiveField(proto_files or []),
    })

    # NB(zundel): Perform any other target validation here. Raising TargetDefinitionException
    # causes the BUILD parsing to error out early and show context in the BUILD file where
    # the problem occured.

    super(SakeWireLibrary, self).__init__(payload=payload, **kwargs)
    self.add_labels('codegen')
