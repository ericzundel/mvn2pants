# Tests for code in squarepants/src/main/python/squarepants/plugins/build_symbols/build_symbols.py
#
# Run with:
# ./pants test squarepants/src/test/python/squarepants_test/plugins:build_symbols

import unittest2 as unittest

from squarepants.plugins.build_symbols.build_symbols import BuildSymbols


class BuildSymbolsTest(unittest.TestCase):

  def test_arch(self):
    self.assertIn(BuildSymbols(None).arch, ('Darwin-i386', 'Linux-x86_64'))
