# squarepants/src/main/python/squarepants/BUILD
# HANDWRITTEN

# default target provided as a convenience to reference all targets in this file
target(
  name = 'squarepants',
  dependencies = [
    ':pom_handlers',
    ':pom_to_build',
    ':pom_utils',
    ':target_template',
    ':build_component',
    ':generation_context',
  ]
)

python_library(
  name = 'build_component',
  sources = ['build_component.py'],
  dependencies = [
    ':pom_handlers',
    ':target_template',
    ':generation_context',
  ],
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
