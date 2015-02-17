# squarepants/src/test/python/squarepants/BUILD
# HANDWRITTEN

# Convenience target to run all test targets in this directory
python_test_suite(
  name='squarepants',
  dependencies=[
    ':pom_handlers',
  ]
)

python_tests(
  name='pom_handlers',
  sources=['test_pom_handlers.py'],
  dependencies=[
    'squarepants/src/main/python/squarepants:pom_handlers',
  ]
)
