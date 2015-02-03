#!/usr/bin/python
# Utility to pull out dependencies from pom.xml and re-write them as pants references for
# BUILD file dependencies.  e.g. pants("3rdparty:...")
#

import logging
import os
import sys
import time

from pom_utils import PomUtils
from pom_handlers import PomContentHandler, DepsFromPom


logger = logging.getLogger(__name__)


# Test driver
def main(sourceFileName):
  start_ms = int(round(time.time() * 1000))
  pants_refs =  DepsFromPom(PomUtils.pom_provides_target()).get(sourceFileName)
  elapsed_ms = int(round(time.time() * 1000)) - start_ms
  for pants_ref in pants_refs:
    print("      %s" % (pants_ref))
  print
  print("Parsed %d pom.xml files in %dms." % (PomContentHandler.num_invocations(), elapsed_ms))


if __name__ == "__main__":
  pom = ""
  args = PomUtils.parse_common_args(sys.argv[1:])
  if len(args) == 1:
    pom = args[0]
  else:
    pom = "common/pom.xml"
    print "usage: {progname} path/to/pom.xml".format(progname=os.path.basename(sys.argv[0]))
    print
    PomUtils.common_usage()
    print
    print "Example with {pom}:".format(pom=pom)
  main(pom)

