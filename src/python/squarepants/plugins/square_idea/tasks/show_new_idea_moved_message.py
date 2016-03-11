# coding=utf-8
# Copyright 2015 Square, Inc.

from __future__ import print_function, with_statement

import logging

from pants.task.task import Task
from textwrap import dedent


logger = logging.getLogger(__name__)


class ShowNewIdeaMovedMessage(Task):
  """Displays a message letting people know that the new-idea goal has been renamed."""

  def execute(self):
    self.context.log.info(dedent('''
      The "./pants new-idea" goal has been promoted and is now just "./pants idea".

      The previous, deprecated idea goal is now "./pants old-idea".

      You may need to update any flags or options you have set (eg, --new-idea-project-name is now
      just --idea-project-name).
    '''))
    self.context.log.error('Please re-run ./pants using "idea" instead of "new-idea".\n')
