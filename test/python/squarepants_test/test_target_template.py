# Tests for code in squarepants/src/main/python/squarepants/target_template.py
#
# Run with:
# ./pants goal test squarepants/src/test/python/squarepants:target_template

import unittest2 as unittest

from squarepants.target_template import Target


class TargetTemplateTest(unittest.TestCase):

  def setUp(self):
    super(TargetTemplateTest, self).setUp()

  def tearDown(self):
    Target.reset()
    super(TargetTemplateTest, self).tearDown()

  def test_simple(self):
    with self.assertRaises(Target.NoSuchTargetError):
      Target.get_template('foo')

    template = Target.create_template(
      'foo', ['var1:string', 'var2:raw', 'var3:list'],
      'var1 is {var1} var2 is {var2} var3 is {var3} var1 again is {var1}')

    self.assertEquals(template, Target.get_template('foo'))
    self.assertEquals("""
var1 is 'foo' var2 is bar var3 is [
    1,
    2
  ] var1 again is 'foo'
""",
                      template.format(var1='foo', var2='bar', var3=['1', '2']))

  def test_default_types(self):
    template = Target.create_template(
      'foo', ['name', 'sources', 'resources', 'dependencies', 'imports', 'var1:string'],
      'name={name} sources={sources} var1={var1} resources={resources} '
      'depencencies={dependencies} imports={imports}')
    result = template.format(name='n', sources=['s1', 's2'], resources=['r1', 'r2'],
                             dependencies=['d1', 'd2'], imports=['i1', 'i2'],
                             var1='v')
    self.assertEquals("""
name='n' sources=[
    s1,
    s2
  ] var1='v' resources=[
    r1,
    r2
  ] depencencies=[
    d1,
    d2
  ] imports=[
    i1,
    i2
  ]
""", result)

  def test_no_such_value(self):
    template = Target.create_template('foo', [], 'var1 is {var1}')
    with self.assertRaises(KeyError):
      template.format(var1='foo')
