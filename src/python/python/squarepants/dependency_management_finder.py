#!/usr/bin/python
#
# Looks through <dependencyManagement> tags and extracts dependencies
# Used to automatically pull in external dependencies defined in Maven into Pants' 3rdparty BUILD

import sys

from pom_utils import PomUtils


# Test driver
def main():
  """Test driver that spits out <dependencyManagement> contents.
     Run from ~/Development/java
  """

  deps = PomUtils.dependency_management_finder().find_dependencies("parents/base/pom.xml")
  for dependency in deps:
    print(dependency["groupId"] + "." + dependency["artifactId"] + "-" + dependency["version"])

if __name__ == "__main__":
  args = PomUtils.parse_common_args(sys.argv[1:])
  main()
