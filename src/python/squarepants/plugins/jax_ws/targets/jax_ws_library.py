# coding=utf-8
# Copyright 2015 Pants project contributors (see CONTRIBUTORS.md).
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import (absolute_import, division, generators, nested_scopes, print_function,
                        unicode_literals, with_statement)

import logging
import os

# NB(zundel): these definitions are a part of the source from https://github.com/pantsbuild/pants
from pants.backend.jvm.targets.exportable_jvm_library import ExportableJvmLibrary
from pants.base.exceptions import TargetDefinitionException
from pants.base.payload import Payload
from pants.base.payload_field import PrimitiveField


logger = logging.getLogger(__name__)

class JaxWsLibrary(ExportableJvmLibrary):
  """Generates a Java library from JAX-WS wsdl files."""

  def __init__(self,
               payload=None,
               vm_args=None,
               xjc_args=None,
               extra_args=None,
               **kwargs):
    """Generates a Java library from WSDL files using JAX-WS.

    :param list vm_args: Additional arguments for the JVM.
    :param list xjc_args: Additional arguments to xjc.
    :param list extra_args: Additional arguments for the CLI.
    """
    payload = payload or Payload()
    payload.add_fields({
      'vm_args': PrimitiveField(vm_args or ()),
      'xjc_args': PrimitiveField(xjc_args or ()),
      'extra_args': PrimitiveField(extra_args or ()),
    })
    super(JaxWsLibrary, self).__init__(payload=payload, **kwargs)
    self.add_labels('codegen')
