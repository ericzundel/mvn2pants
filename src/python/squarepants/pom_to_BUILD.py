#!/usr/bin/python
#
# Given a pom.xml file, turn it into a BUILD file.
#
# This script generates BUILD.gen files and BUILD.aux files.
# BUILD.gen files are generated where no BUILD file exists, filling the same purpose as a
#   handwritten BUILD file would.
# BUILD.aux files are generated /beside/ handwritten BUILD files. All their target names have the
#   'aux-' prefix to avoid collision. The purpose of these is to provide an easy way to maintain
#   dependencies in handwritten BUILD files, simply by referencing the generated dependency list in
#   the adjacent BUILD.aux file. This alleviates the amount of manual work that has to be done to
#   keep handwritten up to date with changin pom.xml's. All target types in BUILD.aux's are forced
#   to be dependencies(), resources(), or jar_library(), to prevent overlapping sources.
#   BUILD.aux files are excluded from the command line when invoking ./pants, but are still pulled
#   in when normal BUILD files reference them in their dependencies.
#

import logging
import os
import sys

from generation_context import GenerationContext
from build_component import BuildComponent
from pom_utils import PomUtils
from pom_file import PomFile


logger = logging.getLogger(__name__)


class PomConversionError(Exception):
  """Error while converting a pom file."""


class PomToBuild(object):

  def convert_pom(self, pom_file_name, rootdir=None, generation_context=None):
    """returns the contents of a BUILD file that corresponds to a module pom.xml file.
       pom_file_name - path to the pom.xml to convert
    """
    if not os.path.exists(pom_file_name) or not os.path.isfile(pom_file_name):
      raise IOError("Couldn't find plain pom.xml file at {0}".format(pom_file_name))

    if generation_context is None:
      generation_context = GenerationContext()

    try:
      pom_file = PomFile(pom_file_name, rootdir, generation_context)
    except Exception as e:
      raise PomConversionError('Failed to initialize PomFile for {}:\n{}'.format(pom_file_name, e))

    contents = ''
    for component in BuildComponent.TYPE_LIST:
      bc = component(pom_file, generation_context=generation_context)
      if bc.exists:
        try:
          gen_code = bc.generate()
        except Exception as e:
          raise PomConversionError('Failed to generate component {} for pom file {}.\n{}'
                                   .format(component.__name__, pom_file_name, e))
        if gen_code:
          contents += gen_code

    try:
      generation_context.write_build_file(pom_file.directory, contents)
    except Exception as e:
      raise PomConversionError('Failed to write generated build data for {}:\n{}'
                               .format(pom_file_name, e))


def main(poms):
  for pom_file_name in poms:
    PomToBuild().convert_pom(pom_file_name)

if __name__ == "__main__":
  args = PomUtils.parse_common_args(sys.argv[1:])
  poms = []
  if (len(args) > 0):
    main(args)
  else:
    print "usage: {0} path/to/pom.xml".format(os.path.basename(sys.argv[0]))
    PomUtils.common_usage()
    sys.exit(1)
