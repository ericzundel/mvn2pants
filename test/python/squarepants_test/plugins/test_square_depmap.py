# Tests for code in squarepants/src/main/python/squarepants/plugins/square_depmap.py
#
# Run with:
# ./pants test squarepants/src/test/python/squarepants_test/plugins:square_depmap

import unittest2 as unittest

from squarepants.plugins.square_depmap.tasks.graph_util import Graph

class SquareDepmapTest(unittest.TestCase):

  def test_graph_utils(self):
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
