#!/usr/bin/env python

# Checks to see if BUILD.gen files need to be re-generated, and if so calls
# generate_BUILD_from_poms.sh. For exact execution process, see docs under main().
#
# Typically runs in about 3 secs if no generation is required, 8 secs if BUILD.gens can be loaded
# from its cache (~/.pants.d/pom-gen/), and 20 seconds if everything must be generated.
#
# When running for the very first time it typically takes a bit longer.

import fnmatch
from hashlib import sha1
import logging
import os
import re
from shutil import copyfile, rmtree
import signal
import subprocess
import sys
import time

from pom_utils import PomUtils
from pom_to_BUILD import PomToBuild
from generate_3rdparty import ThirdPartyBuildGenerator
from generate_root_BUILD import RootBuildGenerator


def _get_dependency_patterns():
  dep_patterns = ['pom.xml', 'BUILD*',]
  for middle in ('main', 'test',):
    for tail in ('resources', 'java', 'proto',):
      dep_patterns.append('*/src/%s/%s' % (middle, tail))
  return dep_patterns

# -------------------------------------------------
# GLOBAL CONFIGURATION VARIABLES
# -------------------------------------------------
_CACHE_DIRECTORY = './.pants.d/pom-gen/'
_EXCLUDE_CONTAINS = ('/target/', './parents/', '/hack-protos/', '/dist/', '/.pants.d/',)
_EXCLUDE_FILES = ('pom.xml',)
_DEPENDENCY_PATTERNS = _get_dependency_patterns()
_GENERATOR_PATHS = ['squarepants',]
_GENERATOR_PATTERNS = ['*/bin/*', '*/src/main/python/*.py', '*/src/main/python/*/*.py',]
_SCRIPT_DIR = 'squarepants/src/main/python/squarepants'
_VERSION = 1.7
_GEN_NAMES = set(['BUILD.gen', 'BUILD.aux',])
_BUILD_GEN_CACHING_ENABLED = True
# -------------------------------------------------

logger = logging.getLogger(__name__)


class MissingToolError(Exception):
  """Raised when this script is unable to execute a command-line utility."""
  pass

class IndexFormatError(Exception):
  """Raised when an index can't be parsed"""
  pass


class OutdatedError(Exception):
  def __init__(self, version):
    super(OutdatedError, self).__init__(
        'checkpoms is outdated (index file version %.3f, checkpom version %.3f), force with -f.'
            % (version, _VERSION))

class TestingError(Exception):
  """Raised when an error occurs in the 'unit' test."""

class Task(object):
  """Basically a souped-up lambda function which times itself running."""

  class Error(Exception):
    pass

  def __init__(self, name=None, run=None):
    self._run = run or (lambda: None)
    self.name = name or 'Unnamed Task'
    self._time_taken = -1

  def run(self):
    return self._run()

  @property
  def duration(self):
    if self._time_taken < 0:
      raise self.Error('Time cannot be queried before task is run.')
    return self._time_taken

  def __call__(self):
    logger.debug('Starting %s.' % self.name)
    start = time.time()
    value = self.run()
    end = time.time()
    self._time_taken = end - start
    logger.debug('Done with %s (took %0.03f seconds).' % (self.name, self.duration))
    return value


def find_files(roots, patterns):
  """Recursively finds files in the given list of root directories which match any of the naming
  patterns
  :param roots: root paths to search under
  :param patterns: filename patterns to search for
  :return: list of files files that match the pattern
  """
  configs = {}
  for pattern in patterns:
    # Runs a second faster when in parallel.
    key = len(configs)
    if not key in configs:
      configs[key] = []
    names = configs[key]
    if names:
      names.append('-or')
    names.extend(['-name' if '/' not in pattern else '-path', pattern])
  try:
    popen_list = []
    for root in roots:
      for key in configs:
        popen_list.append(subprocess.Popen(['find', root] + configs[key], stdout=subprocess.PIPE))
    logger.debug('Number of spawned tasks: {num_tasks}'.format(num_tasks=len(popen_list)))
    results = set(line.strip() for line in stream_stdout(popen_list))
    # If the empty string gets in the results, it mucks up the works.
    if '' in results:
      results.remove('')
    return results
  except OSError:
    raise MissingToolError("Missing tool 'find'!")

def find_branch():
  """:return: the name of the current git branch."""
  try:
    if not os.path.exists('.git'):
      # Ookay, just use the username I guess?
      return re.sub('[^a-zA-Z0-9]+', '', os.getlogin())
    # Counter-intuitively, this method seems to run faster than
    # git describe --contains --all HEAD
    for line in read_binary(['git', 'branch']):
      if line[0] == '*':
        return line[1:].strip()
    return ''
  except OSError:
    raise MissingToolError('Expected git to be on the system path.')

def get_branch_cache(index_base, path):
  """Get the temporary cache directory by the branch name.
  :param index_base: The base path to store the index cache in
  :param path: The path to the root of the repo
  :return: The directory under index_base to store the index in.
  """
  try:
    branch_name = Task('find_branch', find_branch)()
  except MissingToolError as e:
    warn('%s, falling back on input hash.' % e)
    branch_name = hash(path)
  return os.path.join(index_base, branch_name)

def exec_binaries(args_groups, env=None):
  """Launch one or more background processes
  :param args_groups: list of arg lists, one list per binary to launch.
  :param env: environment to launch for each subprocess.
  :return: list of Popen objects.
  """
  if not env:
    env = os.environ
  popen_list = []
  for args in args_groups:
    popen_list.append(subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env))
  return popen_list

def drain_pipes(popen_list, ignore_stderr=False):
  """ Read the output from piped output (see exec_binaries() above)
  :param pipes: list of Popen objects
  :return:  A list of strings Output from the subprocesses. Output from pipes is
          not interleaved.  Blocks until all output is drained.
  """
  results=[]
  for p in popen_list:
    # Originally this code tried to work as a generator, returning output as it was returned from
    # the spawned task by reading lines from the pipes, but that lead to deadlocks, just as
    # predicted by the python docs.  To work that way reliably you have to use select(), threads, or
    # separate proceses.
    (stdoutdata, stderrdata) = p.communicate()
    streams_from_task = [stdoutdata]
    if not ignore_stderr:
     streams_from_task.append(stderrdata)
    for data in streams_from_task:
      if data:
        for line in data.split('\n'):
          results.append(line)
  return results

def stream_stdout(popen_list):
  """Streams the stdout from a list of tasks back to the caller as a generator
  :param pipes: a list of Popen objects
  :return:  A list of strings Output from the subprocesses.  Single lines are not interleaved, but
  output between the two tasks may be intermixed (TBD).
  """
  for p in popen_list:
    while True:
      line = p.stdout.readline()
      if line:
        yield line
      else:
        break

def same_contents(a, b):
  """:return: True if the strong hashes of the files are identical."""
  ha, hb = compute_hashes([a, b])
  return ha == hb

def read_binary(args, env=None):
  """Executes the given command-line arguments and yields its stdout line by line.
  Convenience method to combine the call to exec_binaries() and drain_pipes()"""
  vargs = args if len(args) < 6 else args[:6]+['...']
  logger.debug('read_binary: %s' % vargs)
  return drain_pipes(exec_binaries([args], env=env))

def iter_multi(*groups):
  """:returns: a generator which iterates over all the items in all the input iterators."""
  for group in groups:
    for item in group:
      yield item

def common_prefix(a, b):
  """:return: the longest common prefix between a and b."""
  for i in range(min(len(a), len(b))):
    if a[i] != b[i]:
      return a[:i]
  return ''

def find_gen_deps(baseroot):
  """Finds files in the project which may necessitate re-generating BUILD.gens if modified.
  :param paths: list of root paths (typically just the project directory)
  """
  dep_patterns = _DEPENDENCY_PATTERNS
  deps = find_files([baseroot], dep_patterns)
  deps = deps.union(find_files(_GENERATOR_PATHS, _GENERATOR_PATTERNS))
  # trim out deps we don't want
  taboo_contains = _EXCLUDE_CONTAINS
  taboo_equals = [os.path.join(baseroot, name) for name in _EXCLUDE_FILES]
  deps = Task('trimming deps', lambda: [dep for dep in deps
      if not any((n in dep) for n in taboo_contains) and not any((n == dep) for n in taboo_equals)
    ])()
  return deps

def compute_hashes(paths, path_only=lambda p: False):
  """Computes strong hashes of the contents of all the files paths, and returns them as a list.
  :param path_only: Optional lambda function which takes in a path, and returns true if that path
    should be hashed using only its pathname, rather than its binary contents.
  """
  hashes = []
  for path in paths:
    if path_only(path) or os.path.isdir(path):
      hashes.append(sha1(path).hexdigest())
      continue
    try:
      with open(path, 'rb') as f:
        hashes.append(sha1(f.read()).hexdigest())
    except:
      hashes.append('0') # Probably a broken symlink.
  return hashes

def read_index(index_file, force=False):
  """Reads the index file and returns its contents as set of tuples. An index file is expected to be
  formatted such that each tuple is on its own line, with elements separated by tabs.
  :param boolean force: continue if index appears to be an incompatible version
  """
  with open(index_file, 'r') as f:
    lines = f.readlines()
  if lines and lines[0].startswith('#'):
    version = float(lines[0].split(' ')[-1])
    if version < _VERSION:
      warn('Index file is outdated (version %.3f vs %.3f)' % (version, _VERSION))
      # If the index is outdated, we should force a complete regeneration.
      return set()
    elif version > _VERSION:
      # Nothing we can really do but warn the user and exit.
      err = OutdatedError(version)
      if force:
        warn(str(err))
      else:
        raise err
  results = set()
  line_number = 0
  for line in lines:
    line_number += 1
    line = line.strip()
    if line and not line.startswith('#'):
      result = line.split('\t')
      if len(result) != 2:
        raise IndexFormatError(
          "Expected 2 entries separated by tabs, got: {line} in {file}:{line_number}"
          .format(line=line, file=index_file, line_number=line_number))
  return set(tuple(line.strip().split('\t')) for line in lines
                                             if line.strip() and not line.startswith('#'))

def write_index(index_file, pairs):
  """Writes the index file as set of tuples. An index file is expected to be formatted such that
  each tuple is on its own line, with elements separated by tabs.
  """
  tmp_file = index_file + ".tmp"
  with open(tmp_file, 'w') as f:
    f.write('# Generated by squarepants/bin/checkpoms version {version}'.format(version=_VERSION))
    f.write('\n\n')
    for pair in pairs:
      f.write('\t'.join(pair) + '\n')
  os.rename(tmp_file, index_file)

def find_and_hash_deps(root):
  """Finds all files that matter to BUILD.gen's, hashes them, and returns both lists."""
  logger.debug('Indexing pom.xml/BUILD files...')
  # Order matters here, so list().
  deps = list(Task('finding deps', lambda: find_gen_deps(root))())
  logger.debug('Hashing pom.xml/BUILD files...')
  keys = Task('hashing deps', lambda: compute_hashes(deps,
      lambda p: (os.path.basename(p) not in _GEN_NAMES
                 and os.path.basename(p).startswith('BUILD'))))()
  return deps, keys

def compute_dep_differences(old_pairs, new_pairs):
  """:param old_pairs: list of (dep, sha) tuples retrieved from the index
  :param new_pairs: list of (dep, sha) tuples calculated from workspace
  :return: tuple of pom files that have been removed, added, or modified since stored in the index
  """
  removed_deps = set()
  added_deps = set()
  changed_deps = set()

  if old_pairs != new_pairs:
    new_deps = dict(new_pairs)
    old_deps = dict(old_pairs)
    added_deps = set(dep for dep, sha in new_pairs if dep not in old_deps)
    removed_deps = set(dep for dep, sha in old_pairs if dep not in new_deps)
    changed_deps = set(dep for dep in (set(new_deps.keys()) - added_deps)
                       if new_deps[dep] != old_deps[dep])

  return removed_deps, added_deps, changed_deps


class CheckPoms(object):
  """Main driver class which runs this script (not including testing).
  It checks to see if BUILD.gens need to be regenerated or reloaded from cache, and does so if
  necessary.
  """
  def __init__(self, path, flags):
    self.baseroot = path
    self.flags = flags
    logger.debug('baseroot: "{0}"'.format(self.baseroot))
    cd = _CACHE_DIRECTORY
    if not os.path.isabs(cd):
      cd = os.path.normpath(os.path.join(self.baseroot, cd))
    self.index_base = os.path.expanduser(cd)
    self.index_dir = get_branch_cache(self.index_base, self.baseroot)
    self.index_file = os.path.join(self.index_dir, 'poms.index')
    logger.debug('Index file path: {path}'.format(path=self.index_file))

    def signal_handler(signal, frame):
      print('Aborted with Ctrl-C. Cleaning up.')
      # Removing the current cached dir means the next invocation will re-calculate it
      self._clean_index_dir()
      # Generated build files may be in an inconsistent state. Get rid of them to avoid confusion.
      self._clean_generated_builds()
      sys.exit(1)
    signal.signal(signal.SIGINT, signal_handler)

  def execute(self):
    # TODO(Garrett Malmquist): Unify how cache is stored into a single index, using pickle. Just
    # unpickle previous state to start with, pickle new state to end with. Remove need for ad-hoc
    # I/O in-between.
    self._check_pex_health()
    self._find_dependencies()
    self._execute_clean_flags()
    self._find_dependency_differences()
    self._regenerate_if_necessary_and_reindex()

  def _check_pex_health(self):
    """Check to see if pants.pex has been modified since the version stored in the branch. If so,
    then the workspace is cleaned up to remove old state and force BUILD files to be regenerated.
    """
    logger.info('Checking to see if pants.pex version has changed ...')
    pex_file = os.path.join(self.baseroot, 'squarepants', 'bin', 'pants.pex')
    if not os.path.exists(pex_file):
      error("No pants.pex file found; pants isn't installed properly in your repo.")
      sys.exit(1)
    hashes = set()
    with open(pex_file, 'rb') as pex:
      hashes.add(sha1(pex.read()).hexdigest())
    cached_hashes = os.path.join(_CACHE_DIRECTORY, 'pex-hashes')
    if os.path.exists(cached_hashes):
      with open(cached_hashes, 'r') as f:
        if hashes == set(l.strip() for l in f.readlines() if l.strip()):
          return # Nothing changed.
      logger.info('Pants version has changed since last run. Cleaning .pants.d ...')
      for line in read_binary([pex_file, 'goal', 'clean-all']):
        logger.debug('clean: %s' % line.strip())
    if not os.path.exists(os.path.dirname(cached_hashes)):
      os.makedirs(os.path.dirname(cached_hashes))
    with open(cached_hashes, 'w+b') as f:
      f.write('\n'.join(hashes))

  def _find_dependencies(self):
    logger.info('Checking to see if generated BUILD.* files are outdated in %s ...' % self.baseroot)
    # TODO: Not use absolute paths? What should they be relative to? User? Workdir?
    self.dep_files, self.dep_hashes = Task('find_and_hash_deps',
                                           lambda: find_and_hash_deps(self.baseroot))()
    self.new_pairs = set(zip(self.dep_files, self.dep_hashes))

  def _execute_clean_flags(self):
    """Implements the --clean-all and --clean flags for this script."""
    if '--clean-all' in self.flags: # Very destructive.
      logger.info('Removing %s' % self.index_base)
      if os.path.exists(self.index_base):
        rmtree(self.index_base)

    if '--clean' in self.flags: # Fairly destructive.
      self._clean_index_dir()

  def _find_dependency_differences(self):
    logger.debug('Loading index file...')
    self.old_pairs = self._load_previous_depset()
    self.removed_deps, self.added_deps, self.changed_deps = compute_dep_differences(
        self.old_pairs, self.new_pairs)

    self.total_diffs = len(self.removed_deps) + len(self.added_deps) + len(self.changed_deps)

    if self.total_diffs > 0:
      logger.info('Found: %d changed entries, %d removed entries, %d added entries.' %
          (len(self.changed_deps), len(self.removed_deps), len(self.added_deps)))

    if self.total_diffs < 100:
      for s in ('Added: %s\nRemoved: %s\nChanged: %s' %
          (self.added_deps, self.removed_deps, self.changed_deps)).split('\n'):
        logger.debug(s)

  def _load_previous_depset(self):
    index_dir, index_file = self.index_dir, self.index_file
    old_pairs = set()
    if not os.path.exists(index_file):
      logger.debug('No index file exists at "%s"' % index_file)
      if not os.path.exists(index_dir):
        os.makedirs(index_dir)
    else:
      # Need to read in previous index file.
      logger.debug('Reading index file "%s"' % index_file)
      old_pairs = read_index(index_file, '-f' in self.flags or '--force' in self.flags)
      logger.debug('Read %d hashed deps.' % len(old_pairs))
    return old_pairs

  def _regenerate_if_necessary_and_reindex(self):
    if Task('poms_to_builds', self._regenerate_maybe)():
      if os.path.exists(self.index_file):
        os.remove(self.index_file)
      p, h = Task('find_and_hash_deps', lambda: find_and_hash_deps(self.baseroot))()
      Task('write_index', lambda: write_index(self.index_file, set(zip(p, h))))()

  def _clean_generated_builds(self):
    """Removes all generated BUILD files from the source diretory"""
    Task('clean_build_gen', lambda:
      os.system(
        "find {root} \( -name BUILD.gen -o -name BUILD.aux \! -path '*/.pants.d/*' \) | xargs rm -f"
        .format(root=self.baseroot)))

  def _clean_index_dir(self):
    """Removes the currently computed index of files to shas"""
    logger.info('Removing %s' % self.index_dir)
    if os.path.exists(self.index_dir):
      rmtree(self.index_dir)

  def _regenerate_maybe(self):
    """Generates (or links) BUILD.gen files, if necessary.
    :returns: True if this generated or linked any files, False if it noop'd.
    """
    cache_dir = self.index_dir
    removed_deps = self.removed_deps
    added_deps = self.added_deps
    changed_deps = self.changed_deps

    force_rebuild = not _BUILD_GEN_CACHING_ENABLED or '--rebuild' in self.flags

    if not force_rebuild and  self.total_diffs == 0:
      return False # Nothing to do.

    self._clean_generated_builds()

    if not force_rebuild:
      for dep in iter_multi(removed_deps, added_deps, changed_deps):
        filename = os.path.basename(dep)
        if fnmatch.fnmatch(filename, 'BUILD*'):
          continue
        logger.debug('Matched non-BUILD file %s, forcing rebuild' % (dep))
        force_rebuild = True
        break

    if not force_rebuild:
      # GEN's need to be re-gen'd if a BUILD file was removed.
      # AUX's need to be re-gen'd if a BUILD file was added.
      for dep in iter_multi(removed_deps, added_deps):
        name = os.path.basename(dep)
        if name.startswith('BUILD') and name not in _GEN_NAMES:
          force_rebuild = True
          break

    builds_index = os.path.join(cache_dir, 'build_gen.index')
    gens_dir = os.path.join(cache_dir, 'gens')

    if not force_rebuild and os.path.exists(builds_index):
      logger.info('Generated BUILD.* files are outdated, loading correct versions from cache.')
      self._restore_cache(gens_dir, builds_index)
    else:
      logger.info('Generated BUILD.* files are outdated, Regenerating.')
      self._rebuild_everything(gens_dir, builds_index)
    return True

  def _restore_cache(self, gens_dir, builds_index):
    for dep in self.added_deps:
      if os.path.basename(dep) in _GEN_NAMES:
        logger.debug('Removing %s' % dep)
        try:
          os.remove(dep)
        except OSError:
          # don't complain if the file doesn't exist
          pass

    for source, target in read_index(builds_index, '-f' in self.flags or '--force' in self.flags):
      target_dir = os.path.dirname(target)
      if not os.path.exists(target_dir):
        warn('Missing directory for target %s' % target_dir)
        continue # What? Okay, skip it, I guess.
      if not '3rdparty' in target_dir:
        if any(f.startswith('BUILD') and f != 'BUILD.gen' for f in os.listdir(target_dir)):
          logger.debug('Skipping directory %s, build file already exists.' % target_dir)
          if os.path.exists(target):
            os.remove(target)
          continue # There's a real BUILD file here already.
      gen_source = os.path.join(gens_dir, source)
      if not same_contents(gen_source, target):
        logger.debug('Replacing %s' % target)
        if os.path.exists(target):
          os.remove(target)
        for output in read_binary(['cp', gen_source, target]):
          # Generally isn't any output, and we don't care if there is.
          # Just here to make the stream is drained and the subprocess is closed.
          pass

  def _rebuild_everything(self, gens_dir, builds_index):
    # The cached BUILD files are now invalid. Remove them first
    rmtree(gens_dir, ignore_errors=True)

    poms = [x + '/pom.xml' for x in PomUtils.get_modules()]
    # Convert pom files to BUILD files
    for pom_file_name in poms:
      PomToBuild().convertPom(pom_file_name, rootdir=self.baseroot)

    logger.info('Re-generating 3rdparty/BUILD.gen')
    with open('3rdparty/BUILD.gen', 'w') as build_file:
      build_file.write(ThirdPartyBuildGenerator().generate())

    logger.info('Re-generating BUILD.gen')
    with open('BUILD.gen', 'w') as build_file:
      build_file.write(RootBuildGenerator().generate())

    new_gens = find_files([self.baseroot], _GEN_NAMES)
    logger.info('Caching {num_build_files} regenerated BUILD.* files. '
                .format(num_build_files=len(new_gens)))
    os.makedirs(gens_dir)
    gen_pairs = set()
    for gen in new_gens:
      if gen == '':
        continue
      cache_name = sha1(gen).hexdigest()
      index = 0
      while os.path.exists(os.path.join(gens_dir, cache_name+str(index))):
        index += 1
      cache_name += str(index)
      cache_path = os.path.join(gens_dir, cache_name)
      copyfile(gen, cache_path)
      gen_pairs.add((cache_path, gen))
    write_index(builds_index, gen_pairs)

def usage():
  print "usage: %s [args] " % sys.argv[0]
  print "Checks to see if the BUILD.* files should be recomputed for the repo"
  print ""
  print "-?,-h         Show this message"
  print "--rebuild     unconditionally rebuild the BUILD files from pom.xml"
  print "-f, --force   force the use of a seemingly incompatible index version"
  PomUtils.common_usage()

def main():

  arguments = PomUtils.parse_common_args(sys.argv[1:])

  flags = set(arg for arg in arguments if arg.startswith('-'))

  paths = list(set(arguments) - flags)
  paths = paths or [os.getcwd()]
  if len(paths) > 1:
    logger.error('Multiple repo root paths not supported.')
    return

  path = os.path.realpath(paths[0])

  for f in flags:
    if f == '-h' or f == '-?':
      usage()
      return
    elif f == '--rebuild':
      pass
    elif f == '-f' or f == '--force':
      pass
    else:
      print ("Unknown flag %s" % f)
      usage()
      return
  main_run = Task('main', lambda: CheckPoms(path, flags).execute())
  main_run()
  logger.info('Finish checking BUILD.* health in %0.3f seconds.' % main_run.duration)


if __name__ == '__main__':
  main()
