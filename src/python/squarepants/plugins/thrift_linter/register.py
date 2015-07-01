# coding=utf-8
# Copyright 2015 Square, Inc.

from pants.goal.task_registrar import TaskRegistrar as task

from squarepants.plugins.thrift_linter.tasks.thrift_linter import ThriftLinterDummy

def register_goals():
  task(name='thrift-linter', action=ThriftLinterDummy).install().with_description('Standin for thrift-linter options')
