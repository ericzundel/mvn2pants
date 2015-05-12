#!/usr/bin/python
# Searches a module pom.xml file for dependencies <project><dependencies>

import logging
import sys

from pom_handlers import CachedDependencyInfos


logger = logging.getLogger(__name__)

def main():
  """Test driver that prints out dependencies.
     Run from ~/Development/java
  """
  source_file_name = "service/exemplar/pom.xml"
  df = CachedDependencyInfos.get(source_file_name)
  deps = df.dependencies
  print "dependencies of artifact {groupId}.{artifactId}".format(groupId=df.groupId,
                                                                 artifactId=df.artifactId)
  for dep in deps:
    print("  groupId.artifactId: {groupId}.{artifactId}".format(groupId=dep['groupId'],
                                                               artifactId=dep['artifactId']))

if __name__ == "__main__":
  PomUtils.parse_common_args(sys.args[1:])
  main()
