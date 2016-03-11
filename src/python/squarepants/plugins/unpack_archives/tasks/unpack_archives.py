# coding=utf-8
# Copyright 2016 Square, Inc.

from __future__ import print_function, with_statement

import logging
import os
import shutil
from subprocess import Popen, PIPE

from pants.backend.jvm.jar_dependency_utils import M2Coordinate
from pants.backend.jvm.ivy_utils import IvyUtils, IvyInfo, IvyModuleRef
from pants.backend.jvm.tasks.ivy_task_mixin import IvyTaskMixin
from pants.backend.jvm.tasks.unpack_jars import UnpackJars
from pants.backend.jvm.targets.jar_library import JarLibrary
from pants.base.exceptions import TaskError
from pants.util.dirutil import safe_mkdir, safe_mkdtemp
from pants.fs.archive import ZIP
from pants.backend.jvm.tasks.classpath_products import ClasspathProducts
from pants.ivy.ivy_subsystem import IvySubsystem

from squarepants.plugins.unpack_archives.targets.unpacked_archives import UnpackedArchives


logger = logging.getLogger(__name__)


class UnpackArchives(IvyTaskMixin, UnpackJars):
  """Downloads and extracts archives for unpacked_archives() targets.

  This has two key features that distinguish it from UnpackJars:
    1. It works on tarballs (in addition to jars and zips).
    2. It extracts the files to a directory specified by the unpacked_archives() target, instead of
       to a hidden location inside .pants.d.
  """

  class TarExtractionError(TaskError):
    """Error running the tar extraction subprocess."""

  @classmethod
  def prepare(cls, options, round_manager):
    super(UnpackArchives, cls).prepare(options, round_manager)
    round_manager.require_data('compile_classpath')

  @classmethod
  def product_types(cls):
    # NB(gmalmquist): This is just here to override the products from the superclass.
    return []

  @classmethod
  def global_subsystems(cls):
    return super(IvyTaskMixin, cls).global_subsystems() + (IvySubsystem,)

  def _filtered_copy(self, src_dir, dst_dir, filter_func=None):
    copied_count = 0
    filter_func = filter_func or (lambda _: True)
    for (root, dirnames, filenames) in os.walk(src_dir):
      for name in filenames:
        src_path = os.path.join(root, name)
        rel_path = os.path.relpath(src_path, src_dir)
        if not filter_func(rel_path):
          continue
        dst_path = os.path.join(dst_dir, rel_path)
        safe_mkdir(os.path.dirname(dst_path))
        shutil.copyfile(src_path, dst_path)
        copied_count += 1
    return copied_count

  def _extract_tar(self, tar_path, unpack_dir, filter_func=None):
    temp_unpack_dir = safe_mkdtemp()
    with self.context.new_workunit(name='tar-extract'):
      p = Popen(['tar', 'xzf', tar_path, '-C', temp_unpack_dir], stdout=PIPE, stderr=PIPE)
      out, err = p.communicate()
      if p.returncode != 0:
        raise self.TarExtractionError('Error unpacking tar file "{}" (code={}).\nStderr: {}'
                                      .format(tar_path, p.returncode, err))
    with self.context.new_workunit(name='filtered-copy'):
      copied = self._filtered_copy(temp_unpack_dir, unpack_dir, filter_func=filter_func)
      self.context.log.info('Copied {} extracted files.'.format(copied))

  def _unpack(self, unpacked_archives):
    """Extracts files from the downloaded jar files and places them in a work directory.

    :param UnpackedArchives unpacked_archives: target referencing jar_libraries to unpack.
    """
    self.context.log.info('Unpacking {}'.format(unpacked_archives.address.spec))
    unpack_dir = unpacked_archives.destination
    safe_mkdir(unpack_dir, clean=True)

    unpack_filter = self.get_unpack_filter(unpacked_archives)
    classpath_products =  ClasspathProducts(self.get_options().pants_workdir)
    resolve_hashes = self.resolve(None, unpacked_archives.dependencies, classpath_products)
    ivy_cache_dir = os.path.expanduser(IvySubsystem.global_instance().get_options().cache_dir)

    def to_m2(jar):
      return M2Coordinate(org=jar.org, name=jar.name, rev=jar.rev, classifier=jar.classifier,
                          ext=jar.ext)

    libraries = self.context.build_graph.transitive_subgraph_of_addresses([unpacked_archives.address])
    libraries = [t for t in libraries if isinstance(t, JarLibrary)]
    coords = set()
    for library in libraries:
      coords.update(to_m2(jar) for jar in library.payload.jars)

    for resolve_hash in resolve_hashes:
      path = IvyUtils.xml_report_path(ivy_cache_dir, resolve_hash, 'default')
      info = IvyUtils.parse_xml_report('default', path)
      refs_for_libraries = set()
      for ref in info.modules_by_ref.keys():
        if to_m2(ref) in coords:
          refs_for_libraries.add(ref)

      memo = {}
      for ref in tuple(refs_for_libraries):
        info.traverse_dependency_graph(ref, refs_for_libraries.add, memo)

      for ref in sorted(refs_for_libraries):
        module = info.modules_by_ref[ref]
        artifact_path = module.artifact
        self.context.log.debug('Extracting {} to {}.'.format(to_m2(ref), unpack_dir))
        if artifact_path.endswith('.zip') or artifact_path.endswith('.jar'):
          ZIP.extract(artifact_path, unpack_dir, filter_func=unpack_filter)
        else:
          self._extract_tar(artifact_path, unpack_dir, filter_func=unpack_filter)

  def execute(self):
    addresses = [target.address for target in self.context.targets()]
    closure = self.context.build_graph.transitive_subgraph_of_addresses(addresses)
    for target in closure:
      if isinstance(target, UnpackedArchives):
        self._unpack(target)
