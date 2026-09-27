import networkx as nx
from models.issue import Issue
from core.config import get_settings
from typing import List
import uuid

settings = get_settings()


class RuleEngine:
    """Deterministic rule-based issue detection"""
    
    @staticmethod
    def detect_high_latency_edges(G: nx.DiGraph) -> List[Issue]:
        """High latency edges"""
        issues = []
        threshold = settings.HIGH_LATENCY_THRESHOLD_MS
        
        for source, target, data in G.edges(data=True):
            latency = data.get("avg_latency_ms", 0)
            if latency > threshold:
                issues.append(Issue(
                    id=f"latency-{uuid.uuid4().hex[:8]}",
                    severity="high",
                    type="high_latency_edge",
                    description=f"Edge {source} → {target} has high latency ({latency:.0f}ms)",
                    affected_nodes=[source, target],
                    metric_value=latency,
                    evidence={
                        "threshold": threshold,
                        "actual": latency,
                        "call_count": data.get("call_count", 0)
                    }
                ))
        
        return issues
    
    @staticmethod
    def detect_deep_sync_chains(G: nx.DiGraph) -> List[Issue]:
        """Deep synchronous call chains"""
        issues = []
        max_depth = settings.MAX_SYNC_CHAIN_DEPTH
        
        try:
            for node in G.nodes():
                paths = nx.single_source_shortest_path_length(G, node)
                max_path = max(paths.values()) if paths else 0
                
                if max_path > max_depth:
                    issues.append(Issue(
                        id=f"chain-{uuid.uuid4().hex[:8]}",
                        severity="medium",
                        type="deep_sync_chain",
                        description=f"Service {node} has deep sync chain (depth={max_path})",
                        affected_nodes=[node],
                        metric_value=float(max_path),
                        evidence={
                            "threshold": max_depth,
                            "actual_depth": max_path
                        }
                    ))
        except Exception:
            pass
        
        return issues
    
    @staticmethod
    def detect_high_error_nodes(G: nx.DiGraph) -> List[Issue]:
        """High error rate services"""
        issues = []
        threshold = settings.HIGH_ERROR_RATE_THRESHOLD
        
        for node, data in G.nodes(data=True):
            metrics = data.get("metrics", {})
            error_rate = metrics.get("error_rate", 0)
            
            if error_rate > threshold:
                issues.append(Issue(
                    id=f"error-{uuid.uuid4().hex[:8]}",
                    severity="critical",
                    type="high_error_rate",
                    description=f"Service {node} has high error rate ({error_rate*100:.1f}%)",
                    affected_nodes=[node],
                    metric_value=error_rate,
                    evidence={
                        "threshold": threshold,
                        "actual": error_rate,
                        "call_count": metrics.get("call_count", 0)
                    }
                ))
        
        return issues
    
    @staticmethod
    def detect_fan_out_overload(G: nx.DiGraph) -> List[Issue]:
        """Excessive fan-out"""
        issues = []
        max_fan_out = settings.MAX_FAN_OUT
        
        for node in G.nodes():
            out_degree = G.out_degree(node)
            
            if out_degree > max_fan_out:
                issues.append(Issue(
                    id=f"fanout-{uuid.uuid4().hex[:8]}",
                    severity="medium",
                    type="fan_out_overload",
                    description=f"Service {node} calls too many services ({out_degree})",
                    affected_nodes=[node],
                    metric_value=float(out_degree),
                    evidence={
                        "threshold": max_fan_out,
                        "actual": out_degree,
                        "targets": list(G.successors(node))
                    }
                ))
        
        return issues
    
    @staticmethod
    def detect_single_point_of_failure(G: nx.DiGraph) -> List[Issue]:
        """Critical nodes whose failure impacts many"""
        issues = []
        
        for node in G.nodes():
            in_degree = G.in_degree(node)
            
            if in_degree > 5:  # Many depend on it
                issues.append(Issue(
                    id=f"spof-{uuid.uuid4().hex[:8]}",
                    severity="high",
                    type="single_point_of_failure",
                    description=f"Service {node} is SPOF with {in_degree} dependencies",
                    affected_nodes=[node],
                    metric_value=float(in_degree),
                    evidence={
                        "dependent_services": list(G.predecessors(node)),
                        "in_degree": in_degree
                    }
                ))
        
        return issues
    
    @staticmethod
    def run_all_rules(G: nx.DiGraph) -> List[Issue]:
        """Run all rules"""
        issues = []
        issues.extend(RuleEngine.detect_high_latency_edges(G))
        issues.extend(RuleEngine.detect_deep_sync_chains(G))
        issues.extend(RuleEngine.detect_high_error_nodes(G))
        issues.extend(RuleEngine.detect_fan_out_overload(G))
        issues.extend(RuleEngine.detect_single_point_of_failure(G))
        return issues
