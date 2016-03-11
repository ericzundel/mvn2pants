# coding=utf-8


from pants.backend.jvm.targets.exclude import Exclude
from pants.backend.jvm.targets.jar_dependency import JarDependency
from pants.option.custom_types import list_option
from pants.subsystem.subsystem import Subsystem
from pants.task.task import Task


class SJar(Subsystem):
  options_scope = 'sjar'
  _excludes = None

  @classmethod
  def register_options(cls, register):
    super(SJar, cls).register_options(register)
    register('--excludes', advanced=True, type=list_option, default=[], fingerprint=True,
             help='Specifies the org and name of the jars to exclude from all sjar() entries\n'
                  '[ { "org": "<org>", "name": "<name>"}, ... ]')

  @classmethod
  def get_excludes(cls):
    if cls._excludes == None:
      excludes = []
      for exclude in cls.global_instance().get_options().excludes:
        excludes.append(Exclude(org=exclude['org'], name=exclude['name']))
      cls._excludes = excludes
    return cls._excludes


class SJarTask(Task):
  """A task used soley as a vehicle to register the SJar subsystem.

  See https://github.com/pantsbuild/pants/issues/2858
  """
  @classmethod
  def global_subsystems(cls):
    return super(SJarTask, cls).global_subsystems() + (SJar,)

  def execute(self):
    pass


class JarDependencyWithGlobalExcludes(JarDependency):
  """Automatically append all 'excludes' defined in pants.ini to a JarDependency target.

  This target is aliased to 'sjar' in register.py.  Use it anywhere you would normally use
  a 'jar()' target to pull in an artifact compiled externally to the repo (e.g. in nexus).

  Include the org and name of the jar to exclude in section in pants.ini:

  [sjar]
  excludes: [
    { "org" : "org.json",
      "name" : "json"
    },
    ...
  ]

  The name 'sjar' is historical for a similar implementation defined privately inside of other
  users' repo. If you mention the term 'sjar' on the Pants mailing list, many existing users
  will know the concept.
  """

  @classmethod
  def _calc_excludes(cls, org, name, excludes):
    # NB(zundel) Below, note that self.excludes is usually [] and the list of global excludes is a
    # fixed list currently ~25 items in pants.ini
    excludes = list(excludes or ())
    excludes.extend(e for e in SJar.get_excludes() if not (e.org == org and e.name == name))
    return excludes

  def __new__(cls, org, name, rev=None, force=False, ext=None, url=None, apidocs=None,
               classifier=None, mutable=None, intransitive=False, excludes=None):
    return JarDependency(
      org, name, rev=rev, force=force, ext=ext, url=url, apidocs=apidocs,
      classifier=classifier, mutable=mutable, intransitive=intransitive,
      excludes=cls._calc_excludes(org, name, excludes),
    )
