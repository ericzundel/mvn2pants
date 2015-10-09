# coding=utf-8
# Copyright 2015 Pants project contributors (see CONTRIBUTORS.md).
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from pants.build_graph.target import Target
from pants.base.payload import Payload
from pants.base.payload_field import SourcesField

class RubySpecs(Target):
  """Ruby RSpec target"""

  def __init__(self, address=None, payload=None, sources=None, sources_rel_path=None, **kwargs):
    if sources_rel_path is None:
      sources_rel_path = address.spec_path
    payload = payload or Payload()
    payload.add_fields({
      'sources': SourcesField(sources=self.assert_list(sources),
                              sources_rel_path=sources_rel_path),
    })
    super(RubySpecs, self).__init__(address=address, payload=payload, **kwargs)
