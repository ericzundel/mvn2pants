# coding=utf-8

import logging


from pants.backend.jvm.targets.exclude import Exclude
from pants.backend.jvm.targets.jar_dependency import JarDependency
from pants.option.config import Config

_YAML_FILENAME = "pants.yaml"

logger = logging.getLogger(__file__)


def _load_excludes_from_config():
  excludes=[]
  for exclude in Config.load().get('sjar', 'excludes', type_=list, default=[]):
    excludes.append(Exclude(org=exclude['org'], name=exclude['name']))
  return excludes


class JarDependencyWithGlobalExcludes(JarDependency):
  """Automatically append all 'excludes' defined in pants.yaml to a JarDependency target.

  This target is aliased to 'sjar' in register.py.  Use it anywhere you would normally use
  a 'jar()' target to pull in an artifact compiled externally to the repo (e.g. in nexus).

  The global excludes can be configured in two ways:

  1) Include the org and name of the jar to exclude in section in pants.ini:

  # [sjar]
  # excludes: [
  #   { "org" : "org.json",
  #     "name" : "json"
  #   },
  #   ...
  # ]

  2) Invoke sjar_exclude_globally() in a top level BUILD file:

  sjar_exclude_globally(org="org.json", name="json")

  The name 'sjar' is historical for a similar implementation defined privately inside of other
  users' repo. If you mention the term 'sjar' on the Pants mailing list, many existing users
  will know the concept.
  """

  global_excludes = _load_excludes_from_config()
  loaded = False

  def __init__(self, org, name, rev = None, force = False, ext = None, url = None, apidocs = None,
      type_ = None, classifier = None, excludes = None):
    super(JarDependencyWithGlobalExcludes, self).__init__(org, name, rev, force, ext, url, apidocs,
                                                          type_, classifier, excludes=excludes)

    # NB(zundel) Below, note that self.excludes is usually [] and the list of global excludes is a
    # fixed list currently ~25 items in pants.ini
    self.excludes = list(self.excludes) + [e for e in self.global_excludes
                      if not (e.org == org and e.name == name)]

  @classmethod
  def sjar_exclude_globally(cls, org, name):
    """Add a single exclude to the list of global excludes"""
    cls.global_excludes.append(Exclude(org, name))

