import os
import shutil
from contextlib import contextmanager
from tempfile import mkdtemp, mktemp


@contextmanager
def temporary_dir():
  """Returns a temporary directory that gets cleaned up when the context manager exits."""
  tempdir = mkdtemp()
  try:
    yield tempdir
  finally:
    shutil.rmtree(tempdir)


@contextmanager
def temporary_file():
  """Returns a temporary file that gets cleaned up when the context manager exits."""
  tempfile = mktemp()
  try:
    yield tempfile
  finally:
    os.remove(tempfile)


@contextmanager
def frozen_dir(path):
  """Ensures that the contents of the directory are the same after exiting as before entering."""
  with temporary_dir() as tempdir:
    backup = os.path.join(tempdir, 'backup')
    shutil.copytree(path, backup)
    try:
      yield path
    finally:
      shutil.rmtree(path, ignore_errors=True)
      shutil.move(backup, path)


def file_pattern_exists_in_subdir(subdir, pattern):
  """Search for a file pattern recursively in a subdirectory

  :param subdir: directory to search recursively
  :param re.RegexObject pattern: compiled regular expression object from re.compile()
  :return: True if a file with the named pattern exists in the subdirectory
  :rtype: bool
  """

  for (dirpath, dirnames, filenames) in os.walk(subdir):
    for filename in filenames:
      if pattern.match(filename):
        return True

  return False


def touch(fname, times=None, makedirs=False):
  """Creates the specified file at the named path (and optionally sets the time)."""
  if makedirs:
    directory = os.path.dirname(fname)
    if not os.path.exists(directory):
      os.makedirs(directory)
  with open(fname, 'a'):
    os.utime(fname, times)
