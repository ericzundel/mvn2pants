# General pants regression testing.

import os
import logging
import unittest2 as unittest
from contextlib import contextmanager
from zipfile import ZipFile

from squarepants.binary_utils import Command
from squarepants.file_utils import temporary_dir


class IntegrationTestBase(unittest.TestCase):
  """Base class for performing integration tests."""

  def setUp(self):
    logging.getLogger('squarepants').addHandler(logging.StreamHandler())
    env = os.environ.copy()
    env['REGENERATE_BUILD'] = 'no'
    self.pants = Command(name='./pants', args=['./pants', '--no-lock', '--print-exception-stacktrace'], env=env)
    self.java = Command(name='java')
    self.jar = Command(name='jar')
    self._original_wd = os.getcwd()

  def tearDown(self):
    os.chdir(self._original_wd)

  def assert_success(self, pants_run):
    self.assertTrue(pants_run)

  @contextmanager
  def invariant_file_contents(self, path):
    """Ensures that the contents of the file are unchanged after the contextmanager exits.

    Reads the file contents before yielding, then writes back the file contents after.
    :param string path: The path to the text file to keep invariant.
    """
    with open(path, 'r') as f:
      contents = f.read()
    try:
      yield contents
    finally:
      with open(path, 'w+') as f:
        f.write(contents)
