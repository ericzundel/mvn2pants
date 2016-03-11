# coding=utf-8
# Copyright 2016 Pants project contributors (see CONTRIBUTORS.md).
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import (nested_scopes, generators, division, absolute_import, with_statement,
                        print_function, unicode_literals)

from pants.build_graph.build_file_aliases import BuildFileAliases

from  squarepants.plugins.build_symbols.build_symbols import BuildSymbols


def build_file_aliases():
  return BuildFileAliases(
    context_aware_object_factories={
      'symbols': BuildSymbols,
    },
  )
