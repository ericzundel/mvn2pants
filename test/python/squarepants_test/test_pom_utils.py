# Tests for code in squarepants/src/main/python/squarepants/pom_utils.py
#
# Run with:
# ./pants goal test squarepants/src/test/python/squarepants:pom_utils

import logging
import unittest2 as unittest

from squarepants.pom_utils import PomUtils


# TODO(Eric Ayers) Refactor PomUtils so we can point it at a dummy directory of pom files
class PomUtilsTest(unittest.TestCase):

  # Test singletons
  def test_dependency_management_Finder(self):
    dmf = PomUtils.dependency_management_finder()
    self.assertIsNotNone(dmf)
    self.assertIs(dmf, PomUtils.dependency_management_finder()) # should be a singleton

  def test_pom_provides_target(self):
    ppt = PomUtils.pom_provides_target()
    self.assertIsNotNone(ppt)
    self.assertIs(ppt, PomUtils.pom_provides_target()) # should be a singleton

  def test_local_dep_targets(self):
    ldt = PomUtils.local_dep_targets()
    self.assertIsNotNone(ldt)
    self.assertIs(ldt,  PomUtils.local_dep_targets()) # should be a singleton

  def test_third_party_dep_targets(self):
    tpdt = PomUtils.third_party_dep_targets()
    self.assertIsNotNone(tpdt)
    self.assertIs(tpdt, PomUtils.third_party_dep_targets())

  def test_top_pom_content_handler(self):
    tpch = PomUtils.top_pom_content_handler()
    self.assertIsNotNone(tpch)
    self.assertIs(tpch, PomUtils.top_pom_content_handler())

  def test_external_protos_content_handler(self):
    epch = PomUtils.external_protos_content_handler()
    self.assertIsNotNone(epch)
    self.assertIs(epch, PomUtils.external_protos_content_handler())

  def test_get_modules(self):
    top_modules = PomUtils.top_pom_content_handler()
    self.assertIsNotNone(top_modules)

  def test_common_usage(self):
    # nothing really to test here, it just prints a message to sdout.
    PomUtils.common_usage()

  def test_parse_common_args(self):
    unprocessed = PomUtils.parse_common_args(['-ldebug', 'unused'])
    self.assertEquals(['unused'], unprocessed)
    self.assertTrue(logging.DEBUG, logging.getLogger().getEffectiveLevel())

  def test_is_local_dep(self):
    self.assertFalse(PomUtils.is_local_dep('bogus-dep'))

  def test_is_third_party_dep(self):
    self.assertFalse(PomUtils.is_third_party_dep('bogus-dep'))

  def test_is_external_dep(self):
    self.assertTrue(PomUtils.is_external_dep('bogus-dep'))
