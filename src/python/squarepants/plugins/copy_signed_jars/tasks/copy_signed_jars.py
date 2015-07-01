# coding=utf-8
# Copyright 2015 Square, Inc.

import os
import re
import shutil

from pants.util.dirutil import safe_mkdir
from pants.backend.jvm.targets.jvm_binary import JvmBinary
from pants.backend.jvm.targets.jar_library import JarLibrary
from pants.backend.core.tasks.task import Task


from squarepants.plugins.copy_signed_jars.targets.signed_jars import SignedJars


class CopySignedJars(Task):
  """Copies jar files specified by signed_jars targets to dist/<basename>-signed-jars."""

  @staticmethod
  def prepare(self, round_manager):
    # This task must run after the ivy resolver
    round_manager.require_data('ivy_jar_products')

  def execute(self):
    """Copies the jar files to the destination specified by the jvm_binary."""
    self._all_targets = self.context.targets()
    signed_jars_targets = self.context.targets(lambda t:  isinstance(t, SignedJars))

    for target in signed_jars_targets:
      self.copy_signed_jars(target)


  def _get_ivy_info(self):
    ivy_jar_products = self.context.products.get_data('ivy_jar_products') or {}
    # This product is a list for historical reasons (exclusives groups) but in practice should
    # have either 0 or 1 entries.
    ivy_info_list = ivy_jar_products.get('default')
    if ivy_info_list:
      return ivy_info_list[0]
    return None

  def copy_signed_jars(self, signed_jars_target):
    # Find the jvm_binaries that depend on this target
    ivy_info = self._get_ivy_info()

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

      def get_java_deps(t):
        if isinstance(t, JarLibrary):
          jar_libraries.add(t)
      signed_jars_target.walk(get_java_deps)

      for jar_library in jar_libraries:
        artifacts = ivy_info.get_artifacts_for_jar_library(jar_library)
        for artifact in artifacts:
          self.context.log.info('Copying {jar} for {target}'
                                .format(jar=artifact.path,
                                        target=binary_target.address.spec))
          self._copy_jar_file(binary_target, artifact, signed_jars_target.strip_version)


  def _copy_jar_file(self, binary_target, artifact, strip_version):
    """Copies the artifact into the signed-jar directory.

    Creates the directory if it does not exist.

    :param JvmBinary binary_target: binary that references the signed_jars target
    :param IvyArtifact artifact: the artifact definition that is the source
    :param bool strip_version: whether to strip the version of the jar file.
    :returns: path to the jar file to copy
    """
    dest_dir = os.path.join(self.get_options().pants_distdir,
                            '{}-signed-jars'.format(binary_target.basename))
    safe_mkdir(dest_dir)
    dest_name = os.path.basename(artifact.path)

    if strip_version:
      # Rediscover the (org, name, rev) of the jar, so we can strip it out.
      # This is a little hacky; I'm not sure if there's a better way to do it.

      # We can assume jar_info exists, because otherwise this method would never have
      # been called.
      dest_name_template= '{name}.jar'
      jar_info, = self.context.products.get_data('ivy_jar_products')['default']
      module_ref = None
      for ref, modules in jar_info.modules_by_ref.items():
        if not ref.unversioned or ref.unversioned not in jar_info._artifacts_by_ref:
          continue
        if artifact in jar_info._artifacts_by_ref[ref.unversioned]:
          module_ref = ref
      if module_ref is not None:
        org, name, rev = module_ref.org, module_ref.name, module_ref.rev
        dest_name = dest_name_template.format(org=org, name=name)
      else:
        self.context.log.warn('strip_version is set, but could not find (org,name,rev) '
                              'details for {}.'.format(artifact.path))

    dest_path = os.path.join(dest_dir, dest_name)
    shutil.copy(artifact.path, dest_path)
    self.context.log.debug('  Copied {} -> {}.'.format(artifact.path, dest_path))

