# Tests for code in squarepants/src/main/python/squarepants/plugins/staging_build/tasks/staging_build.py
#
# Run with:
# ./pants test squarepants/src/test/python/squarepants_test/plugins:staging_build

from pants.base.source_root import SourceRoot
from pants_test.tasks.task_test_base import TaskTestBase

from squarepants.plugins.sake_wire_codegen.targets.sake_wire_library import SakeWireLibrary
from squarepants.plugins.sake_wire_codegen.targets.wire_proto_path import WireProtoPath
from squarepants.plugins.sake_wire_codegen.tasks.sake_wire_codegen import SakeWireCodegen


class SakeWireCodegenTest(TaskTestBase):

  @classmethod
  def task_type(cls):
    return SakeWireCodegen


  def test_wire_proto_path(self):
    SourceRoot.register('foo/src/main/proto');
    SourceRoot.register('bar/src/main/proto');
    SourceRoot.register('baz/src/main/proto');

    foo_proto_path = self.make_target('foo/src/main/proto:wire-proto', WireProtoPath,
                                      sources=[
                                        'foo/src/main/proto/squareup/foo/foo.proto'
                                      ])
    bar_proto_path = self.make_target('bar/src/main/proto:wire-proto', WireProtoPath,
                                      sources=[
                                        'bar/src/main/proto/squareup/bar/bar.proto'
                                      ],
                                      dependencies=[
                                        foo_proto_path,
                                      ])
    sake_wire_library_target = self.make_target('baz:wire-library', SakeWireLibrary,
                                                sources=[
                                                  'baz/src/main/proto/squareup/baz/baz.proto'
                                                ],
                                                dependencies=[bar_proto_path])

    task = self.create_task(self.context(target_roots=[sake_wire_library_target]))

    self.assertEquals(['foo/src/main/proto', 'bar/src/main/proto'],
                      task._calculate_proto_paths(sake_wire_library_target))

