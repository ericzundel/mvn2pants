# coding=utf-8
# Copyright 2014 Pants project contributors (see CONTRIBUTORS.md).
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import (absolute_import, division, generators, nested_scopes, print_function,
                        unicode_literals, with_statement)

import os
import re

from twitter.common.collections import OrderedSet

from pants.backend.jvm.subsystems.shader import Shader
from pants.backend.jvm.targets.jar_dependency import JarDependency
from pants.backend.jvm.targets.java_library import JavaLibrary
from pants.backend.jvm.targets.java_tests import JavaTests
from pants.backend.jvm.tasks.nailgun_task import NailgunTask
from pants.base.build_environment import get_buildroot
from pants.base.exceptions import TaskError
from pants.base.workunit import WorkUnitLabel
from pants.util.dirutil import safe_mkdir
from pants.util.xml_parser import XmlParser


class FindBugs(NailgunTask):
  """Check Java code for findbugs violations."""

  _FINDBUGS_MAIN = 'edu.umd.cs.findbugs.FindBugs2'
  _HIGH_PRIORITY_LOWEST_RANK = 4
  _NORMAL_PRIORITY_LOWEST_RANK = 9

  @classmethod
  def register_options(cls, register):
    super(FindBugs, cls).register_options(register)

    register('--skip', action='store_true', default=False, fingerprint=True, help='Skip findbugs.')
    register('--jvm-options', advanced=True, action='append', metavar='<option>...',
             help='Run findbugs with these extra jvm options.')
    register('--effort', default='default', choices=['min', 'less', 'default', 'more', 'max'],
             help='Effort of the bug finders.')
    register('--threshold', default='medium', choices=['low', 'medium', 'high', 'experimental'],
             help='Effort of the bug finders.')
    register('--fail-on-error', action='store_true', help='Fail the build on an error.')
    register('--max-rank', type=int, help='Maximum bug ranking to record [1..20].')
    register('--relaxed', action='store_true', default=False, help='Relaxed reporting mode')
    register('--nested', action='store_true', default=True, help='Analyze nested jar/zip archives')
    register('--exclude-filter-file', help='Exclude bugs matching given filter')
    register('--include-filter-file', help='Include only bugs matching given filter')
    register('--exclude-patterns', action='append', default=[],
             help='Adds patterns for targets to be excluded from analysis.')

    cls.register_jvm_tool(register,
                          'findbugs',
                          classpath=[
                            JarDependency(org='com.google.code.findbugs',
                                          name='findbugs',
                                          rev='3.0.1'),
                          ],
                          main=cls._FINDBUGS_MAIN,
                          custom_rules=[
                            Shader.exclude_package('edu.umd.cs.findbugs',
                                                   recursive=True),
                          ])

  @classmethod
  def prepare(cls, options, round_manager):
    super(FindBugs, cls).prepare(options, round_manager)
    round_manager.require_data('runtime_classpath')

  @property
  def cache_target_dirs(self):
    return True

  def execute(self):
    if self.get_options().skip:
      return
    self.findbugs(self.context.target_roots)

  def findbugs(self, targets):
    runtime_classpaths = self.context.products.get_data('runtime_classpath')

    for target in targets:
      if not isinstance(target, (JavaLibrary, JavaTests)):
        self.context.log.debug('Skipping [{}] becuase it is not a java library or java test'.format(target.address.spec))
        continue

      if target.is_synthetic:
        self.context.log.debug('Skipping [{}] because it is a synthetic target'.format(target.address.spec))
        continue

      if self.get_options().exclude_patterns:
        combined_patterns = "(" + ")|(".join(self.get_options().exclude_patterns) + ")"
        if re.match(combined_patterns, target.address.spec):
          self.context.log.debug('Skipping [{}] because it matches exclude pattern'.format(target.address.spec))
          continue

      self.context.log.info(target.address.spec)

      runtime_classpath = runtime_classpaths.get_for_targets(target.closure(bfs=True))
      aux_classpath = OrderedSet(jar for conf, jar in runtime_classpath if conf == 'default')

      target_jars = OrderedSet(jar for conf, jar in runtime_classpaths.get_for_target(target) if conf == 'default')

      if not target_jars:
        self.context.log.info('No jars to be analyzed')
        continue

      output_dir = os.path.join(self.workdir, target.id)
      safe_mkdir(output_dir)
      output_file = os.path.join(output_dir, 'findbugsXml.xml')

      args = [
        '-auxclasspath', ':'.join(aux_classpath - target_jars),
        '-projectName', target.address.spec,
        '-xml:withMessages',
        '-effort:{}'.format(self.get_options().effort),
        '-{}'.format(self.get_options().threshold),
        '-nested:{}'.format('true' if self.get_options().nested else 'false'),
        '-output', output_file,
      ]

      if self.get_options().exclude_filter_file:
        args.extend(['-exclude', os.path.join(get_buildroot(), self.get_options().exclude_filter_file)])

      if self.get_options().include_filter_file:
        args.extend(['-include', os.path.join(get_buildroot(), self.get_options().include_filter_file)])

      if self.get_options().max_rank:
        args.extend(['-maxRank', str(self.get_options().max_rank)])

      if self.get_options().relaxed:
        args.extend(['-relaxed'])

      if self.get_options().level == 'debug':
        args.extend(['-progress'])

      args.extend(target_jars)
      result = self.runjava(classpath=self.tool_classpath('findbugs'),
                            main=self._FINDBUGS_MAIN,
                            jvm_options=self.get_options().jvm_options,
                            args=args,
                            workunit_name='findbugs-command',
                            workunit_labels=[WorkUnitLabel.PREP])
      if result != 0:
        raise TaskError('java {main} ... exited non-zero ({result})'.format(
            main=self._FINDBUGS_MAIN, result=result))

      prioritized_bugs = { 'high': 0, 'normal': 0, 'low': 0 }
      xml = XmlParser.from_file(output_file)
      for bug_instance in xml.parsed.getElementsByTagName('BugInstance'):
        bug_rank = bug_instance.getAttribute('rank')
        if int(bug_rank) <= self._HIGH_PRIORITY_LOWEST_RANK:
          priority = 'high'
        elif int(bug_rank) <= self._NORMAL_PRIORITY_LOWEST_RANK:
          priority = 'normal'
        else:
          priority = 'low'
        prioritized_bugs[priority] += 1

        source_line = bug_instance.getElementsByTagName('Class')[0].getElementsByTagName('SourceLine')[0]
        self.context.log.info('Bug[{priority}]: {type} {desc} {line}'.format(
          priority=priority,
          type=bug_instance.getAttribute('type'),
          desc=bug_instance.getElementsByTagName('LongMessage')[0].firstChild.data,
          src=source_line.getAttribute('classname'),
          line=source_line.getElementsByTagName('Message')[0].firstChild.data))

      prioritized_bugs['total'] = sum(prioritized_bugs.values())
      error_count = len(xml.parsed.getElementsByTagName('Error'))
      if error_count + prioritized_bugs['total'] > 0:
        if self.get_options().fail_on_error:
          raise TaskError('failed with {bug} bugs and {err} errors'.format(
              bug=bug_count, err=error_count))
        if error_count > 0:
          self.context.log.info('Errors: {}'.format(error_count))
        if prioritized_bugs['total'] > 0:
          self.context.log.info("Bugs: {total} (High: {high}, Normal: {normal}, Low: {low})".format(**prioritized_bugs))
