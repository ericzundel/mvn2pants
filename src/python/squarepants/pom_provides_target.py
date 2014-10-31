#!/usr/bin/python
#
# Returns which pom.xml file provides a named artifactId
#
# usage: pom_provides_target <artifactId>
#

import logging
import sys
from optparse import OptionParser

from pom_utils import PomUtils


logger = logging.getLogger(__name__)


def main(args):
  """Searches all known modules for an artifactId
     of the module defined in sourceFile and prints them out as <groupId>.<artifactId>
  """

  usage = """usage: %prog [options]
  Searches all known modules for an artifactId or <groupId>.<artifactId>
  and prints out the name of pom.xml files that provide them

  e.g. %prog --target=com.squareup.service.exemplar
       %prog --artifactId=annotations
  """
  parser = OptionParser(usage=usage)
  parser.add_option("-a", "--artifactId", dest="artifactId",
                    help="<artifactId> from maven pom file")
  parser.add_option("-t", "--target", dest="target",
                    help="<groupId>.<artifactId> from maven pom file ")
  (options, args) = parser.parse_args(args)

  if not options.artifactId and not options.target:
    parser.print_help()
    PomUtils.common_usage()
    sys.exit(1)


  if options.artifactId:
    poms = PomUtils.pom_provides_target().find_artifact(options.artifactId)
  elif options.target:
    poms = PomUtils.pom_provides_target().find_target(options.target)

  if len(poms) == 0:
    logger.critical("*** No pom.xml file found")
    sys.exit(1)

  for pom in poms:
    print pom


if __name__ == "__main__":
  args = PomUtils.parse_common_args(sys.argv[1:])
  main(args)
