#!/usr/bin/python
#
# This module contains XML parsing handlers and other helper classes.
# Many of these objects have factory constructors in PomUtils which
# will cache a singleton instance.
#

import logging
import os
import re
import xml.sax


logger = logging.getLogger(__name__)


class PomContentHandler(xml.sax.ContentHandler):
  """Base class for a simple sax parser to read a maven pom.xml file

    Tracks the current path as an array in self.path
    Tracks property defs in the array self.properties
  """

  invocations = 0

  def __init__(self):
    xml.sax.ContentHandler.__init__(self)
    # path of tags leading up to this element
    self.path = []
    # text content of the current node being parsed (can be retrieved in endElement)
    self.content = ""
    self.contentStack=[]

    self.properties = {}
    self.artifactId = ""
    self.groupId = ""
    # dict containing elements defined in <project><parent> element
    self.parent = {}


  def startElement(self, name, attrs):
    """invoke this at the beginning of subclass call to startElement()

    :param string name: name of the current element.
    :param list<string> attrs: xml attributes of the current element.
    """
    self.contentStack.append(self.content)
    self.content = ""
    self.path.append(name)

  def characters(self, content):
    """invoked with the element content as a string"""
    self.content += content.encode('ascii','ignore')

  def endElement(self, name):
    """invoke this at the end of subclass call to endElement()

    :param string name: name of the current element that is being closed.
    """

    if self.path == ["project", "groupId"]:
      self.groupId = self.content.strip()
    elif self.path == ["project", "artifactId"]:
      self.artifactId = self.content.strip()

    # Parse properties of the form: <project><properties><foo>fooValue</foo></properties></project>
    elif self.pathStartsWith(["project", "properties"]):
      self.properties[name] = self.content.strip()
    if self.pathStartsWith(["project", "parent"]):
      self.parent[name] = self.content.strip()
    self.path.pop(len(self.path) - 1)
    self.content = self.contentStack.pop()

  def endDocument(self):
    """invoked at the end of the XML document. """
    xml.sax.ContentHandler.endDocument(self)
    PomContentHandler.invocations += 1


  def pathStartsWith(self, path_prefix):
    """Convenience routine to see if the path to the current element matches the path passed.

    :param list path_prefix: prefix to compare to the current path.
    """
    if (len(self.path) >= len(path_prefix)) and self.path[0:len(path_prefix)] == path_prefix:
      return True
    return False

  def resolveProperties(self, str):
    """substitute ${foo} with known property value of foo

    :param string str: string to search for property patterns in.
    """
    while True:
      match = re.search(r"(\$\{[^}]*})", str)
      if not match:
        break
      property_name = match.group(0)[2:-1]
      if not self.properties.has_key(property_name):
        break
      str = str[:match.start(0)] + self.properties[property_name] + str[match.end(0):]
    return str

  def resolveDependencyProperties(self, raw_dependencies):
    deps = []

    # Resolve properties in the content
    for raw_dependency in raw_dependencies:
      dependency = {}
      for tag in raw_dependency.keys():
        if isinstance(raw_dependency[tag], basestring):
          dependency[tag] = self.resolveProperties(raw_dependency[tag])
        else:
          dependency[tag] = raw_dependency[tag]
      deps.append(dependency)
    return deps

  def properties(self):
    """returns a hash of known property name, value pairs"""
    return self.properties

  @staticmethod
  def num_invocations():
    """Static method used for performance analysis"""
    return PomContentHandler.invocations


class TopPomContentHandler(PomContentHandler):
  """SAX parser to read top level Maven pom.xml file.

      Just parses out the 'module' definitions.  Don't instantiate this yourself, use the
      cached factory method PomUtil.top_pom_content_handler().
  """
  def __init__(self):
    PomContentHandler.__init__(self)
    self.modules = []

  def endElement(self, name):
    if self.path == ["project", "modules", "module"]:
      self.modules.append(self.content.strip())

    PomContentHandler.endElement(self, name)

  def modules(self):
    return self.modules;


class _DMFPomContentHandler(PomContentHandler):
  """Dependency Management Finder Content Handler

  Used to parse <dependencyManagement> tags.
  """
  def __init__(self):
    PomContentHandler.__init__(self)
    # Array containing hash of { groupId => "", artifactId => "", version => "" exclusions => [exclusions]}
    self.dependency_management = []

    # Temporary storage for data parsed from sub-elements
    self._dependency = {}
    self._dependency_excludes = []
    self._dependency_exclude = {}

  def endElement(self, name):
    if self.pathStartsWith(["project", "dependencyManagement", "dependencies", "dependency", "exclusions", "exclusion"]):
      if len(self.path) == 7:
        self._dependency_exclude[self.path[-1]] = self.content.strip()
      elif (len(self.path) == 6):
        self._dependency_excludes.append(self._dependency_exclude)
        self._dependency_exclude = {}
    elif self.pathStartsWith(["project", "dependencyManagement", "dependencies", "dependency"]):
      # Parse 'dependencies' under the 'dependencyManagement' tag
      if len(self.path) == 5:
        self._dependency[self.path[-1]] = self.content.strip()
      elif len(self.path) == 4:
        # end of <dependency> definition. Save it.

        # override the 'exclusions' field with the array we built up
        self._dependency['exclusions'] = self._dependency_excludes
        self._dependency_excludes = []
        self.dependency_management.append(self._dependency)
        self._dependency = {}

    PomContentHandler.endElement(self, name)

  def dependencyManagement(self):
    return self.dependency_management


class _DFPomContentHandler(PomContentHandler):
  """Dependency Finder Content Handler

  Used to parse <dependency> tags.
  """

  def __init__(self):
    PomContentHandler.__init__(self)
    # Array containing hash of { groupId => "", artifactId => "", version => "" }
    self.dependencies = []
    self.dependency = {}
    self.dependency_excludes = []
    self.dependency_exclude = {}


  def endElement(self, name):

    # Add the parent pom as one of the dependencies
    if self.pathStartsWith(["project", "parent"]):
      if len(self.path) == 3:
        self.dependency[self.path[-1]] = self.content.strip()
      if len(self.path) == 2:
        self.dependencies.append(self.dependency)
        self.dependency = {}

    if self.pathStartsWith(["project", "dependencies", "dependency", "exclusions", "exclusion"]):
      if len(self.path) == 6:
        self.dependency_exclude[self.path[-1]] = self.content.strip()
      elif (len(self.path) == 5):
        self.dependency_excludes.append(self.dependency_exclude)
        self.dependency_exclude = {}
    elif self.pathStartsWith(["project",  "dependencies", "dependency"]):
      if len(self.path) == 4:
        # Parse members of '<dependency>'
        self.dependency[self.path[-1]] = self.content.strip()
      elif len(self.path) == 3:
        # end of <dependency> definition. Save it.

        # override the 'exclusions' field with the array we built up
        self.dependency['exclusions'] = self.dependency_excludes
        self.dependency_excludes = []
        self.dependencies.append(self.dependency)
        self.dependency = {}

    PomContentHandler.endElement(self, name)


class DependencyFinder():
  """Process a module pom.xml file looking for dependencies."""

  def __init__(self, rootdir=None):
    self.artifactId = ""
    self.groupId = ""
    self.properties = {}
    self._rootdir = rootdir

  def find_dependencies(self, source_file_name):
    """Process a pom.xml file
    :return: an array of dictionaries with contents of <project><dependencies><dependency> tags
    """
    pomHandler = _DFPomContentHandler()
    try:
      if self._rootdir:
        source_file_name = os.path.join(self._rootdir, source_file_name)
      with open(source_file_name) as source:
        xml.sax.parse(source, pomHandler)
    except IOError:
      # assume this file has been removed for a good reason and just continue normally
      return []

    self.artifactId = pomHandler.artifactId
    self.groupId = pomHandler.groupId
    self.properties = pomHandler.properties

    return pomHandler.resolveDependencyProperties(pomHandler.dependencies)


class DependencyManagementFinder():
  """ Searches a pom file for <dependencyManagement> tags.

  Do not instantiate.  Use the factory method PomUtils.dependency_managment_finder()
  """
  _cache = {}

  def __init__(self, rootdir=None):
    """:param string rootdir: root directory of the repo to analyze"""
    self._rootdir = rootdir

  def find_dependencies(self, source_file_name):
    """Process a pom.xml file containing the <dependencyManagement> tag.
       Returns an array of dictionaries containing the children of the <dependency> tag.
    """

    if source_file_name in DependencyManagementFinder._cache:
      return DependencyManagementFinder._cache[source_file_name]
    if self._rootdir:
      source_file_name = os.path.join(self._rootdir, source_file_name)
    pomHandler = _DMFPomContentHandler()
    with open(source_file_name) as source:
      xml.sax.parse(source, pomHandler)
    source.close()

    return pomHandler.resolveDependencyProperties(pomHandler.dependency_management)



class PomProvidesTarget():
  # indexed by <artifactId> mapped to a list of pom file names
  artifacts_in_modules = {}
  # indexed by <groupId>.<artifactId> mapped to a list of pom file names.
  targets_in_modules = {}

  def __init__(self, top_pom_content_handler):
    """Creates a singleton for the lookups so we don't parse the XML over and over (takes about 500ms)"""

    self._top_pom_content_handler = top_pom_content_handler
    if not PomProvidesTarget.artifacts_in_modules:
      self.init_artifacts_in_modules()

  def add_to_dict(self, dictionary, key, value):
    if not dictionary.has_key(key):
      dictionary[key] = []
    dictionary[key].append(value)

  def init_artifacts_in_modules(self):
    modules = self._top_pom_content_handler.modules
    logger.debug("modules are {modules}".format(modules=modules))
    for module in modules:
      finder = DependencyFinder()
      pom = module + "/pom.xml"
      finder.find_dependencies(pom)
      self.add_to_dict(PomProvidesTarget.artifacts_in_modules, finder.artifactId, pom)
      self.add_to_dict(PomProvidesTarget.targets_in_modules,
                       "%s.%s" % (finder.groupId, finder.artifactId), pom)

  def find_artifact(self, query):
    poms = []
    if PomProvidesTarget.artifacts_in_modules.has_key(query):
      poms = PomProvidesTarget.artifacts_in_modules[query]
    return poms

  def find_target(self, query):
    """looks for groupId.artifactId. There should be only one.
    :param string query: target name to find in the list of targets
    :return: list of pom.xml paths that contain the specified target name
    """
    poms = []
    if PomProvidesTarget.targets_in_modules.has_key(query):
      poms = PomProvidesTarget.targets_in_modules[query]
    return poms

  def targets(self):
    return PomProvidesTarget.targets_in_modules.keys()


class DepsFromPom():
  """ Given a module's pom.xml file, pull out the list of dependencies formatted for using a pants BUILD file"""

  def __init__(self, pom_provides_target, rootdir=None, exclude_project_targets=None):
    """:param string rootdir: root directory of the repo to analyze"""
    self.exclude_project_targets = exclude_project_targets or []
    self.target = ""
    self.artifact_id = ""
    self.group_id = ""
    self.properties = {}
    self._source_file_name = ""
    self._rootdir=rootdir
    self._pom_provides_target = pom_provides_target

  def get(self, source_file_name):
    """:param source_file_name: relative path of pom.xml file to analyze
    :return: tuple of (list of library deps, list of test refs)
    """
    df = DependencyFinder(rootdir=self._rootdir)
    deps = sorted(df.find_dependencies(source_file_name))
    self.target = "%s.%s" % (df.groupId, df.artifactId)
    self.group_id = df.groupId
    self.artifact_id = df.artifactId
    self.properties = df.properties

    self._source_file_name = source_file_name
    lib_deps, test_deps = [], []
    for dep in deps:
      if 'scope' in dep and dep['scope'] == 'test':
        test_deps.append(dep)
      else:
        lib_deps.append(dep)

    lib_pants_refs = self.build_pants_refs(lib_deps)
    test_pants_refs = self.build_pants_refs(test_deps)
    return lib_pants_refs, test_pants_refs

  def get_closest_match(self, project_root, target_prefix):
    """Looks for a target close to the one specified in the list of known targets.  If one maven
    project depends on another, there is usually a .../java:lib target, but not always.  This
    method substitutes in a .../proto:proto target if a .../java:lib does not exist.
    :param project_root: the project directory where the pom.xml for the project is found
    :param target_prefix: prefix of the target we're looking for.
    :return: a target that matches the highest precedent target for that project.
    """
    # When targets is empty, we assume we could not build the list and thus just don't do anything.
    target_prefix = os.path.join(project_root, target_prefix)
    targets = LocalTargets.get(project_root)

    # order is important in the list below. if java:lib exists, it will depend on the others.
    # proto:proto and wire_proto:wire_proto will depend on resources if they exist.
    for suffix in ['java:lib', 'proto:proto', 'wire_proto:wire_proto', 'resources:resources']:
      tmp = target_prefix + suffix
      if tmp in targets:
        return tmp
    return None

  def build_pants_refs(self, deps):
    from pom_utils import PomUtils
    pants_refs = []
    for dep in deps:
      dep_target = "%s.%s" % (dep['groupId'], dep['artifactId'])
      if PomUtils.is_local_dep(dep_target):
        # find the POM that contains this artifact
        poms = self._pom_provides_target.find_target(dep_target)
        if len(poms) > 0:
          project_root = os.path.dirname(poms[0])
        else:
          project_root = dep['artifactId']
        if project_root in self.exclude_project_targets:
          continue
        if dep.has_key('type') and dep['type'] == 'test-jar':
          target_prefix = 'src/test/'
        else:
          target_prefix = "src/main/"
        target_name = self.get_closest_match(project_root, target_prefix)
        if target_name:
          pants_refs.append("'{0}'".format(target_name))

    # Print 3rdparty dependencies after the local deps
    for dep in deps:
      dep_target = "%s.%s" % (dep['groupId'], dep['artifactId'])
      if PomUtils.is_third_party_dep(dep_target):
        logger.debug("dep_target %s is not local" % dep_target)
        pants_refs.append("'3rdparty:%s'" % (dep_target))

    # Print the external deps last
    for dep in deps:
      dep_target = "%s.%s" % (dep['groupId'], dep['artifactId'])
      if PomUtils.is_external_dep(dep_target):
        if not dep.has_key('version'):
          raise Exception("Expected artifact %s group %s in pom %s to have a version."
                          % (dep['artifactId'], dep['groupId'], self._source_file_name))
        url_attribute = "url='https://nexus.corp.squareup.com/content/groups/public/'"
        jar_excludes = ""
        if dep.has_key('exclusions'):
          for jar_exclude in dep['exclusions']:
            jar_excludes += ".exclude(org='%s', name='%s')" % (jar_exclude['groupId'], jar_exclude['artifactId'])

        pants_refs.append("""jar(org='%s', name='%s', rev='%s',%s)%s"""
                          % (dep['groupId'], dep['artifactId'], dep['version'], url_attribute, jar_excludes))

    return pants_refs

  def get_property(self, name):
    if self.properties.has_key(name):
      return self.properties[name]
    return ""


class LocalTargets:
  """A util class that looks at a maven project root and uses its structure to determine
    local dependencies.  Results are cached.
  """
  _cache = {}

  @staticmethod
  def get(project_root):
    """:param project_root: path to the root of the project where the pom.xml is located
    :return: a set of all targets based on the presence of directories."""
    types = {
      'src/main/java': ['lib'],
      'src/main/proto': ['proto'],
      'src/main/resources': ['resources'],
      'src/test/java': ['lib','test'],
      'src/test/proto' : ['proto'],
      'src/test/resources' : ['resources'],
      'src/main/wire_proto': ['wire_proto'],
      }
    if LocalTargets._cache.has_key(project_root):
      return LocalTargets._cache[project_root]

    result = set();
    result.add("%s:lib" % project_root)
    for path in types.keys():
      if os.path.isdir(os.path.join(project_root, path)):
        for target in types[path]:
          result.add("%s:%s" % (os.path.join(project_root, path), target))
    LocalTargets._cache[project_root] = result
    return result

