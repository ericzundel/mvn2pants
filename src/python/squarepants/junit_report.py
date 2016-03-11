#!/usr/bin/env python2.7
#
# Called from script/ci to analyze the test failures recorded in the ant .xml files.
#
# JUnit tests listed in the --dir directory are considered flaky and are OK to fail.
# If all the tests that have been marked flaky, exit with status 0
# Otherwise, the script throws an exception and will exit with non-zero status.
#
# To mark a test as flaky, create a file in the --flakes directory with the same name as the test
# failure's class and method name separated by periods.  For example:
#
# cat >build-support/flakes/com.squareup.tracon.TraconReloadTest.swapNewRoutes <<EOT
# Tracon reload test flakes due to timing issues.
# EOT
#
# Notes:
# This script has two disjoint tasks:
# -- Produce an application/json-seq report
# -- Succeed if (and only if) there were failures and they were flakey.
# These tasks are conflated, for now, because they both involve
# reading the XML output from JUnit. It is possible they will be unconflated
# in the future.

from __future__ import unicode_literals, print_function

import argparse
import collections
import functools
import glob
import itertools
import json
import logging
import os

from xml.etree import ElementTree as ET


logger = logging.getLogger(__name__)


TestCase = collections.namedtuple('TestCase', 'full_name time state')


class State(object):
  SUCCESS = 1
  FAILURE = 2

def getText(elem):
  return (elem.text or '').strip()

def getAllText(elem):
  pieces = [getText(elem)]
  for subelem in elem.iter():
    pieces.append(getText(subelem))
  return ''.join(pieces)

def parse_string(data):
  tree = ET.fromstring(data)
  for suite in tree.iter('testsuite'):
    errors = int(suite.get('errors')) + int(suite.get('failures'))
    for test in suite.iter('testcase'):
      basename = test.get('name')
      classname = test.get('classname')
      full_name = '{}.{}'.format(classname, basename)
      tm = 0.0
      if test.get('time') is None:
        logger.error('Junit test-case missing time field! {}'.format(full_name))
      else:
        try:
          tm = float(test.get('time'))
        except:
          logger.error('Junit test-case has malformed time field: {} ({})'.format(test.get('time'),
                                                                                  full_name))
      ## Successful tests are all the same.
      ## Each failing tests puts the text in its own unique element --
      ##   Tolstoy, if he wrote parsers for JUnit output
      if getAllText(test) != '':
        errors -= 1
        state = State.FAILURE
      else:
        state = State.SUCCESS
      yield TestCase(state=state,
                     full_name=full_name,
                     time=tm)
    if errors > 0:
      ## Oh, my! The heuristic for finding
      ## a failed test failed to work.
      ## Let's generate a failure just in case
      classname = suite.get('name')
      full_name = classname + '.DUMMY_TEST'
      yield TestCase(state=State.FAILURE,
                     full_name=full_name,
                     time=0.0)


def rfc7464_record_from_case(case):
  dct = {
    'state': 'success' if case.state == State.SUCCESS else 'failure',
    'full-name': case.full_name,
    'time': case.time,
  }
  return b'\x1e' + json.dumps(dct).encode('utf-8') + b'\n'


def find_true_failures(is_flake, cases, exc):
  failed, flaked = False, False
  for case in cases:
    if case.state == State.SUCCESS:
      continue
    if is_flake(case.full_name):
      print("FAILURE DETECTED: {} -- Ignoring as flake".format(case.full_name))
      flaked = True
      continue
    failed = True
  if failed or not flaked:
    raise exc


def get_test_cases(directory):
  blobs = itertools.imap(read_file, glob.glob(os.path.join(directory, '*.xml')))
  cases = itertools.chain.from_iterable(itertools.imap(parse_string, blobs))
  return cases


PARSER = argparse.ArgumentParser('Process JUnit report')
PARSER.add_argument('--output', help="Output file", required=True)
PARSER.add_argument('--dir', help="Directory with reports", required=True)
PARSER.add_argument('--flakes', help="Directory with flake indicators", required=True)


## Utility routines that are testable
def compose(f, g):
  return lambda x: f(g(x))


def flow_and_process(process, inputs):
  for piece in inputs:
    process(piece)
    yield piece


def read_file(fname):
  with open(fname) as input:
    return input.read()
## End utility routines


def main():
  logging.basicConfig()
  ns = PARSER.parse_args()
  cases = get_test_cases(ns.dir)
  is_flake = compose(os.path.exists, functools.partial(os.path.join, ns.flakes))
  with open(ns.output, 'w') as fp:
    process = compose(fp.write, rfc7464_record_from_case)
    exc = SystemExit('REAL FAILURE DETECTED')
    find_true_failures(is_flake, flow_and_process(process, cases), exc)

if __name__ == '__main__':
  main()
