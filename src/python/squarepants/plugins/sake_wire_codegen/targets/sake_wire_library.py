# coding=utf-8
# Copyright 2015 Pants project contributors (see CONTRIBUTORS.md).
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import (absolute_import, division, generators, nested_scopes, print_function,
                        unicode_literals, with_statement)

import logging

# NB(zundel): these definitions are a part of the source from https://github.com/pantsbuild/pants
from pants.backend.jvm.targets.exportable_jvm_library import ExportableJvmLibrary
from pants.base.exceptions import TargetDefinitionException
from pants.base.payload import Payload
from pants.base.payload_field import PrimitiveField
from pants.base.validation import assert_list


logger = logging.getLogger(__name__)

class SakeWireLibrary(ExportableJvmLibrary):
  """Generates a stub Java library using Wire from .proto files."""

  # NB(zundel): the 'sources' and 'dependencies' fields are defined in a superclass.
  def __init__(self,
               payload=None,
               roots=None,
               registry_class=None,
               enum_options=None,
               no_options=None,
               **kwargs):
    """
    :param list roots: passed through to the --roots option of the Wire compiler
    :param string registry_class: fully qualified class name of RegistryClass to create. If in
    doubt, specify com.squareup.wire.SimpleServiceWriter
    :param list enum_options: list of enums to pass to as the --enum-enum_options option, # optional
    :param boolean no_options: boolean that determines if --no_options flag is passed
    """

    # NB(zundel): The fields encapsulated this way so they can be properly fingerprinted for caching
    payload = payload or Payload()
    payload.add_fields({
      'roots': PrimitiveField(roots or []),
      'registry_class': PrimitiveField(registry_class or None),
      'enum_options': PrimitiveField(enum_options or []),
      'no_options': PrimitiveField(no_options or False),
    })

    # NB(zundel): Perform any other target validation here. Raising TargetDefinitionException
    # causes the BUILD parsing to error out early and show context in the BUILD file where
    # the problem occured.

    super(SakeWireLibrary, self).__init__(payload=payload, **kwargs)
    self.add_labels('codegen')
