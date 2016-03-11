# coding=utf-8
# Copyright 2015 Square, Inc.

from __future__ import (absolute_import, division, generators, nested_scopes, print_function,
                        unicode_literals, with_statement)

import datetime
import os
import sys
from collections import defaultdict
from contextlib import contextmanager
from hashlib import sha1
from subprocess import Popen, PIPE
from shutil import rmtree

from pants.task.task import Task
from pants.base.exceptions import TaskError
from pants.base.workunit import WorkUnitLabel
from pants.util.memo import memoized

from squarepants.graph_util import Graph


class SquareDepmap(Task):

  @classmethod
  def register_options(cls, register):
    super(SquareDepmap, cls).register_options(register)
    register('--compress-projects', action='store_true', default=True,
             help='Compresses all targets in each project to a single vertex.',)
    register('--concentrate-edges', action='store_true', default=True,
             help='Allow edges leading to the same destinations to be combined.',)
    register('--dot-project-weight', type=int, default=1,
             help='Integer weight to assign to edges connecting projects internally. '
                  'Bigger numbers will cause targets within the same project to be '
                  'positioned closer together.',)
    register('--ignore-subprojects', action='store_true', default=False,
             help='Treats all projects under the same directory as the same project. '
                  'For example, "foobar", "foobar/barfoo", and "foobar/foobar-protos" will '
                  'all be treated as one project.',)
    register('--include-tests', action='store_true', default=True,
             help='Includes test targets in the graph.',)
    register('--rainbow', action='store_true', default=True,
             help='Assigns arbitrary colors to projects to aid readability.',)
    register('--reduce-transitive', action='store_true', default=True,
             help='Simplify the graph by removing edges already implied by transitive '
                  'dependencies. Requires graphviz commandline tools. ',)
    register('--run-dot', action='store_true', default=True,
             help='Automatically runs dot on the generated graph to produce an svg. '
                  'Requires graphviz commandline tools.',)

  def __init__(self, *vargs, **kwargs):
    super(SquareDepmap, self).__init__(*vargs, **kwargs)
    self._work_depth = 0

  def _work_log(self, *vargs):
    with self._work_block(*vargs):
      pass

  @contextmanager
  def _work_block(self, *vargs):
    with self.context.new_workunit(name=' '.join(str(s) for s in vargs),
                                   labels=[WorkUnitLabel.TASK]):
      before = datetime.datetime.now()
      yield
      after = datetime.datetime.now()
      millis = (after - before).total_seconds() * 1000
      sys.stdout.write(' ({}ms)'.format(millis))

  def _target_dependencies(self, target):
    try:
      return sorted(target.dependencies)
    except:
      return []

  def _collect_dependencies(self, targets, predicate=None):
    """Dependency walk that doesn't use recursion.

    Walks in DFS order.
    """
    with self._work_block('Collecting with walk_transitive_dependency_graph()'):
      pants_results = []
      self.context.build_graph.walk_transitive_dependency_graph(
        [target.address for target in targets],
        pants_results.append,
        postorder=True, # DFS
        predicate=predicate,
      )
    return pants_results


  def _format_target(self, depth, target):
    try:
      return '{indent}{target}'.format(
        indent='  '*depth,
        target=target.id
      )
    except:
      return '{}???'.format('  '*depth)

  @memoized(key_factory=lambda self, targets: frozenset(targets))
  def _target_to_project_map(self, targets):
    targets_to_projects = {}
    for target in targets:
      project_dir = target.address.build_file.relpath
      if self.get_options().ignore_subprojects:
        project_dir = project_dir.split(os.path.sep)[0]
      else:
        path_parts = project_dir.split(os.path.sep)
        if 'src' in path_parts:
          project_dir = os.path.join(*path_parts[:path_parts.index('src')])
        else:
          while not os.path.exists(os.path.join(project_dir, 'pom.xml')):
            if os.path.abspath(project_dir) == os.path.abspath('.'):
              break # We can't go any higher.
            project_dir = os.path.dirname(project_dir)
      targets_to_projects[target.id] = project_dir
    return targets_to_projects

  def _get_target_project_maps(self, targets):
    target_to_project = self._target_to_project_map(targets)
    project_to_targets = defaultdict(set)
    for target in targets:
      project_to_targets[target_to_project.get(target.id, target.id)].add(target.id)
    return target_to_project, project_to_targets

  def _create_target_graph(self, targets, predicate=None):
    predicate = predicate or (lambda x: True)
    graph = Graph()
    for target in self._collect_dependencies(targets, predicate):
      graph.add_vertex(target.id)
      for dep in self._target_dependencies(target):
        if predicate(dep):
          graph.add_edge(Graph.Edge(target.id, dep.id))
    return graph

  def execute(self):
    targets = self.context.targets()
    hasher = sha1()
    for target in sorted([t.id for t in targets]):
      hasher.update(target)
    gv_path = os.path.join(self.workdir, hasher.hexdigest(), 'output.gv')
    if os.path.exists(os.path.dirname(gv_path)):
      rmtree(os.path.dirname(gv_path))
    os.makedirs(os.path.dirname(gv_path))

    with self._work_block('Generating .gv data'):
      with open(gv_path, 'w') as f:
        try:
          f.write('\n'.join(self.generate_gv(targets)))
        except Exception as e:
          raise TaskError('Error generating graphviz data: {}.'.format(e))

      if self.get_options().reduce_transitive:
        with self._work_block('Reducing transitive dependencies with tred.'):
          tred = Popen(['tred', gv_path], stdout=PIPE, stderr=PIPE)
          out, err = tred.communicate()
          if err:
            self._work_log('tred errors:')
            self._work_log(err)
          with open(gv_path, 'w') as f:
            f.write(out)

      print(' {}'.format(gv_path))

    if self.get_options().run_dot:
      with self._work_block('Generating output svg with dot.'):
        dot = Popen(['dot', '-Tsvg', '-O', gv_path], stdout=PIPE, stderr=PIPE)
        out, err = dot.communicate()
        if err:
          self._work_log('Dot errors: ')
          self._work_log(err)
        print(' {}.svg'.format(gv_path))

  def _dot_args(self, args):
    if not args:
      return ''
    return '[{}]'.format(','.join('{}={}'.format(key,val) for key,val in args.items()))

  def generate_gv(self, targets):
    all_targets = set()
    skipped_targets = set()
    def target_filter(target):
      if not self.get_options().include_tests:
        test_names = ('test', 'tests', 'testing')
        if target.has_label('tests') or any(part in test_names for part in target.id.split('.')):
          skipped_targets.add(target)
          return False
      all_targets.add(target)
      return True

    self._work_log('Generating target graph.')
    graph = self._create_target_graph(targets, predicate=target_filter)
    if skipped_targets:
      print(''.join('\n  skipped {}'.format(target.id) for target in skipped_targets))

    compress_projects = self.get_options().compress_projects
    if compress_projects:
      with self._work_block('Compressing projects.'):
        target_to_project = self._target_to_project_map(all_targets)
        # Make an exception for 3rdparty.
        for target in all_targets:
          if '3rdparty' in target.id:
            target_to_project[target.id] = target.id

        new_graph = Graph()
        for vertex in graph.vertices:
          new_graph.add_vertex(target_to_project[vertex])
        for edge in graph.edges:
          new_graph.add_edge(Graph.Edge(target_to_project[edge.src], target_to_project[edge.dst]))

        graph = new_graph
        all_targets = { target_to_project.get(target.id) for target in all_targets }

        target_to_project = { target: target for target in all_targets }
        project_to_targets = { target: {target} for target in all_targets }
    else:
      with self._work_block('Calculating target project groups.'):
        target_to_project, project_to_targets = self._get_target_project_maps(targets)

    with self._work_block('Finding subgraphs.'):
      groups = sorted(map(sorted, project_to_targets.values()))

    target_to_color = {}
    if self.get_options().rainbow:
      with self._work_block('Assigning colors.'):
        for index, group in enumerate(groups):
          color = '"{hue}, {saturation}, {value}"'.format(
            hue = ((index * 32) % 360) / 360.0,
            saturation = 0.5 if index%2==0 else 0.2,
            value = 0.9 if index%2==0 else 0.7,
          )
          for vertex in group:
            if '3rdparty' in vertex:
              continue
            target_to_color[vertex] = color

    with self._work_block('Assigning vertex names.'):
      alphabet = [chr(c) for c in range(ord('a'), ord('z')+1)]
      vertex_names = {}
      counter = [0]
      for group in groups:
        for vertex in group:
          if vertex in vertex_names:
            raise ValueError('Vertex is duplicated between disjoint sets! {}'.format(vertex))
          vertex_names[vertex] = ''.join(alphabet[c] for c in counter)
          i = len(counter)-1
          while True:
            if i < 0:
              counter.insert(0, 0)
              break
            counter[i] += 1
            if counter[i] >= len(alphabet):
              counter[i] = 0
            else:
              break
            i -= 1

    with self._work_block('Generating .gv file.'):
      name = vertex_names.get
      external_color = 'maroon'
      yield 'digraph "{}" {{'.format(' '.join(sys.argv[1:]))
      yield '  rankdir=LR;'
      yield '  compound=true;'
      if self.get_options().concentrate_edges:
        yield '  concentrate=true;'
      self._work_log('Generating target vertices.')
      for index, group in enumerate(groups):
        label = None
        yield '  subgraph project_{} {{'.format(index)
        yield '    color=black;'
        for vertex in group:
          if label is None:
            label = vertex[:vertex.find('.')]
            yield '    label = "{}";'.format(label)
          args = {
            'label': '"{}"'.format(vertex),
            'shape': 'box',
            'color': 'black',
            'style': 'filled'
          }
          if '3rdparty' in vertex:
            args['shape'] = 'ellipse'
            args['color'] = external_color
            args['fillcolor'] = 'pink'
          else:
            args['fillcolor'] = target_to_color.get(vertex, 'lightgrey')
          yield '    {name} {args};'.format(
            name=name(vertex),
            args=self._dot_args(args),
          )
        yield '  }'
      self._work_log('Generating edges.')
      for edge in graph.edges:
        same_project = target_to_project[edge.src] == target_to_project[edge.dst]
        args = {
          'color': target_to_color.get(edge.dst, 'black'),
        }
        if '3rdparty' in edge.dst:
          args['color'] = external_color
          args['arrowsize'] = 0.5
          args['style'] = 'dashed'
        elif same_project:
          args['weight'] = self.get_options().dot_project_weight
        yield '  {src} -> {dst}{args};'.format(
          src=name(edge.src),
          dst=name(edge.dst),
          args=self._dot_args(args)
        )
      yield '}'
