#!/usr/bin/python
# Used to generate source_root() calls

import logging
import os
import sys

from pom_utils import PomUtils


logger = logging.getLogger(__name__)


class RootBuildGenerator(object):

  def __init__(self):
    pass

  def generate(self):
    modules = PomUtils.get_modules()


    contents = "# Automatically generated by {0}\n\n".format(os.path.basename(sys.argv[0]))
    for module in modules:
      contents += "square_maven_layout('{0}')\n".format(module)

    return contents


def main():
  print RootBuildGenerator().generate()

if __name__ == "__main__":
  main()
