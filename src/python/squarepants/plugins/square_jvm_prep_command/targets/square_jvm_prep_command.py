# coding=utf-8
# Copyright 2015 Pants project contributors (see CONTRIBUTORS.md).
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import (absolute_import, division, generators, nested_scopes, print_function,
                        unicode_literals, with_statement)

from pants.backend.jvm.targets.jvm_prep_command import JvmPrepCommand

class SquareJvmPrepCommand(JvmPrepCommand):
  """Custom override of JvmPrepCommand to add more goals."""

  @staticmethod
  def goals():
    return list(JvmPrepCommand.goals() + ['jooq'])
