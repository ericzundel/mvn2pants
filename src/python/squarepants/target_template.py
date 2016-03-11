import re
from collections import defaultdict
from textwrap import dedent

from generation_utils import GenerationUtils

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

  class MissingTemplateArgumentError(Exception):
    pass

  class Template(object):

    def __init__(self, name, params, template, blank_lines=True):
      """Creates a new target template, which can be used to generate code for targets in BUILD
      files using the format() method.

      :param name: The target type (eg, 'java_library')
      :param params: The list of parameters which can be injected into this template, optionally
        with an associated type declared by following with :type. Eg,  'sources:list' would create a
        parameter with the name 'sources' and the type 'list'. Understood types currently include
        'raw', 'string', and 'list'. These types affect how the parameters are ultimately formatted
        when data is injected into this template. When the type is unspecified, it defaults to the
        values defined in DEFAULT_TYPES, or 'raw' if not present.

        Parameters also have a notion of extra flags, which basically act like type modifiers.
        These are specified in the following format: param_name:type:flags1:flag2:more_flags.

        Supported flags include:
          collapsible - when applied to a list, the list will be made a one-liner if it only has one
            argument.
          optional - if not specified (or specified as None), the argument will be entirely removed
            from the formatted output. This is done by splitting the output at the ',' character,
            and removing and entry which has optional parameters that are None, then joining it
            back together before returning the formatted result.
          sorted - when applied to a list, the list will be sorted() before formatting.
          emptyable - will format as the empty string rather than {} or [] for empty lists and
            dicts.
      :param template: The code for the actual template string, with parameter names specified in
        the same style used for str.format, eg 'Hello {person_name}.'. The parameters included in
        the template code must exactly match those defined in params, or an error will be raised
        when format() is invoked.
      :param blank_lines: Whether to pad the formatted output string with blank lines.
      """
      self.name = name
      self.template = template
      self.blank_lines = blank_lines

      DEFAULT_TYPES = {
        'name':'string',
        'sources':'list',
        'resources':'list',
        'dependencies':'list',
        'imports':'list',
        'platform':'string',
      }

      self.flags = defaultdict(set)
      self.flags.update({
        'sources': {'collapsible'},
        'platform':'optional',
      })

      self.params = {}
      for param in params:
        if ':' in param:
          parts = param.split(':')
          name, kind = parts[:2]
          self.params[name] = kind
          flags = set(parts[2:])
          self.flags[name] = flags
        elif param in DEFAULT_TYPES:
          self.params[param] = DEFAULT_TYPES[param]
        else:
          self.params[param] = 'raw'

    def _indent_text(self, text, indent=2):
      lines = str(text).split('\n')
      lines = ['{0}{1}'.format(' '*indent, line).rstrip() for line in lines]
      return '\n'.join(lines)

    def _format_item(self, item):
      string_pattern = re.compile(r"^(?P<quote>'?)(?P<content>.*?)(?P=quote)(?P<comma>,?)$")
      object_pattern = re.compile(r'^(?P<content>[a-zA-Z_$0-9]+[(].*?[)].*?)(,?)$',
                                  re.DOTALL | re.MULTILINE)
      original = item
      item = item.strip()
      match = re.match(object_pattern, item)
      if match:
        # Handle things like jar() objects.
        return match.group('content')
      match = re.match(string_pattern, item)
      if not match:
        print('  Warning: Unrecognized item format, assuming raw object: {}.'.format(item))
        return original
      return "'{}'".format(match.group('content'))

    def _format_dict(self, param, data):
      if not data:
        return '{}'
      items = [
        (self._format_item(key), self._format_item(value)) for (key, value) in data.items()
      ]
      if 'sorted' in self.flags[param]:
        items = sorted(items)
      return '{{{}\n  }}'.format(''.join('\n    {}: {},'.format(key, val) for (key, val) in items))

    def _format_list(self, param, items):
      if not items:
        return '[]'
      items = [self._format_item(item) for item in items if item]
      if len(items) == 1 and 'collapsible' in self.flags[param]:
        return '[{}]'.format(items[0])
      if 'sorted' in self.flags[param]:
        items = sorted(items)

      return '[{}\n  ]'.format(','.join('\n{}'.format(self._indent_text(item, indent=4))
                                        for item in items))

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
        return "'{0}'".format(value)
      if 'emptyable' in self.flags[param] and not value:
        return ''
      if kind == 'list':
        if not value:
          return '[]'
        if isinstance(value, str):
          if '(' in value:
            return value # Hack for globs() and jar().
          value = [value,]
        return self._format_list(param, value)
      if kind == 'dict':
        if not value:
          return '{}'
        if hasattr(value, '__getitem__') and hasattr(value, 'items'):
          return self._format_dict(param, value)
        if isinstance(value, str):
          return value
        raise ValueError('Illegally formatted dict argument: {} = {}.'.format(param, value))

      raise Target.NoSuchValueType('No such value type "{kind}".'.format(kind=kind))

    def _is_optional(self, param):
      return 'optional' in self.flags[param]

    def _strip_optional(self, **kwargs):
      parts = self.template.split(',')
      for param in self.params:
        if self._is_optional(param):
          if param not in kwargs or kwargs[param] is None:
            parts = [part for part in parts if '{%s}'%param not in part]
        elif param not in kwargs:
          completed = kwargs
          completed.update({ p: 'MISSING VALUE!' for p in self.params if p not in kwargs })
          args_text = self.format(skip_missing_check=True, **completed)
          raise Target.MissingTemplateArgumentError('Missing argument "{}" for {}().\n{}'
                                                    .format(param, self.name, args_text))
      return ','.join(parts)

    def format(self, symbols=None, file_name=None, skip_missing_check=False, **kwargs):
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

      :param dict symbols: If present, replaces all instances of ${key} with symbols[key]
        in the formatted output string.
      :param string file_name: Optional string used to format error messages if something goes
        wrong.
      :param skip_missing_check: If true, will skip the normal check for missing arguments.
      :returns: a string containing the target, which can be inserted directly into a BUILD file.
      """
      if symbols:

        def substitute(value):
          return GenerationUtils.symbol_substitution(symbols, value, symbols_name=file_name)

        for key, value in list(kwargs.items()):
          if not value:
            continue
          if any(isinstance(value, t) for t in (list,set,tuple,)):
            kwargs[key] = [substitute(v) for v in value]
          elif hasattr(value, '__getitem__') and hasattr(value, 'items'):
            kwargs[key] = { k: substitute(v) for k,v in value.items() }
          else:
            kwargs[key] = substitute(value)
      relevant = {}
      for param in self.params.keys():
        relevant[param] = self._extract(param, kwargs)
      template = self._strip_optional(**kwargs) if not skip_missing_check else self.template
      text = template.format(**relevant)
      if not self.blank_lines:
        return text
      return '\n{0}\n'.format(text)

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

  @classmethod
  def reset(cls):
    """Clear out existing templates.

    Intended for testing.
    """
    cls._ALL_TEMPLATES = {}


Target.annotation_processor = Target.create_template('annotation_processor',
      ['name', 'sources', 'resources', 'dependencies', 'platform',],
'''annotation_processor(name={name},
  sources = {sources},
  resources = {resources},
  dependencies = {dependencies},
  platform = {platform},
)''')

Target.dependencies = Target.create_template('dependencies', ['name', 'dependencies',],
'''target(name={name},
  dependencies = {dependencies},
)''')

Target.fingerprint = Target.create_template('fingerprint', ['name', 'sources', 'dependencies'],
dedent('''
  # This target's sole purpose is just to invalidate the cache if loose files (eg app-manifest.yaml)
  # for the jvm_binary change.
  fingerprint(name={name},
    sources = {sources},
    dependencies = {dependencies},
  )
''').strip())

Target.placeholder = Target.create_template('placeholder', ['name',],
'''target(name={name})
''')

Target.jar_library = Target.create_template('jar_library', ['name', 'jars:list:sorted',],
'''jar_library(name={name},
  jars = {jars},
)''')

Target.java_library = Target.create_template('java_library', ['name', 'sources', 'resources',
                                                              'dependencies',
                                                              'groupId', 'artifactId',
                                                              'platform',],
'''java_library(name={name},
  sources = {sources},
  resources = {resources},
  dependencies = {dependencies},
  platform = {platform},
  provides = artifact(org='{groupId}',
                      name='{artifactId}',
                      repo=square,),  # see squarepants/plugin/repo/register.py
)''')

Target.java_protobuf_library = Target.create_template('java_protobuf_library',
      ['name', 'sources', 'dependencies', 'imports', 'platform',  'groupId', 'artifactId'],
'''java_protobuf_library(name={name},
  sources = {sources},
  imports = {imports},
  dependencies = {dependencies},
  platform = {platform},
  provides = artifact(org='{groupId}',
                      name='{artifactId}',
                      repo=square,),  # see squarepants/plugin/repo/register.py
)''')

Target.java_wire_library = Target.create_template('java_wire_library',
     ['name', 'sources', 'dependencies', 'roots:list', 'service_factory:string',
      'enum_options:list:optional', 'registry_class:string', 'no_options:raw:optional',
      'platform'],
'''java_wire_library(name={name},
  sources = {sources},
  dependencies = {dependencies},
  roots = {roots},
  service_factory = {service_factory},
  enum_options = {enum_options},
  no_options = {no_options},
  registry_class = {registry_class},
  platform = {platform},
)''')

Target.jvm_prep_command = Target.create_template('jvm_prep_command',
  ['name', 'mainclass:string', 'goal:string:optional', 'args:list:optional',
   'jvm_options:list:optional', 'dependencies:list'], dedent('''
    jvm_prep_command(name={name},
      goal={goal},
      mainclass={mainclass},
      args={args},
      jvm_options={jvm_options},
      dependencies={dependencies},
    )
  '''))

Target.junit_tests = Target.create_template('junit_tests',
     ['name', 'sources', 'cwd:string', 'dependencies', 'platform', 'tags:list:optional',
      'extra_env_vars:dict:optional', 'extra_jvm_options:list:optional'],
'''junit_tests(name={name},
  # TODO: Ideally, sources between :test, :integration-tests  and :lib should not intersect
  sources = {sources},
  cwd = {cwd},
  tags = {tags},
  dependencies = {dependencies},
  platform = {platform},
  extra_env_vars = {extra_env_vars},
  extra_jvm_options = {extra_jvm_options},
)''')


Target.jvm_binary = Target.create_template('jvm_binary',
      ['name', 'main:string', 'basename:string', 'dependencies', 'manifest_entries:dict:emptyable',
       'deploy_excludes:list:optional', 'platform', 'shading_rules:list:optional'],
'''jvm_binary(name={name},
  main = {main},
  basename= {basename},
  dependencies = {dependencies},
  manifest_entries = square_manifest({manifest_entries}),
  deploy_excludes = {deploy_excludes},
  platform = {platform},
  shading_rules = {shading_rules},
)''')

Target.resources = Target.create_template('resources',
      ['name', 'sources', 'dependencies:list:optional'],
'''resources(name={name},
  sources = {sources},
  dependencies = {dependencies},
)''')

Target.signed_jars = Target.create_template('signed_jars',
    ['name', 'dependencies', 'strip_version:raw:optional'],
'''signed_jars(name={name},
  dependencies={dependencies},
  strip_version={strip_version},
)''')

Target.unpacked_jars = Target.create_template('unpacked_jars',
      ['name', 'libraries:list', 'include_patterns:list', 'exclude_patterns:list'],
'''unpacked_jars(name={name},
  libraries = {libraries},
  include_patterns = {include_patterns},
  exclude_patterns = {exclude_patterns},
)''')

Target.jar = Target.create_template('jar',
    ['org:string', 'name:string', 'rev:string', 'force:raw:optional', 'excludes:list:optional',
     'mutable:raw:optional', 'artifacts:list:optional', 'ext:string:optional',
     'url:string:optional', 'classifier:string:optional', 'apidocs:string:optional',
     'type_:string:optional', 'intransitive:raw:optional',],
'''sjar(org={org}, name={name}, rev={rev}, force={force}, mutable={mutable}, ext={ext}, \
classifier={classifier}, ext={type_}, intransitive={intransitive},
    url={url},
    apidocs={apidocs},
    artifacts={artifacts},
    excludes={excludes},)
'''.strip(), blank_lines=False)

Target.sjar = Target.create_template('sjar',
    ['org:string', 'name:string', 'rev:string', 'force:raw:optional', 'excludes:list:optional',
     'mutable:raw:optional', 'artifacts:list:optional', 'ext:string:optional',
     'url:string:optional', 'classifier:string:optional', 'apidocs:string:optional',
     'type_:string:optional', 'intransitive:raw:optional',],
'''sjar(org={org}, name={name}, rev={rev}, mutable={mutable}, ext={ext}, \
classifier={classifier}, ext={type_}, intransitive={intransitive},
    url={url},
    force={force},
    apidocs={apidocs},
    artifacts={artifacts},
    excludes={excludes},)
'''.strip(), blank_lines=False)

Target.wire_proto_path = Target.create_template('wire_proto_path',
    ['name', 'sources', 'dependencies'], dedent('''
      wire_proto_path(name={name},
        sources={sources},
        dependencies={dependencies},
      )
    ''').strip())
