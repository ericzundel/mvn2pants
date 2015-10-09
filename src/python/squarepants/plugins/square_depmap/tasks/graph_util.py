# coding=utf-8
# Copyright 2015 Square, Inc.

from collections import defaultdict


class Graph(object):
  """Simple directed graph using dicts and sets to store directed edges."""

  class Edge(object):
    def __init__(self, src, dst, weight=1.0):
      self._src = src
      self._dst = dst
      self._weight = weight

    @property
    def src(self):
      return self._src

    @property
    def dst(self):
      return self._dst

    @property
    def weight(self):
      return self._weight

    def is_adjacent(self, vertex):
      return self.src == vertex or self.dst == vertex

    @property
    def reversed(self):
      return Graph.Edge(self.dst, self.src, self._weight)

    def __str__(self):
      return '{} -> {}'.format(self.src, self.dst)

    def __hash__(self):
      return hash(str(self))

    def __eq__(self, other):
      return str(self) == str(other)


  def __init__(self, vertices=None, edges=None):
    self._incomingEdges = defaultdict(set)
    self._outgoingEdges = defaultdict(set)
    self._vertices = set()
    if vertices:
      self._vertices.update(vertices)
    if edges:
      for edge in edges:
        self.add_edge(edge)

  @property
  def vertices(self):
    """All vertices in this graph."""
    return self._vertices

  @property
  def edges(self):
    """All directed edges in this graph."""
    return reduce(set.union, self._incomingEdges.values(), set())

  def incoming(self, vertex):
    """Returns the set of edges which lead to this vertex."""
    return self._incomingEdges[vertex]

  def outgoing(self, vertex):
    """Returns the set of edges which depart from this vertex."""
    return self._outgoingEdges[vertex]

  def incoming_vertices(self, vertex):
    """Returns the source vertices of the set of incoming edges."""
    return { edge.src for edge in self.incoming(vertex) }

  def outgoing_vertices(self, vertex):
    """Returns the destination vertices of the set of outgoing edges."""
    return { edge.dst for edge in self.outgoing(vertex) }

  def add_vertex(self, vertex):
    """Adds the vertex to the graph."""
    self._vertices.add(vertex)

  def add_edge(self, edge):
    """Adds the directed edge to the graph."""
    # Remove first, just in case the edge already exists with a different weight.
    self.remove_edge(edge)
    self._outgoingEdges[edge.src].add(edge)
    self._incomingEdges[edge.dst].add(edge)

  def remove_edge(self, edge):
    """Removes the directed edge from the graph."""
    self._outgoingEdges[edge.src].discard(edge)
    self._incomingEdges[edge.dst].discard(edge)

  def remove_vertex(self, vertex):
    """Removes the vertex from the graph."""
    for edge in self.edges:
      if edge.is_adjacent(vertex):
        self.remove_edge(edge)
    self.vertices.discard(vertex)

  def search(self, start, adjacent=None, next_index=None, multistart=False, cycle_handler=None):
    """Performs a graph search, yielding (path, vertex) pairs.

    If visit is set, simply searches the whole graph without yielding, passing all (path, vertex)
    pairs to visit(), terminating early if visit ever returns True.

    :param start: the starting (source) vertex.
    :param adjacent: the adjacency(vertex) function, defaulting to graph.outgoing.
    :param next_index: choose which index of the frontier to expand next.
      (lambda _: 0) will be a BFS (default).
      (lambda _:-1) will be a DFS.
      (lambda _: min(range(len(_)), key=_.__getitem__) will be a uniform cost search.
    :param multistart: if True, treats 'start' as a list of sources, rather than a single source.
    :param cycle_handler: function(path, vertex) to call if a cycle is detected.
    """
    # Default to forward-directed search.
    adjacent = adjacent or self.outgoing_vertices
    # Default to queue-like behavior, resulting in BFS.
    next_index = next_index or (lambda ls: 0)
    # Default to no-op.
    cycle_handler = cycle_handler or (lambda p,v: None)

    frontier = [(start,)] if not multistart else [(src,) for src in start]
    visited = set()
    while frontier:
      next = frontier.pop(next_index(frontier))
      path, vertex = next[:-1], next[-1]
      if vertex in visited:
        continue
      visited.add(vertex)

      yield path, vertex

      for neighbor in adjacent(vertex):
        if neighbor not in visited:
          frontier.append(path + (vertex,neighbor,))
        elif neighbor in (path + (vertex,)):
          cycle_handler(path + (vertex,), neighbor)

  def search_set(self, *vargs, **kwargs):
    """Returns the set of vertices hit by the given graph.search() parameters."""
    return set(vertex for path, vertex in self.search(*vargs, **kwargs))

  @property
  def copied(self):
    """Returns a copy of the graph."""
    return Graph(self.vertices, self.edges)

  @property
  def transposed(self):
    """Returns a transpose graph."""
    return Graph(self.vertices, [edge.reversed for edge in self.edges])

  def __str__(self):
    vertex_strings = sorted(str(v) for v in self.vertices)
    edge_strings = sorted(str(e) for e in self.edges)
    return 'Vertices:\n{vertex_text}\n\nEdges:\n{edges_text}'.format(
      vertex_text='\n'.join('  {}'.format(vertex) for vertex in vertex_strings),
      edges_text='\n'.join('  {}'.format(edge) for edge in edge_strings)
    )
