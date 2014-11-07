#!/usr/bin/env python
#
# Unconditionally recreates the generated BUILD.gen and BUILD.aux files
#

import logging
import os
import sys
import time

from pom_utils import PomUtils
from pom_to_BUILD import PomToBuild
from generate_3rdparty import ThirdPartyBuildGenerator
from generate_root_BUILD import RootBuildGenerator

logger = logging.getLogger(__name__)


class Task(object):
  """Basically a souped-up lambda function which times itself running."""

  class Error(Exception):
    pass

  def __init__(self, name=None, run=None):
    self._run = run or (lambda: None)
    self.name = name or 'Unnamed Task'
    self._time_taken = -1

  def run(self):
    return self._run()

  @property
  def duration(self):
    if self._time_taken < 0:
      raise self.Error('Time cannot be queried before task is run.')
    return self._time_taken

  def __call__(self):
    logger.debug('Starting %s.' % self.name)
    start = time.time()
    value = self.run()
    end = time.time()
    self._time_taken = end - start
    logger.debug('Done with %s (took %0.03f seconds).' % (self.name, self.duration))
    return value


class RegenerateAll(object):
  def __init__(self, path, flags):
    self.baseroot = path
    self.flags = flags

  def _clean_generated_builds(self):
    """Removes all generated BUILD files from the source diretory"""
    logger.info('Removing old generated BUILD.gen and BUILD.aux files')
    os.system(
      "find {root} \( -path '*/.pants.d/*' -prune -path '*/target/*' -prune \) "
      " -o \( -name BUILD.gen -o -name BUILD.aux \) | xargs rm -f"
      .format(root=self.baseroot))

  def _convert_poms(self):
    poms = [x + '/pom.xml' for x in PomUtils.get_modules()]
    logger.info('Re-generating {count} modules'.format(count=len(poms)))
    # Convert pom files to BUILD files
    for pom_file_name in poms:
      PomToBuild().convertPom(pom_file_name, rootdir=self.baseroot)

  def _regenerate_3rdparty(self):
    logger.info('Re-generating 3rdparty/BUILD.gen')
    with open('3rdparty/BUILD.gen', 'w') as build_file:
      build_file.write(ThirdPartyBuildGenerator().generate())

  def _regenerate_root(self):
    logger.info('Re-generating BUILD.gen')
    with open('BUILD.gen', 'w') as build_file:
      build_file.write(RootBuildGenerator().generate())

  def execute(self):
    Task('clean_build_gen', self._clean_generated_builds)()
    Task('convert_poms', self._convert_poms)()
    Task('regenerate_3rdparty', self._regenerate_3rdparty)()
    Task('regenerate_root', self._regenerate_root)()

def usage():
  print "usage: %s [args] " % sys.argv[0]
  print "Regenerates the BUILD.* files for the repo"
  print ""
  print "-?,-h         Show this message"
  PomUtils.common_usage()

def main():
  arguments = PomUtils.parse_common_args(sys.argv[1:])
  flags = set(arg for arg in arguments if arg.startswith('-'))
  paths = list(set(arguments) - flags)
  paths = paths or [os.getcwd()]
  if len(paths) > 1:
    logger.error('Multiple repo root paths not supported.')
    return

  path = os.path.realpath(paths[0])

  for f in flags:
    if f == '-h' or f == '-?':
      usage()
      return
    else:
      print ("Unknown flag %s" % f)
      usage()
      return
  main_run = Task('main', lambda: RegenerateAll(path, flags).execute())
  main_run()
  logger.info('Finish checking BUILD.* health in %0.3f seconds.' % main_run.duration)


if __name__ == '__main__':
  main()
