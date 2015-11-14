# coding=utf-8
# Copyright 2015 Pants project contributors (see CONTRIBUTORS.md).
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from pants.base.payload import Payload
from pants.base.payload_field import PayloadField, PrimitiveField, stable_json_sha1
from pants.build_graph.target import Target
from pants.backend.jvm.targets.jar_library import JarLibrary


class ResourcesJar(Target):
  """A target that lists jars that should be copied onto the resources path.

  These targets are expected to be dependencies of a Resources target.
  """

  def __init__(self, address=None, payload=None, dest=None,
               **kwargs):
    payload = payload or Payload()
    payload.add_fields({
      'dest': PrimitiveField(dest),
    })
    super(ResourcesJar, self).__init__(address=address, payload=payload, **kwargs)

  @property
  def library(self):
    for dep in self.dependencies:
      if isinstance(dep, JarLibrary):
        return dep
