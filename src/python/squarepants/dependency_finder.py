#!/usr/bin/python
# Searches a module pom.xml file for dependencies <project><dependencies>

import logging
import sys

from pom_handlers import DependencyFinder


logger = logging.getLogger(__name__)

def main():
  """Test driver that prints out dependencies.
     Run from ~/Development/java
  """
  sourceFileName = "service/exemplar/pom.xml"
  df = DependencyFinder()
  deps = df.find_dependencies(sourceFileName)
  print "dependencies of artifact %s.%s" % (df.groupId, df.artifactId)
  for dep in deps:
    print("  groupId:artfactId: %s:%s" %(dep['groupId'],dep['artifactId']))

if __name__ == "__main__":
  PomUtils.parse_common_args(sys.args[1:])
  main()
