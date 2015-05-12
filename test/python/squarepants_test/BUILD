# squarepants/src/test/python/squarepants/BUILD
# HANDWRITTEN

# Why is this directory named 'squarepants_test' instead of 'squarepants'?  The reason is that
# not all python tools work well when you have the same package in two places on PYTHONPATH,
# so the convention is to re-name the package were tests are to '<package>_test'

# Default target. Provided as a convenience to run all test targets in this directory
target(
  name = 'squarepants_test',
  dependencies = [
    ':common',
    ':pom_handlers',
    ':pom_properties',
    ':pom_to_build',
    ':pom_utils',
    ':target_template',
  ]
)

python_library(
  name = 'common',
  sources = [ '__init__.py', 'test_utils.py' ],
  dependencies = [
    'squarepants/src/main/python/squarepants:pom_handlers',
    'squarepants/src/main/python/squarepants:pom_utils',
  ],
)

python_tests(
  name = 'pom_handlers',
  sources = [ 'test_pom_handlers.py' ],
  dependencies = [
    ':common',
    'squarepants/src/main/python/squarepants:pom_handlers',
  ],
)

python_tests(
  name = 'pom_properties',
  sources = [ 'test_pom_properties.py' ],
  dependencies = [
    ':common',
    'squarepants/src/main/python/squarepants:pom_properties',
  ],
)

python_tests(
  name = 'pom_to_build',
  sources = [ 'test_pom_to_build.py' ],
  dependencies = [
    ':common',
    'squarepants/src/main/python/squarepants:pom_handlers',
    'squarepants/src/main/python/squarepants:pom_to_build',
    'squarepants/src/main/python/squarepants:pom_utils',
  ],
)

python_tests(
  name = 'pom_utils',
  sources = [ 'test_pom_utils.py' ],
  dependencies = [
    ':common',
    'squarepants/src/main/python/squarepants:pom_utils',
  ],
)

python_tests(
  name = 'target_template',
  sources = [ 'test_target_template.py' ],
  dependencies = [
    ':common',
    'squarepants/src/main/python/squarepants:target_template',
  ],
)
