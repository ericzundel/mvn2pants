from __future__ import print_function, with_statement

import logging
import os
from contextlib import contextmanager
from file_utils import temporary_file
from subprocess import Popen, PIPE
from urllib2 import urlopen


logger = logging.getLogger(__name__)


class CommandError(Exception):
  """Problem executing or initializing a binary command."""


class GitError(CommandError):
  """Problem invoking git."""


class BinaryUtils(object):

  @classmethod
  def download(cls, url, destination):
    """Downloads a file.

    :param str url: url to download.
    :param str destination: destination file.
    """
    try:
      if os.path.exists(destination):
        os.remove(destination)
      response = urlopen(url)
      with open(destination, 'w+') as output:
        output.write(response.read())
      return os.path.exists(destination)
    except Exception as e:
      logger.debug('Failed to download {} to {} ({}).'.format(url, destination, e))
      return False

  @classmethod
  def pause(cls, message):
    """Prints out the message, waiting for user input to continue."""
    return raw_input('\n{}\nPress Return to continue, Ctrl+C to abort.'.format(message))

  @classmethod
  def run_dev_pants(cls, args, cwd=None):
    """Run PANTS_DEV=1 ./pants with the given arguments.

    :param list args: list of arguments to ./pants.
    :param str cwd: path to the repo directory (where ./pants lives);
      defaults to the Java repo.
    """
    cwd = cwd or BinaryUtils.find_java_dir()
    args = [os.path.join(cwd, 'pants')] + [str(a) for a in args]
    try:
      logger.info('PANTS_DEV=1 {}'.format(' '.join(args)))
      env = os.environ.copy()
      env['PANTS_DEV'] = '1'
      p = Popen(args, env=env, cwd=cwd)
      p.wait()
      return p.returncode
    except Exception as e:
      logger.warning('Could not run pants: {}'.format(e))
      return False

  @classmethod
  def squarepants_binary(self, name, java_repo=None):
    """Returns the path to a binary in squarepants/bin.

    :param str name: name of the binary.
    :param str java_repo: path to the java repo directory, if not the cwd.
    """
    java_repo = java_repo or os.path.abspath('.')
    return os.path.join(java_repo, 'squarepants', 'bin', name)

  @classmethod
  def is_java_dir(cls, cwd=None):
    """Checks whether the given directory is the java directory.

    :param str cwd: the directory to check (defaults to current directory).
    """
    if cwd is None:
      cwd = os.path.abspath('.')
    git = Git(cwd)
    return git.status() and os.path.exists(cls.squarepants_binary('', cwd))

  @classmethod
  def find_java_dir(cls, cwd=None):
    cwd = cwd or os.path.abspath('.')
    if not os.path.exists(cwd):
      return None
    last_path = None
    while cwd != last_path:
      if cls.is_java_dir(cwd):
        return cwd
      last_path = cwd
      cwd = os.path.dirname(cwd)
    return None


class Command(object):
  """Wraps up the configuration for running a command.

  Commands are callable, allowing the convenient syntax:

  echo = Command('echo')
  echo('Hello, world!') # Executes: echo 'Hello, world!'
  """

  def __init__(self, name, args=None, cwd=None, env=None, pipe=True):
    """Creates a new command.

    :param str name: name of the command (eg, 'git').
    :param list args: list of arguments which form the beginning of the command invocation (the rest
      of it being supplied when __call__ is invoked). Defaults to [name,].
    :param str cwd: working directory to run the command in (defaults to current working directory).
    :param env: environment variables to run the command with (defaults to os.environ.copy()).
    :param bool pipe: whether to pipe the output to a returned variable, or just dump it into
      stdout.
    """
    self.name = name
    self.args = args or [name]
    self.cwd = cwd or os.path.abspath('.')
    self.env = env or os.environ.copy()
    self.pipe = pipe
    if not os.path.exists(self.cwd):
      raise CommandError('{}: working directory {} does not exist.'.format(self.name, cwd))

  def __call__(self, *vargs, **kwargs):
    """Invokes the system command with the given *vargs.

    If the command needs to query the user via stdin (eg, for a password prompt), pipe=False
    should be passed as a kwarg.
    :return:
    """
    pipe = kwargs.get('pipe', self.pipe)
    args = list(self.args)

    current_dir = os.path.abspath('.')
    os.chdir(self.cwd)

    try:
      args.extend(vargs)
      logger.info('{} > {}'.format(self.cwd, ' '.join(args)))
      if pipe:
        p = Popen(args, cwd=self.cwd, stdout=PIPE, stderr=PIPE, env=self.env)
        out, err = p.communicate()
        if p.returncode == 0:
          return out or True
        logger.warning('Subprocess error: {}\n{}'.format(err, out))
        return False
      p = Popen(args, cwd=self.cwd, env=self.env)
      p.wait()
      return p.returncode == 0
    finally:
      os.chdir(current_dir)


  def __str__(self):
    return "'{}' in {}".format(' '.join(self.args), self.cwd)


class Git(Command):
  def __init__(self, cwd, **kwargs):
    super(Git, self).__init__('git', ['git'], cwd, None, **kwargs)

  def status(self):
    """Result of git status."""
    return self('status')

  def is_clean(self):
    """Returns whether the git directory is clean."""
    status = self.status()
    return status and ', working directory clean' in str(status)

  def branch(self):
    """Returns the name of the current branch."""
    return self('rev-parse', '--abbrev-ref', 'HEAD').strip()

  def branch_exists(self, branch):
    """Returns true if the branch exists in the local repo."""
    return self('rev-parse', '--verify', branch)

  def commit(self, message):
    """Commits changes to the repo, with the supplied commit message."""
    return self('commit', '-am', message)

  def remotes(self):
    """Returns a list of the names of the remote repos."""
    try:
      return self('remote').split('\n')
    except:
      return []

  def _apply_patch(self, patch_url, patch_name, commit=False):
    if patch_url.endswith('.diff') or patch_url.endswith('.patch'):
      logger.debug('Patch identified as a raw diff, attempting git apply.')
      with temporary_file() as patch_dest:
        if not BinaryUtils.download(patch_url, patch_dest):
          raise GitError('Failed to download {} ({})'.format(patch_url, patch_name))
        if not self('apply', patch_dest):
          raise GitError('Failed to apply {} from {}'.format(patch_name, patch_url))
        if not self('add', '-A'):
          raise GitError('Failed to add untracked files.')
        if commit and not self.commit('{}\n\nPatched in from:\n{}'.format(patch_name, patch_url)):
          raise GitError('Failed to commit {}'.format(patch_name))
    else:
      logger.debug('Patch identified as a branch, attempting git merge.')
      if not self('merge', '--no-edit', patch_url):
        raise GitError('Failed to merge {} from {}'.format(patch_name, patch_url))

  @contextmanager
  def apply_patches(self, patches, on_branch=None, commit=False):
    """Applies the given sequence of patches to the git repo, yields, then reverts all patches.

    This requires the local repo to be clean, and will error otherwise. This will abort cleanly and
    raise an error if anything goes wrong.

    :param list patches: list of patches of the form (patch_url, patch_name).  The url can either be
      a literal url to a .diff or .patch file, in which case the url is used to download the diff
      (which is then git apply'd). Otherwise, it is assumed that the url is actually a branch, and
      git merge is run on it. The name is used for logging and for the commit message (if commit is
      True).
    :param str on_branch: name of the temporary branch to use for patching; defaults to a temporary
      branch name. This branch WILL BE DELETED and created freshly in the local repo.
    :param bool commit: whether to commit after patching.
    """
    if not self.is_clean():
      raise GitError('{} is not clean; please commit or stash changes.'.format(self))
    branch = self.branch()
    if not branch:
      raise GitError('Could determine current branch.')
    logger.debug('Current branch: {}'.format(branch))

    temp_branch_name = on_branch or 'temp/temporary-patching-branch'

    if self.branch_exists(temp_branch_name):
      self('branch', '-D', temp_branch_name)
    if not self('checkout', '-b', temp_branch_name):
      raise GitError('Could not create temporary patching branch.')

    try:
      for patch_url, patch_name in patches:
        self._apply_patch(patch_url, patch_name, commit=commit)
      yield
    finally:
      logger.debug('\nCleaning up repo ...')
      if not self.is_clean():
        self('reset', '--hard')
      self('checkout', branch)


class PantsGit(Git):
  """Creates a new Git command, automatically setting the cwd to the location of the pants repo."""
  def __init__(self, cwd=None, **kwargs):
    if not cwd:
      cwd = PantsGit.find_pants_src()
      if not cwd:
        raise GitError('Could not find pants source directory (try setting PANTS_SRC).')
      if not os.path.exists(cwd):
        raise GitError('Pants source directory set to "{}", but does not exist.'.format(cwd))
    super(PantsGit, self).__init__(cwd, **kwargs)

  def commit(self, message):
    p = Popen(['build-support/bin/isort.sh', '-f'], stdout=PIPE, stderr=PIPE, cwd=self.cwd)
    p.communicate()
    return super(PantsGit, self).commit(message)

  @classmethod
  def find_pants_src(cls):
    """Tries to find the pants source code.

    Returns the path to the source directory if it finds it, otherwise returns None.
    """
    if 'PANTS_SRC' in os.environ:
      return os.environ['PANTS_SRC']
    home = os.path.expanduser('~')
    srcs = [os.path.join(home, name) for name in os.listdir(home) if name.lower()=='src']
    srcs = filter(os.path.isdir, srcs)
    pants_srcs = []
    for source_dir in srcs:
      pants_srcs.extend(os.path.join(source_dir, name) for name in os.listdir(source_dir) if name.lower()=='pants')
    pants_srcs = filter(os.path.isdir, pants_srcs)
    pants_srcs = [src for src in pants_srcs if Git(src).status()]
    return pants_srcs.pop() if pants_srcs else None
