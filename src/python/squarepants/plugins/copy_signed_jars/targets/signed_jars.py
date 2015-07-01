# coding=utf-8
# Copyright 2015 Pants project contributors (see CONTRIBUTORS.md).
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from pants.backend.jvm.targets.jar_dependency import JarDependency
from pants.base.target import Target
from pants.base.payload import Payload
from pants.base.payload_field import JarsField

class SignedJars(Target):
  """A target that lists the signed jars that should be copied with the copy_signed_jars task."""

  def __init__(self, address=None, strip_version=False, **kwargs):
    super(SignedJars, self).__init__(address=address, **kwargs)
    self.strip_version = strip_version