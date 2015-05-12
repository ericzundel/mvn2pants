# coding=utf-8
# Copyright 2015 Pants project contributors (see CONTRIBUTORS.md).
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import (nested_scopes, generators, division, absolute_import, with_statement,
                        print_function, unicode_literals)

from pants.base.build_file_aliases import BuildFileAliases

from  squarepants.plugins.square_manifest.square_manifest import SquareManifest


def build_file_aliases():
  return BuildFileAliases.create(
    context_aware_object_factories={
      'square_manifest': SquareManifest,
    },
  )
