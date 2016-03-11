# squarepants/src/main/python/squarepants/BUILD
# HANDWRITTEN

# default target provided as a convenience to reference all targets in this file
target(
  name = 'squarepants',
  dependencies = [
    ':graph_util',
    ':pom_handlers',
    ':pom_to_build',
    ':pom_utils',
    ':target_template',
    ':build_component',
    ':generation_context',
    ':generate_3rdparty',
    ':junit_report',
    ':junit_report_run',
    ':export_test_data_run',
    ':patchy_pants',
  ]
)

python_library(
  name='binary_utils',
  sources = ['binary_utils.py'],
  dependencies = [
    ':file_utils',
  ],
)

python_library(
  name = 'build_component',
  sources = ['build_component.py'],
  dependencies = [
    ':file_utils',
    ':pom_handlers',
    ':target_template',
    ':generation_context',
  ],
)

python_library(
  name='file_utils',
  sources = ['file_utils.py'],
)

python_library(
  name='generation_context',
  sources = ['generation_context.py'],
  dependencies = [],
)

python_library(
  name='generation_utils',
  sources = ['generation_utils.py'],
  dependencies = [],
)

python_library(
  name='junit_report',
  sources = ['junit_report.py'],
  dependencies = [],
)

python_binary(
  name='junit_report_run',
  entry_point= 'squarepants.junit_report:main',
  dependencies = [
    ':junit_report',
  ],
)

python_library(
  name='export_test_data',
  sources = ['export_test_data.py'],
  dependencies = [
    ':junit_report',
  ],
)

python_binary(
  name='export_test_data_run',
  entry_point= 'squarepants.export_test_data:main',
  dependencies = [
    ':export_test_data',
  ],
)

python_library(
  name='patchy_pants',
  sources = ['patchy_pants.py'],
  dependencies = [
    ':binary_utils',
  ],
)

python_library(
  name = 'pom_file',
  sources = ['pom_file.py'],
  dependencies = [
    ':generation_context',
    ':pom_handlers',
    ':pom_utils',
  ],
)

python_library(
  name = 'pom_handlers',
  sources = ['pom_handlers.py'],
  dependencies = [
    ':generation_utils',
  ],
)

python_binary(
  name = 'pom_properties',
  source = 'pom_properties.py',
  dependencies = [
    ':pom_handlers',
  ],
)

python_binary(
  name = 'pom_to_build',
  source = 'pom_to_build.py',
  dependencies = [
    ':pom_handlers',
    ':pom_utils',
    ':target_template',
    ':build_component',
    ':generation_context',
  ]
)

python_library(
  name = 'pom_utils',
  sources = ['pom_utils.py'],
  dependencies = [
    ':pom_handlers',
  ]
)

python_library(
  name = 'target_template',
  sources = ['target_template.py'],
  dependencies = [
    ':generation_utils',
  ],
)

python_library(
  name = 'generate_3rdparty',
  sources = ['generate_3rdparty.py'],
  dependencies = [
    ':pom_file',
    ':pom_utils',
    ':target_template',
  ],
)

python_library(
  name = 'graph_util',
  sources = ['graph_util.py'],
)
