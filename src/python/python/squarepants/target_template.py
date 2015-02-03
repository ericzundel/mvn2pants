import re

class Target(object):
  """Class to organize target template instances for generated BUILD files.

  To add a new target, created it as a class variable (see existing templates below), then add it to
  the list in get_template at the bottom so that it can be properly discovered.
  """

  class NoSuchTargetError(Exception):
    def __init__(self, name):
      super(Target.NoSuchTargetError, self).__init__(
          'Target "{name}" does not exist.'.format(name=name))

  class NoSuchValueType(Exception):
    pass

  class Template(object):

    def __init__(self, name, params, template):
      """Creates a new target template, which can be used to generate code for targets in BUILD
      files using the format() method.

      :param name: The target type (eg, 'java_library')
      :param params: The list of parameters which can be injected into this template, optionally
        with an associated type declared by following with :type. Eg,  'sources:list' would create a
        parameter with the name 'sources' and the type 'list'. Understood types currently include
        'raw', 'string', and 'list'. These types affect how the parameters are ultimately formatted
        when data is injected into this template. When the type is unspecified, it defaults to the
        values defined in DEFAULT_TYPES, or 'raw' if not present.
      :param template: The code for the actual template string, with parameter names specified in
        the same style used for str.format, eg 'Hello {person_name}.'. The parameters included in
        the template code must exactly match those defined in params, or an error will be raised
        when format() is invoked.
      """
      self.name = name
      self.template = template

      DEFAULT_TYPES = {
        'name':'string',
        'sources':'list',
        'resources':'list',
        'dependencies':'list',
        'imports':'list',
      }
      self.params = {}
      for param in params:
        if ':' in param:
          name = param[:param.find(':')]
          kind = param[param.find(':')+1:]
          self.params[name] = kind
        elif param in DEFAULT_TYPES:
          self.params[param] = DEFAULT_TYPES[param]
        else:
          self.params[param] = 'raw'

    def _extract(self, param, args):
      value = args.get(param) or ''
      kind = self.params[param]
      if kind == 'raw':
        return value
      # Value that can be matched properly by regexes.
      re_value = str(value).replace('\n', ' ')
      if kind == 'string':
        if not value:
          return "''"
        if re.match(r'^\s*(["{quote}]).*?[^\\]\1\s*$'.format(quote="'"), re_value):
          return value
        return "'%s'" % value
      if kind == 'list':
        if not value:
          return '[]'
        if isinstance(value, str):
          if '(' in value:
            return value # Hack for globs()
          value = [value,]
        return '[\n    %s\n  ]' % ',\n    '.join('%s' % s for s in value)
      raise NoSuchValueType('No such value type "{kind}".'.format(kind=kind))

    def format(self, **kwargs):
      """Behaves somewhat like str.format, creating a 'concrete' by injecting relevant parameters
      into this template.

      Parameters which were not specified when this template was initialized are ignored.
      Unspecified parameters will default to reasonable values based on their types (eg, [] or '').
      The parameters are formatted according to their type (specified as 'name:type', defaulting to
      their value in DEFAULT_TYPES or 'raw').

      This means parameters which are lists should be passed in as actual list objects, not as
      strings. If a string is passed in, it will be inserted literally, which is useful for
      specifying things like "globs('*.java')" rather than an explicit list of sources.

      Parameters which are strings will be automatically wrapped in single-quotes if they aren't
      already (eg, '"hello"' will become "hello" in the output file, and 'hello' will become
      'hello'). Raw parameters will be inserted literally, so the string 'hello' will just become
      hello in the output.

      Example usage: Target.jar_library.format(name='lib', jars=["'3rdparty:fake-library'",],)

      :returns: a string containing the target, which can be inserted directly into a BUILD file.
      """
      relevant = {}
      for param in self.params.keys():
        relevant[param] = self._extract(param, kwargs)
      return '\n%s\n' % self.template.format(**relevant)

  _ALL_TEMPLATES = {}
  @classmethod
  def create_template(cls, *args, **kwargs):
    template = cls.Template(*args, **kwargs)
    cls._ALL_TEMPLATES[template.name] = template
    return template

  @classmethod
  def get_template(cls, name):
    if name in cls._ALL_TEMPLATES:
      return cls._ALL_TEMPLATES[name]
    raise Target.NoSuchTargetError(name)


Target.annotation_processor = Target.create_template('annotation_processor',
      ['name', 'sources', 'resources', 'dependencies'],
'''annotation_processor(name={name},
  sources = {sources},
  resources = {resources},
  dependencies = {dependencies},
)''')

Target.dependencies = Target.create_template('dependencies', ['name', 'dependencies',],
'''target(name={name},
  dependencies = {dependencies},
)''')

Target.jar_library = Target.create_template('jar_library', ['name', 'jars:list',],
'''jar_library(name={name},
  jars = {jars},
)''')

Target.java_library = Target.create_template('java_library', ['name', 'sources', 'resources',
                                                              'dependencies',
                                                              'groupId', 'artifactId'],
'''java_library(name={name},
  sources = {sources},
  resources = {resources},
  dependencies = {dependencies},
  provides = artifact(org='{groupId}',
                      name='{artifactId}',
                      repo=square,),  # see squarepants/plugin/repo/register.py
)''')

Target.java_protobuf_library = Target.create_template('java_protobuf_library',
      ['name', 'sources', 'dependencies', 'imports',],
'''java_protobuf_library(name={name},
  sources = {sources},
  imports = {imports},
  dependencies = {dependencies},
)''')

Target.java_wire_library = Target.create_template('java_wire_library',
     ['name', 'sources', 'dependencies'],
'''java_wire_library(name={name},
  sources = {sources},
  dependencies = {dependencies},
)''')

Target.junit_tests = Target.create_template('junit_tests', ['name', 'sources', 'dependencies',],
'''junit_tests(name={name},
   # TODO: Ideally, sources between :test and :lib should not intersect
  sources = {sources},
  dependencies = {dependencies},
)''')


Target.jvm_binary = Target.create_template('jvm_binary',
      ['name', 'main:string', 'basename:string', 'main_source', 'dependencies',],
'''jvm_binary(name={name},
  main = {main},
  basename= {basename},
  #source = 'src/main/java/{main_source}.java',
  dependencies = {dependencies},
)''')

Target.resources = Target.create_template('resources',
      ['name', 'sources', 'dependencies'],
'''resources(name={name},
  sources = {sources},
  dependencies = {dependencies},
)''')

Target.unpacked_jars = Target.create_template('unpacked_jars',
      ['name', 'libraries', 'include_patterns'],
'''unpacked_jars(name={name},
  libraries={libraries},
  include_patterns={include_patterns},
)''')

