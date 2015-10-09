import re

class GenerationUtils(object):
  """Static utility methods for BUILD file generation."""

  @classmethod
  def symbol_substitution(cls, symbols, string, max_substitutions=100, symbols_name=None):
    """Performs symbol substitution on the given string, using symbols dict.

    In pseudo-code, does:

      while max_substitutions > 0:
        for key, value in symbols.items():
          symbols = symbols.replace(key, value)
          max_substitutions -= 1
          if max_substitutions <= 0:
            break

    :param dict symbols: the dictionary of symbols to replace.
    :param string: the string to perform symbol substitution on.
    :param max_substitutions: the maximum number of substitutions to perform. This is a limit on
      the number of symbols in a block of text that will be substituted, and also a limit on how
      deep recursive substitutions can go. (Recursive substitutions being when a symbol produces
      one or more new symbols, that in turn need to be substituted).
    :param string symbols_name: how to refer to this particular set of symbols if something goes
      wrong.
    """
    string = str(string)
    pattern = re.compile(r'[$][{]([^{}]*?)[}]')
    for iteration in range(max_substitutions):
      match = pattern.search(string)
      if not match:
        break
      matched_name = match.group(1)
      if matched_name not in symbols:
        if symbols_name:
          print('  Warning: property "{}" not found in {}.'.format(matched_name, symbols_name))
        break
      string = '{}{}{}'.format(
        string[:match.start()],
        symbols[matched_name],
        string[match.end():]
      )
    return string

  @classmethod
  def symbol_substitution_on_dicts(cls, symbols, dict_list, **kwargs):
    new_dicts = []
    for index, old_dict in enumerate(dict_list):
      new_dict = {}
      for key, value in old_dict.items():
        if isinstance(value, str) or isinstance(value, unicode):
          value = cls.symbol_substitution(symbols, value, **kwargs)
        new_dict[key] = value
      new_dicts.append(new_dict)
    return new_dicts
