# coding=utf-8
# Copyright 2014 Pants project contributors (see CONTRIBUTORS.md).
# Licensed under the Apache License, Version 2.0 (see LICENSE).

# register.py
# When registering a backend in pants.ini, register.py is used by the pants plugin api
# to register new functions exposed in build files, targets, tasks and goals.

from __future__ import (nested_scopes, generators, division, absolute_import, with_statement,
                        print_function, unicode_literals)

from pants.build_graph.build_file_aliases import BuildFileAliases
from squarepants.plugins.square_maven_layout.square_maven_layout import square_maven_layout


def build_file_aliases():
  return BuildFileAliases(
    context_aware_object_factories={
     'square_maven_layout': BuildFileAliases.curry_context(square_maven_layout)
    }
  )
