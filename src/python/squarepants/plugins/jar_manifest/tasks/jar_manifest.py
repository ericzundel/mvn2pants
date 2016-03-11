# coding=utf-8
# Copyright 2015 Square, Inc.

import os

from pants.task.task import Task
from pants.backend.jvm.targets.jvm_binary import JvmBinary
from pants.backend.jvm.tasks.classpath_products import ArtifactClasspathEntry
from pants.util.dirutil import safe_mkdir


class JarManifestTask(Task):
  """Create a list of all the external jars bundled into this artifact."""

  @classmethod
  def prepare(cls, options, round_manager):
    round_manager.require_data('compile_classpath')

  @classmethod
  def product_types(cls):
    return ['runtime_classpath']

  @property
  def cache_target_dirs(self):
    return True

  def execute(self):
    targets = self.context.targets(predicate=lambda t: isinstance(t, JvmBinary))
    compile_classpath = self.context.products.get_data('compile_classpath')
    runtime_classpath = self.context.products.get_data('runtime_classpath', compile_classpath.copy)
    with self.invalidated(targets,
                          invalidate_dependents=True) as invalidation_check:
      for vt in invalidation_check.all_vts:
        if not vt.valid:
          self.add_manifest(vt.target, vt.results_dir, compile_classpath)
          vt.update()
        runtime_classpath.add_for_target(vt.target, [('default', vt.results_dir)])

  def add_manifest(self, target, target_workdir, compile_classpath):
    manifest_entries = []
    classpath = compile_classpath.get_classpath_entries_for_targets(target.closure())
    for conf, classpath_entry in classpath:
      if conf == 'default' and  isinstance(classpath_entry, ArtifactClasspathEntry):
        manifest_entries.append(classpath_entry.coordinate)

    # write it out to the manifest to the workdir
    jar_manifest_path = os.path.join(target_workdir, 'META-INF', 'jar-manifest.txt')
    safe_mkdir(os.path.dirname(jar_manifest_path))
    with open(jar_manifest_path, "w") as jar_manifest:
      for entry in manifest_entries:
        jar_manifest.write("{}:{}:{}:{}:{}\n".format(
          entry.org, entry.name, entry.rev, entry.classifier, entry.ext))


