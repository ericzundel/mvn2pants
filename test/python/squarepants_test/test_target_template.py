# Tests for code in squarepants/src/main/python/squarepants/target_template.py
#
# Run with:
# ./pants test squarepants/src/test/python/squarepants_test:target_template

import pytest
import unittest2 as unittest

from squarepants.target_template import Target


class TargetTemplateTest(unittest.TestCase):

  def setUp(self):
    self.maxDiff = None
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
    triple_quote_string = """
var1 is 'foo' var2 is bar var3 is [
    '1',
    '2'
  ] var1 again is 'foo'
"""
    self.assertEquals(triple_quote_string,
                      template.format(var1='foo', var2='bar', var3=['1', '2']))

  def test_default_types(self):
    template = Target.create_template(
      'foo', ['name', 'sources', 'resources', 'dependencies', 'imports', 'var1:string'],
      'name={name} sources={sources} var1={var1} resources={resources} '
      'depencencies={dependencies} imports={imports}')
    result = template.format(name='n', sources=['s1', 's2'], resources=['r1', 'r2'],
                             dependencies=['d1', 'd2'], imports=['i1', 'i2'],
                             var1='v')
    triple_quote_string = """
name='n' sources=[
    's1',
    's2'
  ] var1='v' resources=[
    'r1',
    'r2'
  ] depencencies=[
    'd1',
    'd2'
  ] imports=[
    'i1',
    'i2'
  ]
"""
    self.assertEquals(triple_quote_string, result)

  def test_no_such_value(self):
    template = Target.create_template('foo', [], 'var1 is {var1}')
    with self.assertRaises(KeyError):
      template.format(var1='foo')

  def test_optional_flag(self):
    template = Target.create_template('target',
                                      ['name:string', 'sources:list', 'dependencies:list:optional',
                                       'foobar:raw:optional'],
                                      'target(name={name}, sources={sources}, '
                                      'dependencies={dependencies}, foobar={foobar})')
    triple_quote_string = """
target(name='my name', sources=[
    'one.txt',
    'two.txt'
  ], foobar=True)
"""
    self.assertEquals(triple_quote_string, template.format(name='my name',
                                                           sources=['one.txt', 'two.txt'],
                                                           foobar=True))

    with self.assertRaises(Target.MissingTemplateArgumentError):
      template.format(name='my name', foobar=True)

  def test_collapsible_flag(self):
    template = Target.create_template('target',
                                      ['name:string',
                                       'collapsible_list:list:collapsible',
                                       'normal_list:list',],
                                      'target(name={name}, collapsible_list={collapsible_list}, '
                                      'normal_list={normal_list})')
    triple_quote_string = """
target(name='my name', collapsible_list=['one.txt'], normal_list=[
    ':foobar'
  ])
"""
    self.assertEquals(triple_quote_string, template.format(name='my name',
                                                           collapsible_list=['one.txt'],
                                                           normal_list=[':foobar']))

  def test_sorted_flag(self):
    template = Target.create_template('target', ['name:string', 'sources:list:sorted'],
                                      'target(name={name}, sources={sources})')
    triple_quote_string = """
target(name='my name', sources=[
    'a.txt',
    'b.txt',
    'one.txt',
    'two.txt',
    'zebra.txt'
  ])
"""
    self.assertEquals(triple_quote_string, template.format(name='my name',
                                                           sources=['one.txt', 'two.txt',
                                                                    'a.txt', 'b.txt', 'zebra.txt']))

  def test_symbol_substitution(self):
    template = Target.create_template('target', ['name:string', 'sources:list'],
                                      'target(name={name}, sources={sources},\n)')
    triple_quote_string = """
target(name='my foobar', sources=[
    '${symbol-not-present}',
    'foobar.txt',
    'hello.txt',
    'potato.txt'
  ],
)
"""
    formatted_target = template.format(name='my ${name}',
      sources=[
       '${symbol-not-present}',
       '${name}.txt',
       '${greeting.file}',
       '${vegetable.file}',
      ],
      symbols={
       'name': 'foobar',
       'greeting.file': 'hello.txt',
       'vegetable.file': 'potato.txt',
      },
    )
    self.assertEquals(triple_quote_string, formatted_target)

  def test_format_list(self):
    result =  Target.jar_library._format_list(
      "foo",
      ["jar(org='com.example',name='a',rev='1',excludes=[exclude(org='bar', name='b'),exclude(org='bar', name='c'),],)"])

    self.assertEquals("""
[
    jar(org='com.example',name='a',rev='1',excludes=[exclude(org='bar', name='b'),exclude(org='bar', name='c'),],)
  ]
""".strip(), result)

  def test_format_item(self):
    result =  Target.jar_library._format_item(
      "jar(org='com.example', name='a', rev='1', excludes=[ exclude(org='bar', name='b'), exclude(org='bar', name='c'),],)")

    self.assertEquals("""
 jar(org='com.example', name='a', rev='1', excludes=[ exclude(org='bar', name='b'), exclude(org='bar', name='c'),],)
        """.strip(), result)

  # This test demonstrates a problem when using the format() method with some types of values.
  # This is why we don't use Target.jar_library.format() in generate_third_party.py
  @pytest.mark.xfail
  def test_jar_library(self):
    jar="""sjar(org='com.example', name='a', rev='0.8.0',
  excludes=[
      exclude(org='bar', name='b'),
      exclude(org='bar', name='c'),
  ],
)"""
    jar_library = Target.jar_library.format(name="foo", jars=[jar,])

    triple_quote_string="""
jar_library(name='foo',
  jars = [
    sjar(org='com.example', name='a', rev='0.8.0',
      excludes=[
          exclude(org='bar', name='b'),
          exclude(org='bar', name='c'),
      ],
    )
  ],
)
"""
    self.assertEquals(triple_quote_string, jar_library)
