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
  ]
)

python_library(
  name = 'pom_handlers',
  sources = ['pom_handlers.py'],
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
)
