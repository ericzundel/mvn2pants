# coding=utf-8
# Copyright 2015 Pants project contributors (see CONTRIBUTORS.md).
# Licensed under the Apache License, Version 2.0 (see LICENSE).

import getpass
import logging
import os
import pwd
from datetime import datetime

from pants.base.build_environment import get_buildroot
from pants.scm.git import Git
from pants.util.osutil import get_os_name, normalize_os_name


logger = logging.getLogger(__file__)


class BuildSymbols(object):
  """Stores symbols that BUILD files need to access.

  This plugin is a temporary mechanism to populate BUILD files with dynamic information, until a
  generally accepted convention is established for this sort of thing in Pants proper.
  """

  __architectures = {
    'darwin': 'Darwin-i386',
    'linux': 'Linux-x86_64',
  }

  __module_file = 'modules.txt'
  __build_timestamp = None
  __modules = None

  def __init__(self, parse_context):
    self.parse_context = parse_context

  @property
  def arch(self):
    name = normalize_os_name(get_os_name())
    return self.__architectures.get(name, 'unknown')

  @property
  def directory(self):
    return self.parse_context.rel_path

  @property
  def module_directory(self):
    modules = self.get_modules()
    path = self.directory
    while path and path not in modules:
      path = os.path.dirname(path)
    if not path: return ''
    return os.path.abspath(path)

  @property
  def module_uri(self):
    return 'file://{}'.format(os.path.realpath(self.module_directory))

  @property
  def module_target_directory(self):
    return os.path.join(self.module_directory, 'target')

  @property
  def build_timestamp(self):
    if self.__build_timestamp is None:
      self.__build_timestamp = datetime.now().strftime("%Y-%m-%d'T'%H:%M:%S'Z'")
    return self.__build_timestamp

  @property
  def user_name(self):
    return getpass.getuser()

  @property
  def build_root(self):
    return get_buildroot()

  def get_modules(self):
    if self.__modules is None:
      self.__modules = set()
      with open(self.__module_file, 'r') as f:
        for line in f:
          if '#' in line:
            line, _ = line.split('#', 1)
          line = line.strip()
          if line:
            self.__modules.add(line)
    return self.__modules

  def __call__(self):
    pass
