import logging
import re
from textwrap import dedent


logger = logging.getLogger(__name__)


class GenerationUtils(object):
  """Static utility methods for BUILD file generation."""

  class MissingSymbolError(Exception):
    """Exception thrown when a symbol is not defined for substitution."""

    def __init__(self, symbol, dictionary):
      super(GenerationUtils.MissingSymbolError, self).__init__('Symbol "{}" not found in {}.'
                                                               .format(symbol, dictionary))

  @classmethod
  def symbol_substitution(cls, symbols, string, max_substitutions=100, symbols_name=None,
                          fail_on_missing=False):
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
    :param bool fail_on_missing: if True, raise an exception when a missing symbol is detected.
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
          if fail_on_missing:
            raise cls.MissingSymbolError(matched_name, symbols_name)
          logger.warn('  Warning: property "{}" not found in {}.'
                      .format(matched_name, symbols_name))
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

  @classmethod
  def autoindent(cls, text, preserve_block_indentation=True, adaptive=False, indent_size=2,
                 force_linebreaks_after=None):
    """Reformats a block of code (eg a build target) to be nicely indented.

    First, all leading and trailing whitespace is stripped off each line. Then each line is
    processed in sequence, with the grouping symbols found in one line determining the indentation
    level of the next line.

    The indentation logic increases the indentation level whenever it sees a '(', '[', or '{', and
    decreases it whenever it finds a matching closing symbol, using a stack. Symbols in quotation
    marks (single or double quotes) are ignored.

    Normally the indentation is simple incremented by `indent_size` each time an opening grouping
    symbol is read, however in an optional `adaptive` mode the indent may be set to the string
    position immediately after the grouping symbol, if the grouping symbol is not the last thing in
    the line. This is easiest to show with an example:

    Input:
      jar_library(name='foobar',
      jars=[
      jar(org='com.squareup',
      name='foobar',
      rev='1.0'),
      ],
      )

    Default output:
      jar_library(name='foobar',
        jars=[
          jar(org='com.squareup',
            name='foobar',
            rev='1.0'),
        ],
      )

    "Adaptive" output:
      jar_library(name='foobar',
                  jars=[
                    jar(org='com.squareup',
                        name='foobar',
                        rev='1.0'),
                  ],
      )

    This is useful for lining up arguments or lists, when the first element of the list is on the
    same line as the opening grouping symbol.

    :param string text: The block of text to format.
    :param bool preserve_block_indentation: If true, the initial indentation of the whole block
      (computed as the minimum number of leading spaces over all the lines in the block of text)
      will be retained, and the auto-indentation will only add to it.
    :param bool adaptive: Described with detailed examples above; essentially whether the algorithm
      attempts to keep keyword arguments and list items lined up if the first element is on the same
      line as the opening symbol.
    :param int indent_size: Amount to increment indentation at each opening symbol, defaults to 2.
    :param iterable force_linebreaks_after: An optional set of symbols to force line breaks after if
      they where not already present. This may be useful if you want a linebreak after every comma,
      or after every opening parenthesis, for example.
    :return: The reindented text.
    :rtype: string
    """
    force_linebreaks_after = set(force_linebreaks_after or ())
    block_indent = 0
    if preserve_block_indentation:
      first_line = text.split('\n', 1)[0]
      lines = dedent(text).split('\n')
      block_indent = len(first_line) - len(lines[0])
    else:
      lines = text.split('\n')

    if force_linebreaks_after:
      broken_lines = []
      current_line = []
      for index, char in enumerate(text):
        if char == '\n':
          broken_lines.append(current_line)
          current_line = []
        elif char in force_linebreaks_after and (index == len(text)-1 or text[index+1] != '\n'):
          current_line.append(char)
          broken_lines.append(current_line)
          current_line = []
        else:
          current_line.append(char)
      if current_line:
        broken_lines.append(current_line)
      lines = [''.join(chars) for chars in broken_lines]

    lines = [line.strip() for line in lines]
    open_close = {
      '{': '}',
      '[': ']',
      '(': ')',
      '"': '"',
      "'": "'",
    }
    nestable = set('{[(')
    buffer = []
    # Stack of (OpenSymbol, Indentation) tuples.
    stack = []

    def get_indent():
      return stack[-1][1] if stack else 0

    for line_no, line in enumerate(lines):
      if line_no > 0:
        buffer.append('\n')
      skip_next = False
      for index, char in enumerate(line):
        opener = stack[-1][0] if stack else None
        closer = open_close[opener] if opener else None
        if not skip_next and char == closer:
          stack.pop()
        if index == 0:
          buffer.append(' '*(block_indent + get_indent()))
        buffer.append(char)
        if not skip_next and char in open_close and (not opener or opener in nestable):
          indent_increase = index+1 if adaptive and index != len(line)-1 else indent_size
          stack.append((char, get_indent() + indent_increase))
        if opener and opener in '"\'' and char == '\\':
          skip_next = True
        else:
          skip_next = False

    return ''.join(buffer)

