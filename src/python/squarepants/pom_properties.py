#!/usr/bin/env python2.7
#
# Print properties from the pom.xml file as BASH variable settings.
# Note that the '.' characters in property names are re-written as '_'
#

import os
import re
import sys


from pom_handlers import DependencyInfo
from pom_utils import PomUtils


class PomProperties(object):

  def safe_property_name(self, property_name):
    """Replace characters that aren't safe for bash variables with an underscore"""
    return re.sub(r'\W', '_', property_name)


  def write_properties(self, pom_file_path, output_stream, rootdir=None):
    di = DependencyInfo(pom_file_path, rootdir)
    for property_name, value in di.properties.iteritems():
      output_stream.write('{0}="{1}"\n'.format(self.safe_property_name(property_name), value))

    # Print out some other things.  These are useful for script/pants_kochiku_build_wrapper
    output_stream.write('project_artifactId="{0}"\n'.format(di.artifactId))
    output_stream.write('project_groupId="{0}"\n'.format(di.groupId))


def usage():
  print "usage: {0} [args] ".format(sys.argv[0])
  print "Prints all the properties defined in a pom.xml in bash variable syntax."
  print ""
  print "-?,-h         Show this message"
  PomUtils.common_usage()
  sys.exit(1)


def main():
  arguments = PomUtils.parse_common_args(sys.argv[1:])
  flags = set(arg for arg in arguments if arg.startswith('-'))

  for f in flags:
    if f == '-h' or f == '-?':
      usage()
      return
    else:
      print ("Unknown flag {0}".format(f))
      usage()
      return

  path_args = list(set(arguments) - flags)
  if len(path_args) != 1 :
    print("Expected a single project path that contains a pom.xml file.")
    usage()

  pom_file_path = os.path.join(os.path.realpath(path_args[0]), 'pom.xml')

  if not os.path.exists(pom_file_path):
    print ("Couldn't find {0}".format(pom_file_path))
    usage()

  PomProperties().write_properties(pom_file_path, sys.stdout)


if __name__ == '__main__':
  main()
