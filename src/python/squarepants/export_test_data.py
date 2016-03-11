#!/usr/bin/env python2.7
#
# Called from script/ci to analyze the test failures and timing data in the .xml files.
#
# Most of the actual functionality was implemented by Moshe in junit_report.py.

from __future__ import unicode_literals, print_function

import argparse
import json
from squarepants.junit_report import get_test_cases, State


PARSER = argparse.ArgumentParser('Convert JUnit XML reports to universal json format.')
PARSER.add_argument('--output', help="Output file", required=True)
PARSER.add_argument('--dir', help="Directory with reports", required=True)


def case_to_json_dict(case):
  # The repo, sha, build, shard, and attempt are acquired from other sources.
  # Project might be determinable from here, but it looks like the pants output assumes test class
  # names are unique (which is not necessarily the case for java tests), so it isn't relevant right
  # now.
  return {
    'test': case.full_name,
    'status': 'pass' if case.state == State.SUCCESS else 'fail',
    'durationMillis': round(case.time * 1000)
  }


def main():
  ns = PARSER.parse_args()
  cases = get_test_cases(ns.dir)
  with open(ns.output, 'w') as fp:
    fp.write(json.dumps(map(case_to_json_dict, cases)))

if __name__ == '__main__':
  main()
