#!/usr/bin/env python

# Checks to see if BUILD.gen files need to be re-generated, and if so calls
# generate_BUILD_from_poms.sh. For exact execution process, see docs under main().
#
# Typically runs in about 0.8 secs if no generation is required, 7 secs if BUILD.gens can be loaded
# from its cache (~/.pants.d/pom-gen/), and 16 seconds if everything must be generated.
#
# When running for the very first time it typically takes about 1.4 seconds longer, because the
# python code hasn't been compiled to a .pyc anywhere yet (I assume).

import logging
import os
import re
import sys
from contextlib import contextmanager
from shutil import copyfile, copytree, rmtree
from tempfile import gettempdir

from checkpoms import *
from pom_utils import PomUtils


logger = logging.getLogger(__name__)

_exit_on_fail = False

_BUILD_GENS_OUTDATED_MSG = 'BUILD.* files are outdated, Regenerating'
_ONE_ADDED_ENTRY_MSG = ' 1 added entr'
_ONE_REMOVED_ENTRY_MSG = ' 1 removed entr'
_ONE_CHANGED_ENTRY_MSG = ' 1 changed entr'
_CORRECT_VERSIONS_FROM_CACHE_MSG = 'correct versions from cache'
_WRITE_INDEX_MSG = 'write_index'


class OutputExaminer(object):
  """Class for inspecting binary output, used for running tests."""

  class Error(Exception):
    """Error examining output."""

  class Checker(object):
    """Individual test for binary output."""
    def __init__(self, name, check_line, init=False, target=True):
      if not callable(check_line):
        raise OutputExaminer.Error('check_line must be callable!')
      self.name = name
      self.check_line = check_line
      self.status = init
      self.target = target
      self.vars = {}
      self.failed_on = None

  def __init__(self, args, name=None, env=None):
    self.args = args
    self.checkers = []
    self.name = name
    self.env = env

  def check(self, name, testf, init=False, target=True):
    '''Convenience method for adding to self.checkers'''
    self.checkers.append(OutputExaminer.Checker(name, testf, init, target))

  def run(self):
    """Invokes the command-line command used to initialize this class, and iterates over the lines
    of its output. Each line is fed through a list of 'checkers', which all return a status used to
    determine 'pass' or 'fail' at the end of the test.
    """
    passed, failed = 0, 0
    if self.name:
      logger.info('\n===  %s  ===' % self.name)

    try:
      for line in read_binary(self.args, env=self.env):
        logger.debug("OUTPUT: " + line.strip())
        for checker in self.checkers:
          checker.status = checker.status or checker.check_line(line)
          if not checker.failed_on and checker.status != checker.target and not checker.target:
            checker.failed_on = line.strip()
      for checker in self.checkers:
        if checker.status and checker.target or (not checker.status and not checker.target):
          passed += 1
          logger.info('PASSED %s' % (checker.name))
        else:
          failed += 1
          logger.error('FAILED %s (%s) on "%s"'
              % (checker.name, checker.status, str(checker.failed_on).replace('\n', ' ')))
          if _exit_on_fail:
            raise self.Error('Exiting on failure due to -x command line flag')
      logger.info('%d passed, %d failed' % (passed, failed))
      failed > 0 and logger.info('Re-run with -ldebug to see command output.')
    except Exception as e:
      failed += 1
      logger.error('EXCEPTION: %s' % e)
      if _exit_on_fail:
        logger.info('Re-run with -ldebug to see command output.')
        raise e

    return passed, failed

  def __call__(self):
    return self.run()


@contextmanager
def create_temp_root(to_copy=[]):
  """Creates a temporary java/ project root used to perform testing."""
  logger.debug('Creating temporary project root...')
  folder = os.path.join(gettempdir(), 'checkpoms_temp_dir')
  if os.path.exists(folder):
    rmtree(folder)
  os.makedirs(folder)

  logger.debug(' Copying project files...')
  # Fill with a few 'example' projects and files.
  for src in to_copy:
    if not os.path.exists(src):
      raise TestingError('Example file or directory does not exist "%s"' % src)
    dst = os.path.join(folder, src)
    if os.path.isdir(src):
      copytree(src, dst)
    else:
      copyfile(src, dst)
  # Clean out all pre-existing BUILD.gens
  logger.debug(' Removing pre-existing BUILD.gens')
  os.system("find '{folder}' -name 'BUILD.gen' | xargs rm".format(folder=folder))
  with open(os.path.join(folder, 'pom.xml'), 'w') as root_pom:
    root_pom.write("""<?xml version="1.0" encoding="UTF-8"?>
<project xmlns="http://maven.apache.org/POM/4.0.0" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:schemaLocation="http://maven.apache.org/POM/4.0.0          http://maven.apache.org/xsd/maven-4.0.0.xsd">
  <modelVersion>4.0.0</modelVersion>

  <groupId>com.squareup</groupId>
  <artifactId>all</artifactId>
  <version>HEAD-SNAPSHOT</version>
  <description>All of Square's Java projects. It's like a party for your code.</description>
  <packaging>pom</packaging>

  <modules>
    <module>hoptoad</module>
    <module>service/container/annotation-processors-tests</module>
    <module>service/container/annotation-processors</module>
    <module>service/container/components/admin</module>
    <module>service/container/components/clustering/database</module>
    <module>service/container/components/gns</module>
    <module>service/container/components/cronjobs/annotations</module>
    <module>service/container/components/cronjobs</module>
    <module>service/container/components/persistence</module>
    <module>service/container/components/proto-interceptors</module>
    <module>service/container/components/proto-interceptors/modules</module>
    <module>service/container/components/redis</module>
    <module>service/container/components/rpc</module>
    <module>service/container/components/webservice</module>
    <module>service/container/testing</module>
    <module>service/container/tests</module>
    <module>service/container</module>
    <module>service/exemplar</module>
    <module>service/framework/validation</module>
    <module>service/framework</module>
    <module>squarepants/pants-test-app</module>
  </modules>
</project>
""")

  yield folder
  if os.path.exists(folder):
    rmtree(folder)

def run_tests():
  """Runs some tests to check whether the script functions as expected.

  It currently copies part of the directory structure from java/ to function, which means these
  tests may break if changes are made to the files/directories mentioned in to_copy.
  """
  # TODO(zundel) create a canned directory in test to copy files over?  But maybe this is better
  # because it tests the actual contents of our repo.
  to_copy = ('3rdparty', 'squarepants', 'service', 'hoptoad', 'parents',
    'BUILD', 'BUILD.tools', 'pants', 'pants.ini', 'no_pants.yaml')

  with create_temp_root(to_copy) as rootdir:
    checkpoms = os.path.join(rootdir, 'squarepants/bin/checkpoms')
    command = [checkpoms, '-ldebug', rootdir,]
    results = {'passed': 0, 'failed': 0}
    environment = os.environ.copy()
    environment['PWD'] = rootdir
    os.chdir(rootdir)

    @contextmanager
    def examiner(com=command, name='', env=environment, ignore_errors=False):
      exam = OutputExaminer(com, name=name, env=env)
      yield exam
      if not ignore_errors:
        exam.check('No errors occured', lambda l: l.startswith('Traceback (most recent'),
          target=False)
      p, f = exam()
      results['passed'] += p
      results['failed'] += f

    def noop():
      """Checks to make sure checkpoms does nothing when re-ran multiple times."""
      with examiner(name='Repeated No-op') as exam:
        exam.check('No-op', lambda l: _WRITE_INDEX_MSG in l, target=False)

    @contextmanager
    def idempotent(com=command, name=''):
      """Calls examiner twice, the first time as normal, the second time to make sure checkpoms
      no-ops when run multiple times.
      """
      with examiner(com, name) as exam:
        yield exam
      noop()

    def check(msg, value, crash=False):
      if value:
        results['passed'] += 1
        logger.info('PASSED %s' % msg)
      else:
        results['failed'] += 1
        logger.error('FAILED %s' % msg)
        if crash:
          raise TestingError('Test failed: {msg}'.format(msg=msg))

    with idempotent(name='Fresh start') as exam:
      exam.check('BUILD.gens re-generated', lambda l: _BUILD_GENS_OUTDATED_MSG in l)
      exam.check('Files added', lambda l: re.search(r'\d{2,} added entries', l))
      exam.check('Index written', lambda l: _WRITE_INDEX_MSG in l)
    test_file = os.path.join(rootdir, '3rdparty', 'BUILD.gen')
    check(test_file + ' exists', os.path.exists(test_file), crash=True)

    with idempotent(name='No-op') as exam:
      exam.check('No-op', lambda l: _WRITE_INDEX_MSG in l, target=False)

    # BUILD gen file to mess with to check build process
    build_gen_victim = os.path.join(rootdir, 'hoptoad', 'BUILD.gen')

    check('build_gen_victim exists', os.path.exists(build_gen_victim), crash=True)
    os.remove(build_gen_victim)
    with idempotent(name='Reload from cache after BUILD.gen deletion') as exam:
      exam.check('Removed 1 entry', lambda l: _ONE_REMOVED_ENTRY_MSG in l)
      exam.check('Replace from cache', lambda l: 'Replacing' in l)
    check('BUILD.gen exists again', os.path.exists(build_gen_victim), crash=True)

    os.system("echo 'hi-there' >> {path}".format(path=build_gen_victim))
    with idempotent(name='Changed single BUILD.gen file') as exam:
      exam.check('Changed 1 entry', lambda l: _ONE_CHANGED_ENTRY_MSG in l)
      exam.check('Reload from cache', lambda l: _CORRECT_VERSIONS_FROM_CACHE_MSG in l)

    os.system("echo 'hi-there' >> {path}"
        .format(path=os.path.join(rootdir, 'service', 'BUILD.gen')))
    with idempotent(name='Added single BUILD.gen file') as exam:
      exam.check('Added 1 entry', lambda l: _ONE_ADDED_ENTRY_MSG in l)
      exam.check('Reload from cache', lambda l: _CORRECT_VERSIONS_FROM_CACHE_MSG in l)

    os.system("find {path} -name 'BUILD' | grep -v -e '3rdparty' -e '.pants.d' -e 'squarepants' | head -n 1 | xargs rm"
        .format(path=os.path.join(rootdir, 'hoptoad')))
    with idempotent(name='BUILD removed') as exam:
      exam.check('BUILD.gens re-generated', lambda l: _BUILD_GENS_OUTDATED_MSG in l)
      exam.check('Index written', lambda l: _WRITE_INDEX_MSG in l)

    os.system("echo '  \n  ' >> {path}"
        .format(path=os.path.join(rootdir, 'hoptoad', 'pom.xml')))
    with idempotent(name='Changed single POM file') as exam:
      exam.check('BUILD.gens re-generated', lambda l: _BUILD_GENS_OUTDATED_MSG in l)
      exam.check('Index written', lambda l: _WRITE_INDEX_MSG in l)

    os.system("echo 'hi-there' >> {path}"
        .format(path=os.path.join(rootdir, 'hoptoad', 'BUILD')))
    with idempotent(name='Added single BUILD file') as exam:
      exam.check('Added 1 entry', lambda l: _ONE_ADDED_ENTRY_MSG in l)
      exam.check('Reload from cache', lambda l: _BUILD_GENS_OUTDATED_MSG in l)

    os.system("echo 'generator-update' >> {path}"
        .format(path=os.path.join(rootdir, 'squarepants', 'bin', 'checkpom')))
    with idempotent(name='Added checkpom script in squarepants/bin') as exam:
      exam.check('Added 1 entry', lambda l: _ONE_ADDED_ENTRY_MSG in l)
      exam.check('BUILD.gens re-generated', lambda l: _BUILD_GENS_OUTDATED_MSG in l)

    os.system("echo 'generator-update' >> {path}"
        .format(path=os.path.join(rootdir, 'squarepants', 'bin', 'checkpom')))
    with idempotent(name='Updated checkpom script in squarepants/bin') as exam:
      exam.check('Updated 1 entry', lambda l: _ONE_CHANGED_ENTRY_MSG in l)
      exam.check('BUILD.gens re-generated', lambda l: _BUILD_GENS_OUTDATED_MSG in l)

    os.system("echo 'generator-update' >> {path}"
        .format(path=os.path.join(rootdir, 'squarepants', 'src', 'main', 'python', 'squarepants', 'generate_foo.py')))
    with idempotent(name='Added checkpom script in squarepants/src/main/python') as exam:
      exam.check('Added 1 entry', lambda l: _ONE_ADDED_ENTRY_MSG in l)
      exam.check('BUILD.gens re-generated', lambda l: _BUILD_GENS_OUTDATED_MSG in l)

    os.system("echo 'generator-update' >> {path}"
        .format(path=os.path.join(rootdir, 'squarepants', 'src', 'main', 'python', 'squarepants', 'generate_foo.py')))
    with idempotent(name='Updated checkpom script in squarepants/src/main/python') as exam:
      exam.check('Updated 1 entry', lambda l: _ONE_CHANGED_ENTRY_MSG in l)
      exam.check('BUILD.gens re-generated', lambda l: _BUILD_GENS_OUTDATED_MSG in l)

    logger.info('\n===  TOTAL RESULTS  ===')
    logger.info('%d PASSED, %d FAILED' % (results['passed'], results['failed']))

def _usage():
  usage()
  print("-x        Exit immediately on failure")
  PomUtils.common_usage()

def _main():
  global _exit_on_fail
  arguments = PomUtils.parse_common_args(sys.argv[1:])

  flags = set(arg for arg in arguments if arg.startswith('-'))
  paths = list(set(arguments) - flags)
  paths = paths or [os.getcwd()]

  for i, path in enumerate(paths):
    paths[i] = os.path.realpath(path)

  for f in flags:
    if f == '-x':
      _exit_on_fail = True
    elif f == '-?' or f == '-h':
      _usage()
      return
    else:
      print("Unknown flag %s" % f)
      _usage()
      return

  run_tests()

if __name__ == '__main__':
  _main()
