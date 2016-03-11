# coding=utf-8
# Copyright 2016 Pants project contributors (see CONTRIBUTORS.md).
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from pants.base.payload import Payload
from pants.base.payload_field import PayloadField, PrimitiveField, stable_json_sha1
from pants.backend.jvm.targets.unpacked_jars import UnpackedJars


class UnpackedArchives(UnpackedJars):
  """An UnpackedJars target that copies its contents to a directory not under .pants.d."""

  def __init__(self, payload=None, dest=None, **kwargs):
    payload = payload or Payload()
    payload.add_fields({
      'dest': PrimitiveField(dest),
    })
    super(UnpackedArchives, self).__init__(payload=payload, **kwargs)

  @property
  def destination(self):
    return self.payload.dest
