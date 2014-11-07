#!/usr/bin/env python

# Stores a fingerprint of the pants.pex file so that we can clean out the repo when it is updated.

from hashlib import sha1
import os
import sys
import logging

from pom_utils import PomUtils


# -------------------------------------------------
# GLOBAL CONFIGURATION VARIABLES
# -------------------------------------------------
_CACHE_DIRECTORY = './.pants.d/pom-gen/'
# -------------------------------------------------


logger = logging.getLogger(__name__)


def check_pex_health(baseroot, flags):
  """Check to see if pants.pex has been modified since the version stored in the branch. If so,
  then the workspace is cleaned up to remove old state and force BUILD files to be regenerated.

  :param string baseroot: directory at the root of the repo
  :param list<String> flags: flags passed on the command line
  """
  logger.info('Checking to see if pants.pex version has changed ...')
  pex_file = os.path.join(baseroot, 'squarepants', 'bin', 'pants.pex')
  if not os.path.exists(pex_file):
    error("No pants.pex file found; pants isn't installed properly in your repo.")
    sys.exit(1)
  hashes = set()
  with open(pex_file, 'rb') as pex:
    hashes.add(sha1(pex.read()).hexdigest())
  cached_hashes = os.path.join(baseroot, _CACHE_DIRECTORY, 'pex-hashes')
  if os.path.exists(cached_hashes):
    with open(cached_hashes, 'r') as f:
      if hashes == set(l.strip() for l in f.readlines() if l.strip()):
        return # Nothing changed.
    logger.info('Pants version has changed since last run. Cleaning .pants.d ...')
    result = os.system('{pex} goal clean-all'.format(pex=pex_file))
    if result:
      logger.error('pants goal clean-all failed with status {0}'.format(result))
      sys.exit(result)
  if not os.path.exists(os.path.dirname(cached_hashes)):
    os.makedirs(os.path.dirname(cached_hashes))
  with open(cached_hashes, 'w+b') as f:
    f.write('\n'.join(hashes))

def usage():
  print "usage: %s [args] " % sys.argv[0]
  print "Checks the pants.pex file to see if it has changed.  If so, runs a clean-all."
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
  check_pex_health(path, flags)


if __name__ == '__main__':
  main()
