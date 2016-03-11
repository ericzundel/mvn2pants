# coding=utf-8
# Copyright 2015 Square, Inc.

from __future__ import print_function, with_statement

import logging
import os
import re

from pants.build_graph.resources import Resources
from pants.task.task import Task
from pants.backend.jvm.tasks.classpath_products import ClasspathProducts, ArtifactClasspathEntry
from pants.backend.jvm.tasks.ivy_task_mixin import IvyTaskMixin
from pants.base.exceptions import TaskError
from pants.build_graph.address import Address
from pants.java.distribution.distribution import DistributionLocator
from pants.java.executor import SubprocessExecutor
from pants.util.dirutil import safe_mkdir

from squarepants.plugins.link_resources_jars.targets.resources_jar import ResourcesJar


logger = logging.getLogger(__name__)


class LinkResourcesJars(IvyTaskMixin, Task):
  """Copies jar files specified by resources_jars targets to the resources product."""

  @classmethod
  def prepare(cls, options, round_manager):
    super(LinkResourcesJars, cls).prepare(options, round_manager)
    # round_manager.require_data('java')
    # round_manager.require_data('scala')

  @classmethod
  def product_types(cls):
    return ['compile_classpath']

  def resolve_jars(self, targets):
    """Resolve
    :param targets: targets that have dependencies to resolve
    :return: structure containing the path to resolved jars
    :rtype:  ClasspathProducts
    """
    executor = SubprocessExecutor(DistributionLocator.cached())
    classpath_products = self.context.products.get_data('classpath_products',
        init_func=ClasspathProducts.init_func(self.get_options().pants_workdir))
    self.resolve(executor=executor,
                 targets=targets,
                 classpath_products=classpath_products,
                 confs=['default'],
                 extra_args=())
    return classpath_products

  def _coordinate_to_path_pattern(self, coordinate):
    return re.compile(os.path.join(
      '^.*?',
      coordinate.org,
      coordinate.name,
      '[^/]+',
      '{name}-{rev}.{ext}$'.format(name=coordinate.name, rev=coordinate.rev, ext=coordinate.ext)
    ))

  def execute(self):

    def is_type(type_):
      return lambda target: isinstance(target, type_)

    def transitive_resource_jars(addresses):
      closure = set()
      self.context.build_graph.walk_transitive_dependency_graph(addresses, closure.add)
      return set(filter(is_type(ResourcesJar), closure))

    all_resources = self.context.targets(predicate=is_type(Resources))
    resources_to_resources_jars = {}
    for resources in all_resources:
      resources_to_resources_jars[resources] = transitive_resource_jars([resources.address])

    all_resources_jars = reduce(set.union, resources_to_resources_jars.values(), set())

    transitive_jars = reduce(set.union, (set(j.dependencies) for j in all_resources_jars), set())
    classpath_products = self.resolve_jars(transitive_jars)

    for resources, resources_jars in resources_to_resources_jars.items():
      if not resources_jars:
        continue
      resources_dir = os.path.join(self.workdir, resources.id)
      safe_mkdir(resources_dir, clean=True)
      sources = []
      for resources_jar in resources_jars:
        resources_classpath = classpath_products.get_for_target(resources_jar.library)
        jars = [jar for conf, jar in resources_classpath if conf == 'default']
        # NB(gmalmquist): It is insufficient to just pull the mapped jars out of the classpath,
        # because it may also include transitive jar dependencies of 3rdparty jars. The logic below
        # removes any jars that were not specified directly by the jar library, by comparing the
        # M2Coordinates of the direct dependencies with the mapped jar file paths.
        coordinates = {jar_dep.coordinate for jar_dep in resources_jar.library.jar_dependencies}
        direct_dependency_patterns = map(self._coordinate_to_path_pattern, coordinates)
        jars = [path for path in jars if any(p.match(path) for p in direct_dependency_patterns)]
        if len(jars) != 1:
          raise TaskError('Cannot map jar for {resources} because the library {library} does not '
                          'contain exactly one jar!{artifacts}'
                          .format(resources=resources.address.spec,
                                  library=resources_jar.library.address.spec,
                                  artifacts=''.join('\n  {}'.format(j) for j in jars)))
        destination = os.path.join(resources_dir, resources_jar.payload.dest)
        os.link(jars[0], destination)
        sources.append(resources_jar.payload.dest)
      synthetic_address = Address(resources_dir, 'resources-jars')
      self.context.build_graph.inject_synthetic_target(address=synthetic_address,
                                                       target_type=Resources,
                                                       derived_from=resources,
                                                       sources=sources)
      for dependee in self.context.build_graph.dependents_of(resources.address):
        self.context.build_graph.inject_dependency(dependee, synthetic_address)
