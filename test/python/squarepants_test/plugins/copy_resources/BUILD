
# Integration test target.
# Test with: ./pants gen squarepants/src/test/python/squarepants_test/plugins/copy_resources --print-exception-stacktrace
resources(name='copy_resources',
  dependencies=[
    ':test-resource-jar',
  ],
)

resources_jar(name='test-resource-jar',
  dest='all-protos.jar',
  dependencies=[
    '3rdparty:com.squareup.protos.all-protos',
  ],
)
