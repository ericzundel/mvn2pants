# coding=utf-8
# Copyright 2015 Square, Inc.

from pants.goal.goal import Goal
from pants.goal.task_registrar import TaskRegistrar as task
from pants.backend.project_info.tasks.idea_gen import IdeaGen


from squarepants.plugins.square_idea.tasks.square_idea import SquareIdea

def register_goals():

  # NB(gmalmquist): Uncomment the lines below when we are ready to promote our custom idea goal to
  # the primary version.

  # Goal.by_name('idea').uninstall_task('idea')
  #
  # task(name='old-idea', action=IdeaGen).install('old-idea').with_description(
  #   'The old task to generate an IntelliJ project (this is the task used in open-source pants).'
  # )

  task(name='new-idea', action=SquareIdea).install('new-idea').with_description(
    'Generates an IntelliJ project for the specified targets and transitive dependencies. This is '
    'Square\'s internal version of the idea goal, implemented as a plugin.'
  )
