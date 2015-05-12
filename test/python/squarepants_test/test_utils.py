# Useful test methods

from contextlib import contextmanager
import shutil
from tempfile import mkdtemp

from squarepants.pom_utils import PomUtils
import squarepants.pom_handlers


@contextmanager
def temporary_dir():
  """Returns a temporary directory that gets cleaned up when the context manager exits."""
  tempdir = mkdtemp()
  try:
    yield tempdir
  finally:
    shutil.rmtree(tempdir)


def reset_caches():
  """Reset the internal caches in some of the libraries used for BUILD file generation."""
  PomUtils.reset_caches()
  squarepants.pom_handlers.reset_caches()
