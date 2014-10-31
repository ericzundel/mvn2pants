#!/usr/bin/python
# Used to automatically pull in external dependencies defined in Maven into Pants' 3rdparty BUILD

import logging
import sys

from pom_utils import PomUtils


logger = logging.getLogger(__name__)


# Exclude targets handled already in 3rdparty/BUILD... It would be nice to be able to figure this out dynamically
_excludes = [
              #'com.google.guava.guava',
            ]
_loaded_artifacts = []
_loaded_names = []



class ThirdPartyBuildGenerator(object):
  _deps = PomUtils.dependency_management_finder().find_dependencies('parents/base/pom.xml')

  def __init__(self):
    pass

  def generate(self):
    buf = """class Exclude(object):
  def __init__(self, org, name=None):
    self.org = org
    self.name = name

global_excludes = []
def exclude_globally(org, name):
  global_excludes.append(Exclude(org, name))

class JarDependencyWithGlobalExcludes(jar):
  def __init__(self, org, name, rev = None, force = False, ext = None, url = None, apidocs = None,
               type_ = None, classifier = None):
    super(JarDependencyWithGlobalExcludes, self).__init__(org, name, rev, force, ext, url, apidocs,
        type_, classifier)
    self.excludes = [] + [e for e in global_excludes if not (e.org == org and e.name == name)]

sjar = JarDependencyWithGlobalExcludes

# Add your global exclusions below
exclude_globally(org = 'org.slf4j', name = 'log4j-over-slf4j')
# Prefer the square modified protobuf library to the stock google one.
# Apps that use Hadoop may require us to shade the square version so it can continue to use and older protobuf library
exclude_globally(org = 'com.google.protobuf', name = 'protobuf-java')
exclude_globally(org = 'org.eclipse.jetty.orbit', name = 'javax.servlet')
exclude_globally(org = 'org.mortbay.jetty', name = 'servlet-api-2.5')
exclude_globally(org = 'org.mortbay.jetty', name = 'servlet-api')
exclude_globally(org = 'javax.servlet', name = 'servlet-api')
exclude_globally(org = 'org.sonatype.sisu.inject', name = 'cglib')
exclude_globally(org = 'tomcat', name = 'jasper-compiler')
exclude_globally(org = 'tomcat', name = 'jasper-runtime')
exclude_globally(org = 'org.mortbay.jetty', name = 'jsp-2.1')
exclude_globally(org = 'org.glassfish.web', name = 'javax.el')
exclude_globally(org = 'hsqldb', name = 'hsqldb')
exclude_globally(org = 'org.jboss.netty', name = 'netty')
exclude_globally(org = 'com.fasterxml.jackson.datatype', name = 'jackson-datatype-joda')
exclude_globally(org = 'org.mockito', name = 'mockito-all')
exclude_globally(org = 'com.google.guava', name = 'guava')
exclude_globally(org = 'commons-logging', name = 'commons-logging')
exclude_globally(org = 'org.bouncycastle', name = 'bcprov-jdk15on')
"""

    for dep in ThirdPartyBuildGenerator._deps:
      artifact = "%s.%s" %(dep['groupId'] ,dep['artifactId'])
      if artifact in _excludes:
        logger.debug("skipping " + artifact)
        continue

      force_attribute = ""
      if artifact in _loaded_artifacts:
        # pants normally complains about 2 artifact names with different versions,
        # like com.squareup.okhttp.mockwebserver, but we sometimes use multiple versions.
        force_attribute = "force=True,"

      # Format a 'jar' type of dependency
      if not dep.has_key('type') or dep['type'] == 'jar':
        name = artifact
        if force_attribute:
          name += "-%s" % dep['version']

        url_attribute = "url='https://nexus.corp.squareup.com/content/groups/public/',"

        #if name in _loaded_names:
        #  name = artifact
        #  # Ugh, some of our dependencies have the same unqualified artifactId. Renaming the second one
        #  print "Duplicate artifactId: %s. Renaming to %s as a workaround." % (dep['artifactId'], artifact)
        jar_excludes = ""
        if dep.has_key('exclusions'):
          for jar_exclude in dep['exclusions']:
            jar_excludes += ".exclude(org='%s', name='%s')" % (jar_exclude['groupId'], jar_exclude['artifactId'])

        logger.debug("Adding {artifact} as {name}.".format(artifact=artifact, name=name))

        buf += """
jar_library(name='%s',
    jars=[
      sjar(org='%s',
           name='%s',
           rev='%s',%s
           %s).with_sources()%s,
    ],
)""" % (name, dep['groupId'], dep['artifactId'], dep['version'], force_attribute, url_attribute, jar_excludes)
        _loaded_names.append(name)
        _loaded_artifacts.append(artifact)

    return buf


def main():
  """Test driver that spits out <dependencyManagement> contents.
     Run from ~/Development/java
  """
  print(ThirdPartyBuildGenerator().generate())


if __name__ == "__main__":
  PomUtils.parse_common_args(sys.argv[1:])
  main()
