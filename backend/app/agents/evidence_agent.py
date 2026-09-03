"""
Evidence Agent — Agent 2.

Gathers actual available evidence from:
- Customer history
- Account history
- Related transactions
- Entity relationships
- Graph relationships

Every evidence item has provenance.
Does NOT invent external evidence or pretend web searches occurred.
"""
from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Any

import networkx as nx
import pandas as pd

from app.agents.state import InvestigationState
from app.core.logging import get_logger
from app.services.entity_resolution import resolve_entities

logger = get_logger("evidence_agent")


def evidence_agent(state: InvestigationState) -> InvestigationState:
    """
    Evidence Agent node for LangGraph.

    Reads: transaction, all_transactions, suspicious_transaction_ids
    Writes: customer_info, account_history, related_transactions,
            entity_relationships, evidence, graph_nodes, graph_edges, graph_metrics
    """
    start_time = time.monotonic()
    investigation_id = state["investigation_id"]

    logger.info("evidence_agent.start", investigation_id=investigation_id)

    try:
        transaction = state["transaction"]
        all_transactions = state["all_transactions"]
        suspicious_ids = set(state["suspicious_transaction_ids"])

        txn_df = pd.DataFrame(all_transactions)
        if txn_df.empty:
            raise ValueError("No transactions to analyze.")

        evidence: list[dict] = []
        entity_relationships: list[dict] = []

        # === Customer / Account Info ===
        from_acc = transaction.get("from_account_number", "UNKNOWN")
        to_acc = transaction.get("to_account_number", "UNKNOWN")

        # Find all transactions involving this account
        account_history = txn_df[
            (txn_df["from_account_number"] == from_acc) |
            (txn_df["to_account_number"] == from_acc)
        ].to_dict(orient="records")

        if account_history:
            evidence.append({
                "evidence_type": "ACCOUNT_HISTORY",
                "source": "transaction_database",
                "source_record_id": from_acc,
                "description": f"Account {from_acc} has {len(account_history)} historical transactions in the dataset.",
                "supporting_transaction_ids": [str(t["id"]) for t in account_history[:20]],
                "confidence": 1.0,
                "is_external": False,
            })

        # === Related Transactions ===
        related_txns = txn_df[
            (txn_df["from_account_number"] == to_acc) |
            (txn_df["to_account_number"] == to_acc)
        ].to_dict(orient="records")

        if related_txns:
            evidence.append({
                "evidence_type": "RELATED_TRANSACTIONS",
                "source": "transaction_database",
                "source_record_id": to_acc,
                "description": f"Counterparty account {to_acc} has {len(related_txns)} related transactions.",
                "supporting_transaction_ids": [str(t["id"]) for t in related_txns[:20]],
                "confidence": 1.0,
                "is_external": False,
            })

        # === Entity Resolution ===
        entity_rels, cluster_info = resolve_entities(txn_df)
        entity_relationships = entity_rels

        for rel in entity_rels[:5]:
            evidence.append({
                "evidence_type": "ENTITY_RELATIONSHIP",
                "source": "entity_resolution_engine",
                "source_record_id": None,
                "description": rel["reason"],
                "supporting_transaction_ids": rel.get("supporting_transaction_ids", []),
                "confidence": rel.get("confidence", 0.9),
                "is_external": False,
            })

        # === Graph Analysis ===
        G = nx.DiGraph()
        graph_nodes = []
        graph_edges = []
        seen_nodes = set()

        for _, row in txn_df.iterrows():
            frm = str(row.get("from_account_number", "") or "")
            to = str(row.get("to_account_number", "") or "")
            amt = float(row.get("amount", 0))
            txn_id = str(row["id"])

            if frm and frm not in seen_nodes:
                G.add_node(frm, node_type="account")
                is_suspicious = txn_id in suspicious_ids
                graph_nodes.append({
                    "id": frm,
                    "label": frm,
                    "node_type": "account",
                    "properties": {"is_suspicious": is_suspicious},
                })
                seen_nodes.add(frm)

            if to and to not in seen_nodes:
                G.add_node(to, node_type="account")
                graph_nodes.append({
                    "id": to,
                    "label": to,
                    "node_type": "account",
                    "properties": {"is_suspicious": False},
                })
                seen_nodes.add(to)

            if frm and to:
                if G.has_edge(frm, to):
                    G[frm][to]["weight"] += amt
                    G[frm][to]["count"] += 1
                else:
                    G.add_edge(frm, to, weight=amt, count=1)
                    graph_edges.append({
                        "source": frm,
                        "target": to,
                        "edge_type": "TRANSFER",
                        "label": f"₹{amt:,.0f}",
                        "weight": amt,
                        "properties": {"transaction_ids": [txn_id]},
                    })

        # Graph metrics
        graph_metrics: dict[str, Any] = {
            "node_count": G.number_of_nodes(),
            "edge_count": G.number_of_edges(),
        }

        if G.number_of_nodes() > 0:
            try:
                degrees = dict(G.degree())
                graph_metrics["avg_degree"] = sum(degrees.values()) / len(degrees)
                graph_metrics["max_degree_node"] = max(degrees, key=degrees.get)

                components = list(nx.weakly_connected_components(G))
                graph_metrics["component_count"] = len(components)
                graph_metrics["largest_component_size"] = max(len(c) for c in components)

                # Centrality for subject account
                if from_acc in G:
                    try:
                        in_deg = G.in_degree(from_acc)
                        out_deg = G.out_degree(from_acc)
                        graph_metrics["subject_in_degree"] = in_deg
                        graph_metrics["subject_out_degree"] = out_deg
                    except Exception:
                        pass

                # Detect cycles
                try:
                    cycles = list(nx.simple_cycles(G))
                    graph_metrics["cycle_count"] = len(cycles)
                    if cycles:
                        graph_metrics["cycles"] = cycles[:3]
                        evidence.append({
                            "evidence_type": "CIRCULAR_TRANSACTION_PATHS",
                            "source": "graph_analysis",
                            "source_record_id": None,
                            "description": f"Graph analysis detected {len(cycles)} circular transaction path(s) in the account network.",
                            "supporting_transaction_ids": [],
                            "confidence": 0.9,
                            "is_external": False,
                        })
                except Exception:
                    graph_metrics["cycle_count"] = 0
            except Exception as e:
                logger.warning("evidence_agent.graph_metrics_error", error=str(e))

        if entity_rels:
            evidence.append({
                "evidence_type": "NETWORK_SUMMARY",
                "source": "entity_resolution_engine",
                "source_record_id": None,
                "description": f"Entity resolution identified {len(entity_rels)} relationships among accounts in this dataset.",
                "supporting_transaction_ids": [],
                "confidence": 1.0,
                "is_external": False,
            })

        # Duration
        duration_ms = int((time.monotonic() - start_time) * 1000)
        audit_event = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "actor": "evidence_agent",
            "action": "EVIDENCE_GATHERED",
            "summary": (
                f"Evidence gathering complete. {len(evidence)} evidence items. "
                f"{len(entity_relationships)} entity relationships. "
                f"Graph: {G.number_of_nodes()} nodes, {G.number_of_edges()} edges."
            ),
            "metadata": {
                "evidence_count": len(evidence),
                "entity_relationship_count": len(entity_relationships),
                "duration_ms": duration_ms,
            },
        }

        logger.info(
            "evidence_agent.complete",
            investigation_id=investigation_id,
            evidence_count=len(evidence),
            entity_rel_count=len(entity_relationships),
            duration_ms=duration_ms,
        )

        return {
            **state,
            "account_history": account_history[:50],
            "related_transactions": related_txns[:50],
            "entity_relationships": entity_relationships,
            "evidence": evidence,
            "graph_nodes": graph_nodes,
            "graph_edges": graph_edges,
            "graph_metrics": graph_metrics,
            "audit_events": state["audit_events"] + [audit_event],
        }

    except Exception as e:
        logger.error("evidence_agent.error", investigation_id=investigation_id, error=str(e))
        error_event = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "actor": "evidence_agent",
            "action": "EVIDENCE_ERROR",
            "summary": f"Evidence agent encountered an error: {str(e)}",
            "metadata": {"error": str(e)},
        }
        return {
            **state,
            "errors": state["errors"] + [{"agent": "evidence", "error": str(e)}],
            "audit_events": state["audit_events"] + [error_event],
        }
