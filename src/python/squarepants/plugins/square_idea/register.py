# coding=utf-8
# Copyright 2015 Square, Inc.

from pants.goal.goal import Goal
from pants.goal.task_registrar import TaskRegistrar as task
from pants.backend.project_info.tasks.idea_gen import IdeaGen


from squarepants.plugins.square_idea.tasks.square_idea import SquareIdea
from squarepants.plugins.square_idea.tasks.show_new_idea_moved_message import ShowNewIdeaMovedMessage

def register_goals():
  Goal.by_name('idea').uninstall_task('idea')
  Goal.register('old-idea',
    'The old, deprecated task to generate an IntelliJ project (this is the task used in '
    'open-source pants).')
  Goal.register('idea', 
    'Generates an IntelliJ project for the specified targets and transitive dependencies. This is '
    'Square\'s internal version of the idea goal, implemented as a plugin.')
  Goal.register('new-idea', 'This has been renamed to just "idea".')

  task(name='old-idea', action=IdeaGen).install('old-idea')
  task(name='idea', action=SquareIdea).install('idea')
  task(name='new-idea', action=ShowNewIdeaMovedMessage).install('new-idea')
