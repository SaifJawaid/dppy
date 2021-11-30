from networkx import Graph

from dppy.graph.uniform_spanning_tree import UST

# Build graph
g = Graph()
edges = [(0, 2), (0, 3), (1, 2), (1, 4), (2, 3), (2, 4), (3, 4)]
g.add_edges_from(edges)

# Initialize UST object
ust = UST(g)

# Display original graph
ust.plot_graph()

# Display some samples
for _ in range(3):
    ust.sample()
    ust.plot()

# Display underlying kernel i.e. transfer current matrix
ust.plot_kernel()
