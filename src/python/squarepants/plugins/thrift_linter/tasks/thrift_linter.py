# coding=utf-8
# Copyright 2015 Square, Inc.

from pants.backend.core.tasks.task import Task

# TODO(zundel): this is a temporary workaround for compatibility with the IntelliJ plugin for pants.
# remove it once the plugin is upgraded
class ThriftLinterDummy(Task):

  @classmethod
  def register_options(cls, register):
    super(ThriftLinterDummy, cls).register_options(register)
    register('--skip', help='No-op option to satisfy Pants Support IntelliJ plugin')

  def execute(self):
    """Do nothing"""
    pass
