# Tests for code in squarepants/src/main/python/graph_util.py
#
# Run with:
# ./pants test squarepants/src/test/python/squarepants_test:graph_util

import unittest2 as unittest

from squarepants.graph_util import Graph

class GraphUtilTest(unittest.TestCase):

  def test_graph_search(self):
    graph = Graph()
    graph.add_vertex('a')
    graph.add_vertex('b')
    graph.add_vertex('c')
    graph.add_vertex('d')
    graph.add_vertex('george')
    graph.add_vertex('dave')
    graph.add_edge(Graph.Edge('a', 'b'))
    graph.add_edge(Graph.Edge('b', 'a'))
    graph.add_edge(Graph.Edge('b', 'c'))
    graph.add_edge(Graph.Edge('a', 'd'))
    graph.add_edge(Graph.Edge('a', 'dave'))
    graph.add_edge(Graph.Edge('george', 'dave'))

    expected = '''
Vertices:
  a
  b
  c
  d
  dave
  george

Edges:
  a -> b
  a -> d
  a -> dave
  b -> a
  b -> c
  george -> dave
    '''
    self.assertEquals(expected.strip(), str(graph))
    self.assertEquals(set('ac'), graph.outgoing_vertices('b'), 'outgoing(b)')
    self.assertEquals(set('a'), graph.incoming_vertices('b'), 'incoming(b)')
    self.assertEquals(set('b'), graph.incoming_vertices('c'), 'incoming(c)')

    self.assertEquals(set('abcd').union(['dave']), graph.search_set('a'), 'search a -> ')
    self.assertEquals(set('c'), graph.search_set('c'), 'search c ->')
    self.assertEquals(set('abc'), graph.search_set('c', adjacent=graph.incoming_vertices),
                      'search <- c')

    self.assertEquals({Graph.Edge('a', 'b'), Graph.Edge('a', 'c')},
                {Graph.Edge('a', 'b'), Graph.Edge('a', 'b'), Graph.Edge('a', 'c')})

  def _char_graph(self, vertices, edges):
    """Convenience method for constructing a graph where each vertex is a single character.

    :param string vertices: Vertices, given as a string of characters.
    :param list edges: Edges, given as an iterable of strings, where each string is expected to be
      of the form 'uv'. Eg, edges might be ('ab', 'bc').
    """
    return Graph(vertices=vertices, edges=[Graph.Edge(u, v) for u, v in edges])

  def test_topological_ordering(self):
    graph = self._char_graph('abc', ('ab', 'bc'))
    self.assertEquals(tuple('abc'), tuple(graph.topological_ordering()))
    self.assertEquals(tuple('abc'), tuple(graph.topological_ordering(stable=True)))

    graph = graph.transposed
    self.assertEquals(tuple('cba'), tuple(graph.topological_ordering()))
    self.assertEquals(tuple('cba'), tuple(graph.topological_ordering(stable=True)))

    graph = Graph(vertices='cabzyx')
    self.assertEquals(tuple('abcxyz'), tuple(graph.topological_ordering(stable=True)))

    graph.add_edge(Graph.Edge('x', 'a'))
    self.assertEquals(tuple('bcxayz'), tuple(graph.topological_ordering(stable=True)))

    with self.assertRaises(Graph.CycleError):
      self._char_graph('abc', ('ab', 'bc', 'ca')).topological_ordering()

    with self.assertRaises(Graph.CycleError):
      self._char_graph('abc', ('ab', 'bc', 'ba')).topological_ordering()

    with self.assertRaises(Graph.CycleError):
      self._char_graph('ab', ('ab', 'ba')).topological_ordering()
