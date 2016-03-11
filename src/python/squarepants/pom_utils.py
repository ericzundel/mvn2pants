
import logging
import os
import xml.sax

from pom_handlers import *


logger = logging.getLogger(__name__)


class ArgParseError(Exception):
  pass


class PomUtils(object):
  """Utility class for parsing pom.xml files in the square/java repo.

     Keeps singletons for many of the handlers defined in pom_content_handlers.py.  Prefer
     using these factory methods for best performance.
  """
  _DEPENDENCY_MANAGMENT_FINDER = None
  _LOCAL_DEP_TARGETS = None
  _THIRD_PARTY_DEP_TARGETS = {}
  _TOP_POM_CONTENT_HANDLER = None
  _EXTERNAL_PROTOS_POM_CONTENT_HANDLER = None
  _POM_PROVIDES_TARGET = None

  @classmethod
  def reset_caches(cls):
    """Reset all the singleton instances. Useful for testing."""
    cls._DEPENDENCY_MANAGMENT_FINDER = None
    cls._LOCAL_DEP_TARGETS = None
    cls._THIRD_PARTY_DEP_TARGETS = {}
    cls._TOP_POM_CONTENT_HANDLER = None
    cls._EXTERNAL_PROTOS_POM_CONTENT_HANDLER = None
    cls._POM_PROVIDES_TARGET = None
    cls._ROOTDIR = None
    reset_caches()

  @classmethod
  def dependency_management_finder(cls, rootdir=None):
    """:returns: the singleton for DependencyManagementFinder so we only have to compute it once.
    :rtype: DependencyManagementFinder
    """
    if not cls._DEPENDENCY_MANAGMENT_FINDER:
      cls._DEPENDENCY_MANAGMENT_FINDER = DependencyManagementFinder(rootdir=rootdir)
    return cls._DEPENDENCY_MANAGMENT_FINDER

  @classmethod
  def pom_provides_target(cls, rootdir=None):
    """:returns: the singleton for PomProvidesTarget so we only have to compute it once.
    :rtype: PomProvidesTarget
    """
    if not cls._POM_PROVIDES_TARGET:
      cls._POM_PROVIDES_TARGET = PomProvidesTarget(cls.top_pom_content_handler(rootdir=rootdir))
    return cls._POM_PROVIDES_TARGET

  @classmethod
  def local_dep_targets(cls, rootdir=None):
    """:returns: a list of all of the target names that are provided by poms defined in this repo.
    :rtype: list of string
    """
    if not cls._LOCAL_DEP_TARGETS:
      cls._LOCAL_DEP_TARGETS = \
        sorted(cls.pom_provides_target(rootdir=rootdir).targets())
    return cls._LOCAL_DEP_TARGETS

  @classmethod
  def third_party_dep_targets(cls, rootdir=None):
    """:returns: the list of targets that will be defined in 3rdparty/BUILD.gen.
    :rtype: list of string
    """
    if not cls._THIRD_PARTY_DEP_TARGETS:
      dmf = cls.dependency_management_finder(rootdir=rootdir)
      deps = dmf.find_dependencies('parents/base/pom.xml')
      for dep in deps:
        target_name = '{groupId}.{artifactId}'.format(
          groupId=dep['groupId'],
          artifactId=dep['artifactId'],
        )
        cls._THIRD_PARTY_DEP_TARGETS[target_name] = dep['version']
    return cls._THIRD_PARTY_DEP_TARGETS

  @classmethod
  def top_pom_content_handler(cls, rootdir=None):
    """:returns: the singleton for the top level pom.xml parser so we only have to compute it once.
    :rtype: TopPomContentHandler
    """
    if not cls._TOP_POM_CONTENT_HANDLER:
      cls._TOP_POM_CONTENT_HANDLER = TopPomContentHandler()
      if rootdir:
        pathname = os.path.join(rootdir, "pom.xml")
      else:
        pathname = "pom.xml"
      xml.sax.parse(pathname, cls._TOP_POM_CONTENT_HANDLER)
    return cls._TOP_POM_CONTENT_HANDLER

  @classmethod
  def external_protos_content_handler(cls):
    """:returns: the singleton PomContentHandler for parents/external-protos/pom.xml
    :rtype: TopPomContentHandler
    """
    if not cls._EXTERNAL_PROTOS_POM_CONTENT_HANDLER:
      cls._EXTERNAL_PROTOS_POM_CONTENT_HANDLER = TopPomContentHandler()
      xml.sax.parse("parents/external-protos/pom.xml", cls._EXTERNAL_PROTOS_POM_CONTENT_HANDLER)
    return cls._EXTERNAL_PROTOS_POM_CONTENT_HANDLER

  @classmethod
  def get_modules(cls, rootdir=None):
    """:returns: the list of modules stored in the top pom.xml file
    :rttype: list of string"""
    return cls.top_pom_content_handler(rootdir=rootdir).modules

  @classmethod
  def common_usage(cls):
    """Print help for arguments parsed by parse_common_args()."""
    print "-l<level>  Turn on log level where <level> is one of DEBUG, INFO, WARNING, ERROR, CRITICAL"

  @classmethod
  def parse_common_args(cls, args):
    """Initializes logging and handles command line arguments shared between all tools in this package
    :returns: unprocessed arguments after processing known arguments
    :rtype: list of string
    """
    logging.basicConfig(format='%(asctime)s: %(message)s')
    logging.getLogger().setLevel(logging.INFO)
    unprocessed_args=[]
    for arg in args:
      if arg.startswith('-l'):
        level = arg[2:].upper()
        if hasattr(logging, level):
          logging.getLogger().setLevel(getattr(logging, level))
        else:
          raise ArgParseError(
            "There is no logging level named '{level}'. Try DEBUG, INFO, WARNING, ERROR, CRITICAL"
            .format(level=level))
      else:
        unprocessed_args.append(arg)
    return unprocessed_args

  @classmethod
  def is_local_dep(cls, target):
    """:return: True for targets that exist in the local repo.
    :rtype: bool
    """
    return target in cls.local_dep_targets()

  @classmethod
  def is_third_party_dep(cls, target, rootdir=None):
    """:return: True for targets that should be prefixed with "3rdparty"
    :rtype: bool
    """
    return target in cls.third_party_dep_targets(rootdir=rootdir)

  @classmethod
  def is_external_dep(cls, target, rootdir=None):
    """:return: True if this is an external dep that should be declared in a local jar_library target.
    :rtype: bool
    """
    return not (cls.is_local_dep(target) or cls.is_third_party_dep(target, rootdir))
