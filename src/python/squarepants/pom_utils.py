
import logging
import xml.sax

from pom_handlers import *


logger = logging.getLogger(__name__)


class ArgParseError(Exception):
  pass


class PomUtils(object):
  """Utility class for parsing pom.xml files in the square/java repo.

     PomUtils keeps singletons for many of the handlers defined in pom_content_handles.  Prefer
     using these factory methods for best performance.
  """
  _DEPENDENCY_MANAGMENT_FINDER = DependencyManagementFinder()
  _LOCAL_DEP_TARGETS = None
  _THIRD_PARTY_DEP_TARGETS = []
  _TOP_POM_CONTENT_HANDLER = None
  _POM_PROVIDES_TARGET = None

  @staticmethod
  def dependency_management_finder():
    return PomUtils._DEPENDENCY_MANAGMENT_FINDER

  @staticmethod
  def pom_provides_target():
    if not PomUtils._POM_PROVIDES_TARGET:
      PomUtils._POM_PROVIDES_TARGET = PomProvidesTarget(PomUtils.top_pom_content_handler())
    return PomUtils._POM_PROVIDES_TARGET

  @staticmethod
  def local_dep_targets():
    if not PomUtils._LOCAL_DEP_TARGETS:
      PomUtils._LOCAL_DEP_TARGETS = \
        sorted(PomUtils.pom_provides_target().targets())
    return PomUtils._LOCAL_DEP_TARGETS

  @staticmethod
  def third_party_dep_targets():
    if not PomUtils._THIRD_PARTY_DEP_TARGETS:
      deps = PomUtils.dependency_management_finder().find_dependencies("parents/base/pom.xml")
      for dep in deps:
        PomUtils._THIRD_PARTY_DEP_TARGETS.append("%s.%s" % (dep['groupId'], dep['artifactId']))
    return PomUtils._THIRD_PARTY_DEP_TARGETS

  @staticmethod
  def top_pom_content_handler():
    if not PomUtils._TOP_POM_CONTENT_HANDLER:
      PomUtils._TOP_POM_CONTENT_HANDLER = TopPomContentHandler()
      xml.sax.parse("pom.xml", PomUtils._TOP_POM_CONTENT_HANDLER)
    return PomUtils._TOP_POM_CONTENT_HANDLER

  @staticmethod
  def get_modules():
    """Get the list of modules stored in the top pom.xml file"""
    return PomUtils.top_pom_content_handler().modules

  @staticmethod
  def common_usage():
    """Print help for arguments parsed by parse_common_args()"""
    print "-l<level>  Turn on log level where <level> is one of DEBUG, INFO, WARNING, ERROR, CRITICAL"

  @staticmethod
  def parse_common_args(args):
    """Initializes logging and handles command line arguments shared between all tools in this package
    :returns: list of unprocessed arguments
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

  @staticmethod
  def is_local_dep(target):
    """:return: True for targets that exist in the local repo"""
    return target in PomUtils.local_dep_targets()

  @staticmethod
  def is_third_party_dep(target):
    """:return: True for targets that should be prefixed with "3rdparty" """
    return target in PomUtils.third_party_dep_targets()

  @staticmethod
  def is_external_dep(target):
    return not (PomUtils.is_local_dep(target) or PomUtils.is_third_party_dep(target))
