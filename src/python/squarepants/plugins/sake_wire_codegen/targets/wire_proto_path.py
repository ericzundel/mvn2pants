# coding=utf-8
# Copyright 2015 Pants project contributors (see CONTRIBUTORS.md).
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import (absolute_import, division, generators, nested_scopes, print_function,
                        unicode_literals, with_statement)

import logging

# NB(zundel): these definitions are a part of the source from https://github.com/pantsbuild/pants
from pants.base.payload import Payload
from pants.build_graph.target import Target

logger = logging.getLogger(__name__)

class WireProtoPath(Target):
  """Paths containing .proto files that a sake_wire_library depends on."""

  # NB(zundel): the Target base class defines `dependencies` already
  def __init__(self, address=None, payload=None, sources=None, **kwargs):

    """
    :param list sources: .proto files to add to this path
    """

    # NB(zundel): The fields encapsulated this way so they can be properly fingerprinted for caching
    payload = payload or Payload()
    payload.add_fields({
      # NB(zundel): Even though the wire plugin just needs the directory where these sources
      # are kept, enumerating helps pants correctly invalidate a target when sources change.
      'sources': self.create_sources_field(sources or [], address.spec_path),
    })
    super(WireProtoPath, self).__init__(address=address, payload=payload, **kwargs)

