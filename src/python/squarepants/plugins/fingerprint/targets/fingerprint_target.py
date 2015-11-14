# coding=utf-8
# Copyright 2015 Pants project contributors (see CONTRIBUTORS.md).
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import (absolute_import, division, generators, nested_scopes, print_function,
                        unicode_literals, with_statement)

import logging

from pants.base.payload import Payload
from pants.build_graph.target import Target

logger = logging.getLogger(__name__)


class FingerprintTarget(Target):
  """Target just for causing cache invalidation when its sources are changed."""

  def __init__(self, address=None, payload=None, sources=None, **kwargs):

    """
    :param list sources: Any files that should be fingerprinted.
    """
    self.address = address
    payload = payload or Payload()
    payload.add_fields({
      # NB(gmalmquist): Has to be named something other than 'sources' so we don't mark this as a
      # source root.
      'files': self.create_sources_field(sources or [], address.spec_path),
    })
    super(FingerprintTarget, self).__init__(address=address, payload=payload, **kwargs)
