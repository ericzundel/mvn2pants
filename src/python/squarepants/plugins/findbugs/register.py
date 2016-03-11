# coding=utf-8
# Copyright 2015 Pants project contributors (see CONTRIBUTORS.md).
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from pants.goal.goal import Goal
from pants.goal.task_registrar import TaskRegistrar as task

from squarepants.plugins.findbugs.tasks.findbugs_task import FindBugs

def register_goals():
  Goal.register('findbugs', 'Check Java code for findbugs violations.')
  task(name='findbugs', action=FindBugs).install()
