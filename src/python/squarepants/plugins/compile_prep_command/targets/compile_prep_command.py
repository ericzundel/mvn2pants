# coding=utf-8
# Copyright 2014 Pants project contributors (see CONTRIBUTORS.md).
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import (absolute_import, division, generators, nested_scopes, print_function,
                        unicode_literals, with_statement)

from pants.base.payload import Payload
from pants.base.payload_field import PrimitiveField
from pants.build_graph.target import Target


class CompilePrepCommand(Target):
  """A command that must be run before some other target can be compiled.

  For example, you can use `compile_prep_command()` to execute a script that sets up tunnels to database
  servers. These tunnels could then be leveraged by integration tests.

  Pants will only execute the `compile_prep_command()` under the test goal, when testing targets that
  depend on the `prep_command()` target.
  """

  def __init__(self, executable=None, args=None, payload=None, environ=False, **kwargs):
    """
    :param executable: The path to the executable that should be run.
    :param args: A list of command-line args to the excutable.
    :param environ: If True, the output of the command will be treated as
      a \\\\0-separated list of key=value pairs to insert into the environment.
      Note that this will pollute the environment for all future tests, so
      avoid it if at all possible.
    """
    payload = payload or Payload()
    payload.add_fields({
      'executable': PrimitiveField(executable),
      'args': PrimitiveField(args or []),
      'environ': PrimitiveField(environ),
    })
    super(CompilePrepCommand, self).__init__(payload=payload, **kwargs)
