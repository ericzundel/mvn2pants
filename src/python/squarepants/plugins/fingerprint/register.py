# coding=utf-8
# Copyright 2015 Pants project contributors (see CONTRIBUTORS.md).
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from pants.goal.goal import Goal
from pants.build_graph.build_file_aliases import BuildFileAliases
from pants.goal.task_registrar import TaskRegistrar as task

from squarepants.plugins.fingerprint.targets.fingerprint_target import FingerprintTarget
from squarepants.plugins.fingerprint.tasks.invalidate_fingerprint_dependees import InvalidateFingerpintDependees

def build_file_aliases():
  return BuildFileAliases(
    targets={
      'fingerprint': FingerprintTarget,
    }
  )


def register_goals():
  Goal.register('invalidate-fingerprint-dependees', 
    'Hack to make sure that java libraries are recompiled when a resource is changed.')
  task(name='invalidate-fingerprint-dependees',
       action=InvalidateFingerpintDependees).install('invalidate-fingerprint-dependees')
