# squarepants/src/main/python/squarepants/plugins/BUILD
# HANDWRITTEN


# HACK: something is broken in running pants tests that depend on this requirement.
# See https://github.com/pantsbuild/pex/issues/167
target(name='plugins')

target(name='plugins-real',
  dependencies = [
    'squarepants/src/main/python/squarepants/plugins/compile_prep_command',
    'squarepants/src/main/python/squarepants/plugins/copy_signed_jars',
    'squarepants/src/main/python/squarepants/plugins/repo',
    'squarepants/src/main/python/squarepants/plugins/ruby',
    'squarepants/src/main/python/squarepants/plugins/sake_wire_codegen',
    'squarepants/src/main/python/squarepants/plugins/sjar',
    'squarepants/src/main/python/squarepants/plugins/square_depmap',
    'squarepants/src/main/python/squarepants/plugins/square_manifest',
    'squarepants/src/main/python/squarepants/plugins/square_maven_layout',
    'squarepants/src/main/python/squarepants/plugins/staging_build',
  ],
)
