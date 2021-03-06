# coding=utf-8
# Copyright 2015 Square, Inc.

import glob
import logging
import os
import re
import shutil

from pants.task.task import Task
from pants.backend.jvm.targets.java_library import JavaLibrary

from squarepants.plugins.fingerprint.targets.fingerprint_target import FingerprintTarget

logger = logging.getLogger(__name__)


class InvalidateFingerpintDependees(Task):
  """Makes sure app-manifest.yaml and similar loose files don't get stale.

  This is accomplished by forcing zinc to fully recompile java_library targets with a direct
  dependency on a fingerprint that has been invalidated.
  """

  @classmethod
  def prepare(cls, options, round_manager):
    super(InvalidateFingerpintDependees, cls).prepare(options, round_manager)
    round_manager.require_data('java')

  @classmethod
  def product_types(cls):
    return ['compile_classpath']

  def execute(self):
    fingerprints = self.context.targets(lambda t: isinstance(t, FingerprintTarget))
    with self.invalidated(fingerprints,
                          invalidate_dependents=True) as invalidation_check:
      addresses = set()
      for vts in invalidation_check.invalid_vts:
        addresses.update(target.address for target in vts.targets)
      direct_dependees = set()
      for address in addresses:
        direct_dependees.update(self.context.build_graph.dependents_of(address))
      direct_dependees = map(self.context.build_graph.get_target, direct_dependees)
      direct_dependees = {target for target in direct_dependees if isinstance(target, JavaLibrary)}
      for target in direct_dependees:
        for valid_vts in invalidation_check.all_vts:
          for versioned_target in valid_vts.targets:
            if versioned_target.address == target.address:
              valid_vts.force_invalidate()
              break
        # HACK(gmalmquist): This uses a magic path to figure out where the zinc analysis output is.
        # Unfortunately, there is not a good way (that I can find) to find the incremental compile
        # analysis file generated by zinc. JvmCompile in open-source pants computes it based off the
        # vts.results_dir from the invalidate_check it does on its java_library inputs, but that
        # incorporates the fingerprint strategy used by JvmCompile to compute its path. The
        # fingerprint strategy used by JvmCompile generated by an instance method of JvmCompile,
        # which can be overridden by subclasses. So there's no way to get at it without accessing
        # the actual JvmCompile instance, and even then it's pretty hacky to be running an
        # invalidation check using another task's fingerprint strategy, because we'd have to be
        # careful not to accidentally change the validation status unintentionally (which could
        # cause pants to erroneously skip or do extra compilation).
        #
        # The long term solution for this is to modify JvmCompile or ZincCompile in open-source
        # pants to add a provision for clearing out the analysis for specific targets.

        # NB(zundel): there is actually a field `vts._is_incremental` that could potentially
        # be used to short-circuit the incremental compile, but it may actually be turned
        # on later after this task runs.

        # Paths the analysis files look like this as of 0.0.64
        # .pants.d/compile/zinc/squarepants.pants-aop-test-app.src.main.java.lib/52832f7bc075/squarepants.pants-aop-test-app.src.main.java.lib.analysis
        # .pants.d/compile/zinc/squarepants.pants-aop-test-app.src.main.java.lib/52832f7bc075/squarepants.pants-aop-test-app.src.main.java.lib.analysis.portable
        # HACK(zundel): We used to just remove the analysis file, but that now causes compiles to fail.  I don't know which directory is the right one, remove them all
        prefix = os.path.join(self.get_options().pants_workdir,
                              'compile', 'zinc', '*', target.id, '*')
        for sha_dir in glob.glob(prefix):
          dirname = os.path.basename(sha_dir)
          if re.match(r'^[0-9a-f]+$', dirname):
            if os.path.isdir(sha_dir):
              self.context.log.debug('Cleaning out {} to prevent stale app-manifest.yaml.'
                                     .format(sha_dir))
              # NB(zundel): if we remove the analysis file it just complains an stops
              shutil.rmtree(sha_dir)
              # NB(zundel): This doesn't work by default. It blows up on an empty analysis file,
              # BUT, there is an option to keep going we can turn on: --clear_invalid_analysis
              #safe_mkdir(sha_dir)
              #empty_analysis_file = os.path.join(sha_dir, "{}.analysis".format(target.id))
              #self.context.log.info("Touching {}".format(empty_analysis_file))
              #touch(empty_analysis_file)
