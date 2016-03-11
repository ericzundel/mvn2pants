#!/usr/bin/env python2.7
#
# This script makes it easy to do two things:
#
# 1. Automatically release a new version of pants to the java repo, including patching in our
#    custom patches.
#
# 2. Run pants in development mode along with those same patches (avoiding the need to manually
#    merge branches).
#
# This script only works if the pants development working directory is clean. It attempts to find
# that directory automatically (assuming it's named something like ~/src/pants), but you can also
# set the PANTS_SRC environment variable.
#
from __future__ import print_function, with_statement

import argparse
import logging
import os
import sys
from contextlib import contextmanager
from datetime import date
from textwrap import dedent

from binary_utils import BinaryUtils, Command, PantsGit


logger = logging.getLogger(__name__)


SQUARE_REMOTE = 'https://github.com/square/pants'
SQUARE_RELEASE_BRANCH = 'square/release'
SQUARE_RELEASE_FORMAT = 'square-%Y%m%d-01'
SQUARE_RELEASE_WIKI = 'https://wiki.corp.squareup.com/display/ATLS2/Pants+Release+Procedure'


# List of tuples in the form :
#   (patch_url, description of patch)
# or
#   (patch branch name, description of patch)
#
# These are applied in order, aborting if any patch fails to apply.
# TODO(gmalmquist) Maybe it would be good to load these in from a .json or something?
PANTS_PATCHES = [
]


class RunError(Exception):
  """Error running patchy pants."""


class PatchyPants(object):

  @classmethod
  def run_pants(cls, options, args, patches):
    """Run PANTS_DEV=1 ./pants with the given arguments, after applying the given list of patches.
    """
    git = PantsGit()
    with git.apply_patches(patches, commit=options.commit_patches):
      BinaryUtils.run_dev_pants(args)

  @classmethod
  def square_pants_run(cls, options, pants_args):
    """Runs pants in development mode with the global list of PANTS_PATCHES."""
    cls.run_pants(options, pants_args, PANTS_PATCHES)

  @classmethod
  def square_pants_release(cls, options, release_args):
    """Runs a pants release with the given arguments to the release script."""
    known_args = {'--no-push', '--overwrite', '--dirty'}

    unknown = [arg for arg in release_args if arg not in known_args]
    if unknown:
      logger.error('Got unknown arguments for --release: {}'.format(unknown))
      cls.usage()
      return

    releaser = Releaser(release_args, options.dirty)
    releaser.release()

  @classmethod
  def usage(cls):
    print(dedent('''
      Usage:
        {script} <arguments to pants>
        {script} --release [--no-push] [--overwrite] [--dirty]
    '''.format(script='pants_with_patches')))

  @classmethod
  def main(cls, args):
    logging.basicConfig(format='%(message)s')

    if not args:
      cls.usage()
      return

    executors = {
      'pants-run': cls.square_pants_run,
      'release': cls.square_pants_release,
    }

    parser = argparse.ArgumentParser('Apply patches to pants, for development runs or releases.')
    # Global options.
    parser.add_argument('--action', default='pants-run', choices=executors.keys(),
                        help=argparse.SUPPRESS) # Just used as storage.
    parser.add_argument('--release', dest='action', action='store_const', const='release',
                        help='Automatically patch and release pants to the java repo.')
    parser.add_argument('-l', '--log-level', default='info',
                        help='Set the log level.')
    parser.add_argument('--dirty', dest='dirty', action='store_true',
                        help='Use the current state of the pants repo instead of pulling.')
    parser.add_argument('--no-dirty', dest='dirty', action='store_false',
                        help='Update the pants repo to the latest version first.')
    parser.add_argument('--commit-patches', default=False, action='store_true',
                        help='Commit patches after applying them. This happens by default for a '
                             'release, but not when just running pants in development mode. In '
                             'development mode, the commits will be kept on '
                             'temp/temporary-patching-branch until the next time this command is '
                             'run.')
    parser.set_defaults(dirty=False)

    options, action_args = parser.parse_known_args(args)
    if action_args and args[-len(action_args):] != action_args:
      mixed_in = [a for a in args[-len(action_args):] if a not in action_args]
      logger.error('Error: arguments to --{} have to be last.'.format(options.action))
      if mixed_in:
        logger.error('  Options {} were mixed in with the '.format(mixed_in))
      logger.error('  args: {}'.format(action_args))
      return

    logging.getLogger().level = getattr(logging, options.log_level.upper(), logging.INFO)

    runner = executors.get(options.action)
    try:
      logger.info("Executing {}('{}')".format(runner.__name__, ' '.join(action_args)))
      runner(options, action_args)
    except RunError as rp:
      logger.critical('\n{}: {}\n'.format(type(rp).__name__, rp))
    except KeyboardInterrupt:
      logger.error('Aborted.')


class Releaser(object):
  """Automates most of the work of updating the version of pants in our java repo."""

  def __init__(self, release_script_args, use_dirty):
    self.release_script_args = release_script_args
    self.use_dirty = use_dirty

  def _get_java_dir(self):
    """Returns the current working directory if it is the java repo, otherwise raises an error."""
    java_dir = BinaryUtils.find_java_dir()
    if not java_dir:
      raise RunError('Not in java repo.')
    return java_dir

  def _assert_square_exists(self, git, try_add=True):
    """Checks to see if the 'square' remote repo exists.

     Raises an exception if it 'square' isn't present and can't be added.
     :param Git git: the pants repo git command.
     :param bool try_add: whether to attempt 'git remote add ...' automatically.
    """
    remotes = git.remotes()
    if 'square' not in remotes:
      if try_add:
        # Have to run with pipe=False to allow user to enter github credentials.
        if git('remote', 'add', 'square', SQUARE_REMOTE, pipe=False):
          self._assert_square_exists(git, try_add=False)
          return
      raise RunError('Square remote was not found. Please run:\n'
                     '  git remote add square {}'.format(SQUARE_REMOTE))

  def _get_upstream_remote(self, git):
    """Determines the name of the pants upstream repository.

    If present, prefer the repository 'upstream', otherwise, choose 'origin.

    :param git: the Git command object for the pants repo.
    """
    remotes = git.remotes()
    if 'upstream' in remotes:
      return 'upstream'
    if 'origin' in remotes:
      return 'origin'
    raise RunError('Could not find upstream or origin remotes.')

  @contextmanager
  def _setup_pants_repo(self):
    """Cleans the pants repo and applies patches, yielding the Git command for the repo."""
    git = PantsGit()

    if self.use_dirty:
      yield git
      raise StopIteration

    if not git.is_clean():
        raise RunError('Pants source not clean: please stash or commit changes in {}.'
                       .format(git.cwd))
    self._assert_square_exists(git)
    pants_upstream = self._get_upstream_remote(git)
    git('checkout', 'master')
    git('fetch', pants_upstream)
    git('reset', '--hard', '{}/master'.format(pants_upstream))
    git('clean', '-fdx')
    with git.apply_patches(PANTS_PATCHES, on_branch=SQUARE_RELEASE_BRANCH, commit=True):
      git('push', '-f', 'square')
      BinaryUtils.pause('Patches applied. It is recommended that you run either:"\n'
                        '  full CI:                 {cwd}/build-support/bin/ci.sh\n'
                        '  or just the unit tests:  cd {cwd} ; ./pants test tests/python/pants_test:all\n'
                        'before continuing.'.format(cwd=git.cwd))
      yield git

  def _run_release_script(self, java_dir):
    """Invokes pants_release.sh."""
    default_release_name=date.today().strftime(SQUARE_RELEASE_FORMAT)
    release_name = raw_input('Release name (default is {}): '.format(default_release_name))
    release_name = release_name.strip() or default_release_name
    releaser = Command(BinaryUtils.squarepants_binary('pants_release.sh'), cwd=java_dir)
    if not releaser(*(self.release_script_args+[release_name]), pipe=False):
      raise RunError('{} failed.'.format(releaser.name))
    return release_name

  def _test_exemplar(self, pants_git, java_dir, release_name):
    logger.info('\nTesting on exemplar:\n')
    env = os.environ.copy()
    env['SQPANTS_VERSION'] = release_name
    if 'PANTS_DEV' in env:
      env.pop('PANTS_DEV')
    env['PANTS_SRC'] = pants_git.cwd
    java_pants = Command('./pants', cwd=java_dir, env=env)
    success = True
    if not java_pants('binary', 'service/exemplar', pipe=False):
      BinaryUtils.pause('Building service/exemplar failed.')
      success = False
    elif not java_pants('test', 'service/exemplar', pipe=False):
      BinaryUtils.pause('Testing service/exemplar failed.')
      success = False
    return success

  def _print_closing_info(self, release_name):
    print('\nYou should edit squarepants/bin/pants_bootstrap.sh to update the version number ({}).\n'.format(release_name))
    print(dedent('''
      If you want to verify that things are working as expected in the java repo, you can run
      pants-check-compile job: squarepants/bin/check.sh compile | tee ~/check-compile.txt  #  takes on the order of 1.5 hours on Jenkins
      pants-check-test job: squarepants/bin/check.sh test | tee ~/check-test.txt   # takes on the order of 15 hours on Jenkins

      These are tracked at go/pants-success.

      Update squarepants/CHANGELOG.md

      Make a PR in square/java containing the change to pants_bootstrap.sh with the updated CHANGELOG.md to download and any other changes needed to update compatibility.
      In your commit message, record the sha of the square/stable branch you built pants.pex from similar to the following:
      Built from github square/pants commit fbcea7ec27fa8789df6919263fa3c638ca09ec26
      This should allow us to investigate bugs in the future.
    '''))

  def release(self):
    java_dir = self._get_java_dir() # Run this first to fail-fast if we're not in the java repo.
    print('\nAdapted from manual release procedure:\n{}\n'.format(SQUARE_RELEASE_WIKI))
    with self._setup_pants_repo() as pants_git:
      release_name = self._run_release_script(java_dir)
      BinaryUtils.pause('You should check to see if BUILD.tools or pants.ini need updating now.')
      self._test_exemplar(pants_git, java_dir, release_name)
      self._print_closing_info(release_name)


if __name__ == '__main__':
  PatchyPants.main(sys.argv[1:])
