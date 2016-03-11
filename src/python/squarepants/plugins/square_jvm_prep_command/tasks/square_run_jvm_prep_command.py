# coding=utf-8
# Copyright 2015 Pants project contributors (see CONTRIBUTORS.md).
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import (absolute_import, division, generators, nested_scopes, print_function,
                        unicode_literals, with_statement)

from pants.backend.jvm.tasks.run_jvm_prep_command import RunJvmPrepCommandBase


class RunJooqJvmPrepCommand(RunJvmPrepCommandBase):
  """Run code from a JVM compiled language before other tasks in the jooq goal.

  Register this tasks to run code at the beginning of the jooq goal in register.py

   task(name='jooq-jvm-prep-command', action=RunJooqJvmPrepCommand).install('jooq', first=True)
  """
  goal = 'jooq'
