import networkx as nx
from typing import Dict, List, Any


class GraphAnalysis:
    """Advanced graph algorithms"""
    
    @staticmethod
    def find_critical_paths(G: nx.DiGraph) -> List[List[str]]:
        """Find longest paths"""
        try:
            dag = G.copy()
            if not nx.is_directed_acyclic_graph(dag):
                dag = nx.DiGraph([(u, v) for u, v in G.edges() if u != v])
            
            paths = []
            for source in [n for n in dag.nodes() if dag.in_degree(n) == 0]:
                for target in [n for n in dag.nodes() if dag.out_degree(n) == 0]:
                    try:
                        path = nx.shortest_path(dag, source, target)
                        if len(path) > 3:
                            paths.append(path)
                    except nx.NetworkXNoPath:
                        continue
            
            return sorted(paths, key=len, reverse=True)[:5]
        except Exception:
            return []
    
    @staticmethod
    def compute_centrality(G: nx.DiGraph) -> Dict[str, float]:
        """Betweenness centrality"""
        try:
            return nx.betweenness_centrality(G)
        except Exception:
            return {}
    
    @staticmethod
    def find_bottlenecks(G: nx.DiGraph) -> List[str]:
        """High-centrality nodes"""
        centrality = GraphAnalysis.compute_centrality(G)
        threshold = 0.3
        return [node for node, score in centrality.items() if score > threshold]
    
    @staticmethod
    def detect_cycles(G: nx.DiGraph) -> List[List[str]]:
        """Find circular dependencies"""
        try:
            return list(nx.simple_cycles(G))
        except Exception:
            return []
    
    @staticmethod
    def compute_service_layers(G: nx.DiGraph) -> Dict[str, int]:
        """Topological layers — depth from any source node."""
        try:
            if G.number_of_nodes() == 0:
                return {}
            # nx.shortest_path_length(G, target=None) returns a generator of
            # (source, dict) pairs.  Aggregate: layer = min distance from any source.
            layer: Dict[str, int] = {}
            for _source, lengths in nx.shortest_path_length(G):
                for node, dist in lengths.items():
                    if node not in layer or dist < layer[node]:
                        layer[node] = dist
            return layer
        except Exception:
            return {}
    
    @staticmethod
    def analyze_architecture(G: nx.DiGraph) -> Dict[str, Any]:
        """Full graph analysis"""
        return {
            "node_count": G.number_of_nodes(),
            "edge_count": G.number_of_edges(),
            "critical_paths": GraphAnalysis.find_critical_paths(G),
            "bottlenecks": GraphAnalysis.find_bottlenecks(G),
            "cycles": GraphAnalysis.detect_cycles(G),
            "avg_degree": sum(dict(G.degree()).values()) / G.number_of_nodes() if G.number_of_nodes() > 0 else 0,
            "is_dag": nx.is_directed_acyclic_graph(G)
        }
