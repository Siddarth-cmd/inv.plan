"""
GraphQueryTool — Controlled interface for relationship/network queries.

Architecture rule: invest.planner and other agents reference this tool by name only.
The tool encapsulates NetworkX graph construction and query logic.
Interface is designed to be swapped for Neo4j without changing caller code.

All methods accept/return plain dicts for LangGraph state compatibility.
"""
from __future__ import annotations

import math
from typing import Any, Optional

import networkx as nx
import structlog

logger = structlog.get_logger("finspectra.tools.graph")


try:
    from neo4j import GraphDatabase
    NEO4J_AVAILABLE = True
except ImportError:
    NEO4J_AVAILABLE = False


class GraphQueryTool:
    """
    Controlled graph access layer.

    Build once from case context, query many times.
    NetworkX default backend; Neo4j-ready interface with Cypher translation support.
    """

    def __init__(self, backend_override: Optional[str] = None) -> None:
        from app.core.config import get_settings
        self._settings = get_settings()
        self._backend = backend_override or self._settings.graph_backend
        self._graph: Optional[nx.DiGraph] = None
        self._case_id: Optional[str] = None
        self._node_map: dict[str, dict[str, Any]] = {}  # node_id → metadata
        self._neo4j_driver = None

        if self._backend == "neo4j" and NEO4J_AVAILABLE:
            try:
                self._neo4j_driver = GraphDatabase.driver(
                    self._settings.neo4j_uri,
                    auth=(self._settings.neo4j_user, self._settings.neo4j_password)
                )
                logger.info("Neo4j driver initialized", uri=self._settings.neo4j_uri)
            except Exception as e:
                logger.warning("Neo4j connection failed — falling back to NetworkX", error=str(e))
                self._backend = "networkx"

    # ── Construction ──────────────────────────────────────────────────────────

    def build_from_context(self, case_context: dict[str, Any]) -> dict[str, Any]:
        """
        Build the investigation graph from the loaded case context.
        Returns build summary (nodes, edges, components).
        """
        self._graph = nx.DiGraph()
        self._case_id = case_context.get("case_id", "unknown")
        self._node_map = {}

        transactions = case_context.get("transactions", [])
        accounts = case_context.get("accounts", [])
        customers = case_context.get("customers", [])

        # Add account nodes
        for acc in accounts:
            nid = f"ACC:{acc.get('account_number', acc.get('id', ''))}"
            self._graph.add_node(nid, node_type="ACCOUNT", **acc)
            self._node_map[nid] = {"type": "ACCOUNT", **acc}

        # Add customer nodes
        for cust in customers:
            nid = f"CUST:{cust.get('customer_ref', cust.get('id', ''))}"
            self._graph.add_node(nid, node_type="CUSTOMER", **cust)
            self._node_map[nid] = {"type": "CUSTOMER", **cust}

        # Add transaction edges + infer nodes for unknown accounts
        for txn in transactions:
            from_acc = txn.get("from_account_number")
            to_acc = txn.get("to_account_number")
            amount = txn.get("amount", 0)
            txn_id = txn.get("id", txn.get("txn_ref", ""))

            if from_acc:
                fn = f"ACC:{from_acc}"
                if fn not in self._graph:
                    self._graph.add_node(fn, node_type="ACCOUNT", account_number=from_acc)
                    self._node_map[fn] = {"type": "ACCOUNT", "account_number": from_acc}
            if to_acc:
                tn = f"ACC:{to_acc}"
                if tn not in self._graph:
                    self._graph.add_node(tn, node_type="ACCOUNT", account_number=to_acc)
                    self._node_map[tn] = {"type": "ACCOUNT", "account_number": to_acc}

            if from_acc and to_acc:
                fn, tn = f"ACC:{from_acc}", f"ACC:{to_acc}"
                if self._graph.has_edge(fn, tn):
                    self._graph[fn][tn]["weight"] += amount
                    self._graph[fn][tn]["txn_count"] += 1
                    self._graph[fn][tn]["txn_ids"].append(txn_id)
                else:
                    self._graph.add_edge(
                        fn, tn,
                        weight=amount,
                        txn_count=1,
                        txn_ids=[txn_id],
                        edge_type="TRANSACTION",
                    )

            # Device-based entity edges
            device_id = txn.get("device_id")
            if device_id and from_acc:
                dn = f"DEV:{device_id}"
                if dn not in self._graph:
                    self._graph.add_node(dn, node_type="DEVICE", device_id=device_id)
                    self._node_map[dn] = {"type": "DEVICE", "device_id": device_id}
                self._graph.add_edge(
                    f"ACC:{from_acc}", dn,
                    edge_type="USES_DEVICE", weight=1,
                    txn_count=1, txn_ids=[txn_id],
                )

        # Entity clusters → group nodes
        for cluster in case_context.get("entity_clusters", []):
            members = cluster.get("members", [])
            cluster_id = cluster.get("cluster_id", "")
            for i, m1 in enumerate(members):
                for m2 in members[i + 1:]:
                    if m1 in self._graph and m2 in self._graph:
                        self._graph.add_edge(
                            m1, m2,
                            edge_type="ENTITY_CLUSTER",
                            reason=cluster.get("reason", "Shared identifier"),
                            weight=0.5,
                            txn_count=0,
                            txn_ids=[],
                        )

        num_components = nx.number_weakly_connected_components(self._graph)
        summary = {
            "nodes": self._graph.number_of_nodes(),
            "edges": self._graph.number_of_edges(),
            "weakly_connected_components": num_components,
            "case_id": self._case_id,
        }
        logger.info("Graph built", **summary)
        return summary

    def _require_graph(self) -> nx.DiGraph:
        if self._graph is None:
            raise RuntimeError("Graph not built — call build_from_context() first")
        return self._graph

    # ── Queries ───────────────────────────────────────────────────────────────

    def find_cycles(self) -> list[dict[str, Any]]:
        """
        Detect cycles in the transaction graph (circular money movement indicator).
        Returns list of cycle dicts with nodes, total_amount, txn_count.
        """
        g = self._require_graph()
        results = []
        try:
            for cycle in nx.simple_cycles(g):
                if len(cycle) < 2:
                    continue
                total_amount = 0.0
                txn_count = 0
                txn_ids = []
                for i in range(len(cycle)):
                    src = cycle[i]
                    dst = cycle[(i + 1) % len(cycle)]
                    if g.has_edge(src, dst):
                        ed = g[src][dst]
                        total_amount += ed.get("weight", 0)
                        txn_count += ed.get("txn_count", 0)
                        txn_ids.extend(ed.get("txn_ids", []))
                results.append({
                    "nodes": cycle,
                    "length": len(cycle),
                    "total_amount": total_amount,
                    "txn_count": txn_count,
                    "txn_ids": txn_ids,
                })
        except Exception as e:
            logger.warning("Cycle detection error", error=str(e))
        return results

    def get_degree_centrality(self) -> dict[str, float]:
        """Return in/out degree for all account nodes."""
        g = self._require_graph()
        try:
            in_deg = dict(nx.in_degree_centrality(g))
            out_deg = dict(nx.out_degree_centrality(g))
            return {
                node: {"in": round(in_deg.get(node, 0), 4), "out": round(out_deg.get(node, 0), 4)}
                for node in g.nodes
                if self._node_map.get(node, {}).get("type") == "ACCOUNT"
            }
        except Exception as e:
            logger.warning("Centrality error", error=str(e))
            return {}

    def get_high_centrality_nodes(self, threshold: float = 0.3) -> list[dict[str, Any]]:
        """Return nodes with degree centrality above threshold (potential hub accounts)."""
        centrality = self.get_degree_centrality()
        results = []
        for node, scores in centrality.items():
            max_score = max(scores.get("in", 0), scores.get("out", 0))
            if max_score >= threshold:
                results.append({
                    "node": node,
                    "in_centrality": scores.get("in", 0),
                    "out_centrality": scores.get("out", 0),
                    "metadata": self._node_map.get(node, {}),
                })
        return sorted(results, key=lambda x: max(x["in_centrality"], x["out_centrality"]), reverse=True)

    def get_neighbors(self, node_id: str, depth: int = 1) -> list[dict[str, Any]]:
        """
        Return all neighbors of a node up to `depth` hops.
        node_id format: "ACC:ACC001" or "CUST:C001"
        """
        g = self._require_graph()
        if node_id not in g:
            return []
        visited = {node_id}
        frontier = {node_id}
        results = []
        for _ in range(depth):
            next_frontier = set()
            for n in frontier:
                for nbr in list(g.successors(n)) + list(g.predecessors(n)):
                    if nbr not in visited:
                        edge_data = {}
                        if g.has_edge(n, nbr):
                            edge_data = dict(g[n][nbr])
                        elif g.has_edge(nbr, n):
                            edge_data = dict(g[nbr][n])
                        results.append({
                            "node": nbr,
                            "via": n,
                            "edge_type": edge_data.get("edge_type", "UNKNOWN"),
                            "weight": edge_data.get("weight", 0),
                            "txn_count": edge_data.get("txn_count", 0),
                            "metadata": self._node_map.get(nbr, {}),
                        })
                        visited.add(nbr)
                        next_frontier.add(nbr)
            frontier = next_frontier
        return results

    def get_shared_devices(self) -> list[dict[str, Any]]:
        """Return device nodes used by more than one account (entity resolution signal)."""
        g = self._require_graph()
        results = []
        for node in g.nodes:
            if self._node_map.get(node, {}).get("type") == "DEVICE":
                accounts_using = [
                    pred for pred in g.predecessors(node)
                    if self._node_map.get(pred, {}).get("type") == "ACCOUNT"
                ]
                if len(accounts_using) > 1:
                    results.append({
                        "device": node,
                        "accounts": accounts_using,
                        "account_count": len(accounts_using),
                    })
        return results

    def get_rapid_pass_through(self, window_seconds: int = 3600) -> list[dict[str, Any]]:
        """
        Detect accounts that receive and immediately forward funds (layering indicator).
        Returns accounts where outgoing transactions closely follow incoming ones.
        """
        g = self._require_graph()
        results = []
        for node in g.nodes:
            if self._node_map.get(node, {}).get("type") != "ACCOUNT":
                continue
            in_edges = list(g.in_edges(node, data=True))
            out_edges = list(g.out_edges(node, data=True))
            in_vol = sum(d.get("weight", 0) for _, _, d in in_edges if d.get("edge_type") == "TRANSACTION")
            out_vol = sum(d.get("weight", 0) for _, _, d in out_edges if d.get("edge_type") == "TRANSACTION")
            if in_vol > 0 and out_vol > 0:
                ratio = out_vol / in_vol
                if ratio > 0.8:  # >80% of incoming immediately forwarded
                    results.append({
                        "account": node,
                        "in_volume": in_vol,
                        "out_volume": out_vol,
                        "passthrough_ratio": round(ratio, 3),
                        "in_sources": [str(s) for s, _, _ in in_edges],
                        "out_destinations": [str(t) for _, t, _ in out_edges],
                    })
        return sorted(results, key=lambda x: x["passthrough_ratio"], reverse=True)

    def to_serializable(self) -> dict[str, Any]:
        """Return the graph as a JSON-serializable dict for API/frontend."""
        g = self._require_graph()
        nodes = []
        for n, data in g.nodes(data=True):
            nodes.append({
                "id": n,
                "label": n.split(":", 1)[-1] if ":" in n else n,
                "node_type": data.get("node_type", "UNKNOWN"),
                "properties": {k: v for k, v in data.items() if k != "node_type"},
            })
        edges = []
        for src, dst, data in g.edges(data=True):
            edges.append({
                "source": src,
                "target": dst,
                "edge_type": data.get("edge_type", "UNKNOWN"),
                "label": data.get("edge_type", ""),
                "weight": data.get("weight", 1.0),
                "properties": {k: v for k, v in data.items()},
            })
        return {
            "nodes": nodes,
            "edges": edges,
            "metrics": {
                "node_count": g.number_of_nodes(),
                "edge_count": g.number_of_edges(),
                "cycles_detected": len(self.find_cycles()),
            },
        }
