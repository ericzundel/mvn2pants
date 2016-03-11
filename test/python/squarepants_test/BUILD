# squarepants/src/test/python/squarepants/BUILD
# HANDWRITTEN

# Why is this directory named 'squarepants_test' instead of 'squarepants'?  The reason is that
# not all python tools work well when you have the same package in two places on PYTHONPATH,
# so the convention is to re-name the package were tests are to '<package>_test'

# Default target. Provided as a convenience to run all test targets in this directory
target(
  name = 'squarepants_test',
  dependencies = [
    ':artifact_dependency_analysis',
    ':common',
    ':binary_utils',
    ':build_component',
    ':file_utils',
    ':generation_utils',
    ':generate_3rdparty',
    ':graph_util',
    ':junit_report',
    ':plugins',
    ':pom_handlers',
    ':pom_properties',
    ':pom_to_build',
    ':pom_utils',
    ':target_template',
    ':pants_integration',
  ],
)

target(
  name = 'plugins',
  dependencies = [
    'squarepants/src/test/python/squarepants_test/plugins',
  ],
)

python_tests(
  name = 'artifact_dependency_analysis',
  sources = ['test_artifact_dependency_analysis.py'],
  dependencies = [
    'squarepants/src/main/python/squarepants:generation_utils',
    'squarepants/src/main/python/squarepants:pom_handlers',
  ]
)

python_library(
  name = 'common',
  sources = [ '__init__.py', ],
  dependencies = [
    'squarepants/src/main/python/squarepants:pom_handlers',
    'squarepants/src/main/python/squarepants:pom_utils',
    'squarepants/src/main/python/squarepants:file_utils',
  ],
)

python_tests(
  name = 'binary_utils',
  sources = [ 'test_binary_utils.py' ],
  dependencies = [
    ':common',
    'squarepants/src/main/python/squarepants:binary_utils',
  ],
)

python_tests(
  name = 'build_component',
  sources = [ 'test_build_component.py' ],
  dependencies = [
    ':common',
    ':file_utils',
    'squarepants/src/main/python/squarepants:pom_file',
    'squarepants/src/main/python/squarepants:build_component',
  ],
)

python_tests(
  name = 'file_utils',
  sources = [ 'test_file_utils.py' ],
  dependencies = [
    'squarepants/src/main/python/squarepants:file_utils',
  ],
)

python_tests(
  name = 'generation_utils',
  sources = [ 'test_generation_utils.py' ],
  dependencies = [
    ':common',
    'squarepants/src/main/python/squarepants:generation_utils',
  ],
)

python_tests(
  name = 'graph_util',
  sources = [ 'test_graph_util.py' ],
  dependencies = [
    ':common',
    'squarepants/src/main/python/squarepants:graph_util',
  ],
)

python_tests(
  name = 'junit_report',
  sources = [ 'test_junit_report.py' ],
  dependencies = [
    ':common',
    'squarepants/src/main/python/squarepants:junit_report',
  ],
)

python_tests(
  name = 'pom_file',
  sources = [ 'test_pom_file.py' ],
  dependencies = [
    ':common',
    ':file_utils',
    'squarepants/src/main/python/squarepants:pom_file',
  ]
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

python_tests(
  name = 'generate_3rdparty',
  sources = [ 'test_generate_3rdparty.py' ],
  dependencies = [
    ':common',
    'squarepants/src/main/python/squarepants:generate_3rdparty',
  ],
)

python_library(
  name = 'integration_test_base',
  sources = [ 'integration_test_base.py' ],
  dependencies = [
    'squarepants/src/main/python/squarepants:file_utils',
    'squarepants/src/main/python/squarepants:binary_utils',
  ],
)

python_tests(
  name = 'pants_integration',
  sources = [ 'test_pants_integration.py' ],
  dependencies = [
    ':integration_test_base',
    'squarepants/src/main/python/squarepants:binary_utils',
  ],
  tags = {'integration'},
)
