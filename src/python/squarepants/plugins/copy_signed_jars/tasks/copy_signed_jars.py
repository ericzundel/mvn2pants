# coding=utf-8
# Copyright 2015 Square, Inc.

import logging
import os
import shutil

from pants.util.dirutil import safe_mkdir
from pants.task.task import Task
from pants.backend.jvm.targets.jvm_binary import JvmBinary
from pants.backend.jvm.targets.jar_library import JarLibrary
from pants.backend.jvm.tasks.classpath_products import ArtifactClasspathEntry

from squarepants.plugins.copy_signed_jars.targets.signed_jars import SignedJars


logger = logging.getLogger(__name__)


class CopySignedJars(Task):
  """Copies jar files specified by signed_jars targets to dist/<basename>-signed-jars."""

  @classmethod
  def prepare(cls, options, round_manager):
    # This task must run after the ivy resolver
    round_manager.require_data('compile_classpath')

  def execute(self):
    """Copies the jar files to the destination specified by the jvm_binary."""
    self._all_targets = self.context.targets()
    signed_jars_targets = self.context.targets(lambda t:  isinstance(t, SignedJars))

    for target in signed_jars_targets:
      self.copy_signed_jars(target)

  def copy_signed_jars(self, signed_jars_target):
    # Find the jvm_binaries that depend on this target
    compile_classpath = self.context.products.get_data('compile_classpath') or {}

    found_binary_targets = set()
    def find_binary_targets(target):
      if isinstance(target, JvmBinary):
        found_binary_targets.add(target)

    self.context.build_graph.walk_transitive_dependee_graph([signed_jars_target.address],
                                                            work=find_binary_targets)
    if not found_binary_targets:
      self.context.log.warn('Ignoring {spec}. Expected at least one jvm_binary() dependency'
                            .format(spec=signed_jars_target.address.spec))
      return

    for binary_target in found_binary_targets:
      # Copy the specified jars into the dist directory for the specified binary base.
      jar_libraries = set()

      def get_jar_library_deps(t):
        if isinstance(t, JarLibrary):
          jar_libraries.add(t)
      signed_jars_target.walk(get_jar_library_deps)

      entries = compile_classpath.get_classpath_entries_for_targets(jar_libraries)
      for conf, classpath_entry in entries:
        if conf != 'default':
          continue
        if not isinstance(classpath_entry, ArtifactClasspathEntry):
          logger.warn('Skipping {}, not an artifact (got type {})'.format(
            classpath_entry.path, type(classpath_entry)))
          continue
        jar_path = classpath_entry.path
        coordinate = classpath_entry.coordinate
        self.context.log.info('Copying {jar} for {target}'
                              .format(jar=jar_path,
                                      target=binary_target.address.spec))
        self._copy_jar_file(binary_target, jar_path, coordinate, signed_jars_target.strip_version)


  def _copy_jar_file(self, binary_target, jar_path, coordinate, strip_version):
    """Copies the artifact into the signed-jar directory.

    Creates the directory if it does not exist.

    :param JvmBinary binary_target: binary that references the signed_jars target
    :param str jar_path: the artifact definition that is the source for the copy
    :param M2Coordinate coordinate: key used to look up this jar
    :param bool strip_version: whether to strip the version of the jar file.
    :returns: path to the jar file to copy
    """
    dest_dir = os.path.join(self.get_options().pants_distdir,
                            '{}-signed-jars'.format(binary_target.basename))
    safe_mkdir(dest_dir)

    if strip_version:
      dest_name = '{name}.jar'.format(name=coordinate.name)
    else:
      dest_name = os.path.basename(jar_path)

    dest_path = os.path.join(dest_dir, dest_name)
    shutil.copy(jar_path, dest_path)
    self.context.log.debug('  Copied {} -> {}.'.format(jar_path, dest_path))
