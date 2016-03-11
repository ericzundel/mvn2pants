# squarepants/src/test/python/squarepants_test/plugins/BUILD
# HANDWRITTEN

# Default target. Provided as a convenience to run all test targets in this directory

target(name='plugins',
  dependencies = [
    ':build_symbols',
    ':fingerprint_integration',
    ':idea_gen',
    ':idea_gen_xml',
    ':link_resources_jars',
    ':link_resources_jars_integration',
    ':sake_wire_codegen',
    ':staging_build',
    ':unpack_archives',
  ]
)

resources(name='test_data',
  sources=rglobs('test_data/*'),
)

python_requirements('requirements.txt')

target(name='common',
  dependencies = [
    ':test_data',
    'squarepants/src/test/python/squarepants_test:common',
  ],
)

python_tests(name='build_symbols',
  sources = [ 'test_build_symbols.py' ],
  dependencies = [
    ':common',
    'squarepants/src/main/python/squarepants/plugins/build_symbols',
    ':pantsbuild.pants.testinfra',
  ],
)

python_tests(name='fingerprint_integration',
  sources = ['test_fingerprint_integration.py'],
  dependencies = [
    'squarepants/src/main/python/squarepants:file_utils',
    'squarepants/src/test/python/squarepants_test:integration_test_base',
  ],
  tags = {'integration'},
)

python_tests(name='idea_gen',
  sources = [ 'test_idea_gen.py' ],
  dependencies = [
    ':common',
    'squarepants/src/main/python/squarepants/plugins/square_idea',
    ':pantsbuild.pants.testinfra',
  ],
)

python_tests(name='idea_gen_xml',
  sources = [ 'test_idea_gen_xml.py' ],
  dependencies = [
    ':common',
    'squarepants/src/main/python/squarepants/plugins/square_idea',
    ':pantsbuild.pants.testinfra',
  ],
)

python_tests(name='link_resources_jars',
  sources = [ 'test_link_resources_jars.py'],
  dependencies = [
      ':common',
      'squarepants/src/main/python/squarepants/plugins/link_resources_jars',
      ':pantsbuild.pants.testinfra',
  ],
)

python_tests(name='link_resources_jars_integration',
  sources = ['test_link_resources_jars_integration.py'],
  dependencies = [
    'squarepants/src/main/python/squarepants:file_utils',
    'squarepants/src/test/python/squarepants_test:integration_test_base',
  ],
  tags = {'integration'},
)

python_tests(name='sake_wire_codegen',
  sources = [ 'test_sake_wire_codegen.py' ],
  dependencies = [
    ':common',
    'squarepants/src/main/python/squarepants/plugins/sake_wire_codegen',
    ':pantsbuild.pants.testinfra',
  ],
)

python_tests(name='sjar',
  sources = [ 'test_sjar.py' ],
  dependencies = [
    ':common',
    'squarepants/src/main/python/squarepants/plugins/sjar',
   ':pantsbuild.pants.testinfra',
  ],
)

python_tests(name='staging_build',
  sources = [ 'test_staging_build.py' ],
  dependencies = [
    ':common',
    'squarepants/src/main/python/squarepants/plugins/staging_build',
   ':pantsbuild.pants.testinfra',
  ],
)

python_tests(name='unpack_archives',
  sources = [ 'test_unpack_archives.py' ],
  dependencies = [
    ':common',
    'squarepants/src/main/python/squarepants/plugins/unpack_archives',
    ':pantsbuild.pants.testinfra',
  ],
)
