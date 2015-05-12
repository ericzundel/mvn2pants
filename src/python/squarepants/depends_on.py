#!/usr/bin/python
#
# Shows projects a target depends on (transitively) going through definitions defined  and referenced in the top level repo.
# invoke from ~/Development/java
#
# usage: depends_on.py path/to/pom.xml
#

import logging
import os
import os.path
import sys

from pom_utils import PomUtils
from pom_handlers import CachedDependencyInfos

logger = logging.getLogger(__name__)

def recursive_find_deps(query, dependency_edges, results):
  """ query - the name of the target to find
      dependency_edges - the dictionary of all dependencies found
      results - set() containing the result set.
  """
  logger.debug("looking for {query} in graph" .format(query=query))
  if query in results:
    # avoid following the same dep twice
    return
  results.add(query)
  if not dependency_edges.has_key(query):
    return
  deps = dependency_edges[query]
  for dep in deps:
    recursive_find_deps(dep, dependency_edges, results)

def build_dependency_graph():
  dependency_edges = {}
  for module in PomUtils.top_pom_content_handler().modules:
    logger.debug("found module: " + module)
    finder = CachedDependencyInfos.get(module + "/pom.xml")
    deps = finder.dependencies
    target = "{group_id}.{artifact_id}".format(group_id=finder.groupId,
                                               artifact_id=finder.artifactId)
    logger.debug("Adding dependencies for {target}".format(target=target))
    dependency_edges[target] = []
    for dep in deps:
      dep_target = "{group_id}.{artifact_id}".format(group_id=dep['groupId'],
                                                     artifact_id=dep['artifactId'])
      logger.debug("{target} => {dep_target}".format(target=target, dep_target=dep_target))
      dependency_edges[target].append(dep_target)
  return dependency_edges

def main(sourceFile):
  """Builds a dependency graph,  searches the graph for all transitive dependencies
     of the module defined in sourceFile and prints them out as <groupId>.<artifactId>
  """
  # Fetch the group/artifact for the source file
  finder = DependencyInfo(sourceFile)
  query =  "{group_id}.{artifact_id}".format(group_id=finder.groupId,
                                             artifact_id=finder.artifactId)
  logger.debug("Looking for all dependencies of: {query}".format(query=query))

  dependency_edges = build_dependency_graph()

  results = set()
  recursive_find_deps(query, dependency_edges, results)
  logger.debug("Found {num_results} results.".format(num_results=len(results)))
  sorted_results = sorted(results)

  # Sort the output with local deps first
  for dep_target in sorted_results:
    if PomUtils.is_local_dep(dep_target):
      print dep_target
  for dep_target in sorted_results:
    if not PomUtils.is_local_dep(dep_target):
      print dep_target

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
