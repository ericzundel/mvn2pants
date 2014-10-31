#!/usr/bin/python
# Used to add source_root() definitions for Pants.

from collections import defaultdict
import logging
import os.path

from pom_utils import *


logger = logging.getLogger(__name__)


class AllSourceRoots():
  """Finds all modules defined in the top level pom.xml file and looks for source directories beneath
     that are candidates to be added to Pants source_root() directives.
  """
  def __init__(self):
    self.sourceroots = defaultdict(list)

  def findRoots(self):
    for module in PomUtils.top_pom_content_handler().modules:
      self.addIfDir('java', os.path.join(module, "src/main/java"))
      self.addIfDir('javaTest', os.path.join(module, "src/test/java"))
      self.addIfDir('resources', os.path.join(module, "src/main/resources"))
      self.addIfDir('resources', os.path.join(module, "src/test/resources"))
      self.addIfDir('proto', os.path.join(module, "src/main/proto"))
      self.addIfDir('proto', os.path.join(module, "src/test/proto"))
      self.addIfDir('antlr', os.path.join(module, "src/main/antlr3"))
      self.addIfDir('antlr',os.path.join(module, "src/main/antlr4"))

  def addIfDir(self, key, path):
    if os.path.isdir(path):
      self.sourceroots[key].append(path)

def main():
  """Test driver that looks for source_roots contents.
     Run from ~/Development/java
  """
  roots = AllSourceRoots()
  roots.findRoots()
  for key in roots.sourceroots.keys():
    print ("sourceroots[{key}] = {value}".format(key=key, value=roots.sourceroots[key]))

if __name__ == "__main__":
  main()

