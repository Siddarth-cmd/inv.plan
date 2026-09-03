"""
LangGraph Investigation Workflow.

Orchestrates the full investigation pipeline through a typed state graph.
Each node has clear input/output contracts.
The workflow is resumable and observable via audit events.
"""
from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Literal

from langgraph.graph import END, START, StateGraph

from app.agents.decision_agent import decision_agent
from app.agents.detection_agent import detection_agent
from app.agents.evidence_agent import evidence_agent
from app.agents.report_agent import report_agent
from app.agents.risk_agent import risk_agent
from app.agents.state import InvestigationState, initial_state
from app.core.logging import get_logger

logger = get_logger("workflow")


def build_investigation_graph() -> StateGraph:
    """Build and compile the LangGraph investigation workflow."""

    graph = StateGraph(InvestigationState)

    # Add nodes
    graph.add_node("detection", detection_agent)
    graph.add_node("evidence", evidence_agent)
    graph.add_node("risk", risk_agent)
    graph.add_node("decision", decision_agent)
    graph.add_node("report", report_agent)

    # Define edges (sequential pipeline)
    graph.add_edge(START, "detection")
    graph.add_edge("detection", "evidence")
    graph.add_edge("evidence", "risk")
    graph.add_edge("risk", "decision")
    graph.add_edge("decision", "report")
    graph.add_edge("report", END)

    return graph.compile()


# Module-level compiled graph
_compiled_graph = None


def get_investigation_graph():
    """Get the compiled graph (singleton)."""
    global _compiled_graph
    if _compiled_graph is None:
        _compiled_graph = build_investigation_graph()
    return _compiled_graph


async def run_investigation(
    investigation_id: str,
    alert_id: str,
    transaction: dict,
    all_transactions: list[dict],
) -> InvestigationState:
    """
    Run the complete investigation workflow.

    Args:
        investigation_id: UUID of the investigation record
        alert_id: UUID of the triggering alert
        transaction: The triggering transaction dict
        all_transactions: All available transactions for context

    Returns:
        Final InvestigationState with all agent outputs
    """
    logger.info(
        "workflow.start",
        investigation_id=investigation_id,
        alert_id=alert_id,
        transaction_count=len(all_transactions),
    )

    state = initial_state(investigation_id, alert_id, transaction, all_transactions)

    try:
        graph = get_investigation_graph()

        # LangGraph invoke is synchronous in this version
        # Run in executor to avoid blocking the event loop
        import asyncio
        loop = asyncio.get_event_loop()
        final_state = await loop.run_in_executor(
            None,
            lambda: graph.invoke(state),
        )

        logger.info(
            "workflow.complete",
            investigation_id=investigation_id,
            decision=final_state.get("decision"),
            risk_level=final_state.get("risk_level"),
        )

        return final_state

    except Exception as e:
        logger.error("workflow.error", investigation_id=investigation_id, error=str(e))
        # Return state with error record rather than raising
        state["errors"].append({"agent": "workflow", "error": str(e)})
        state["audit_events"].append({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "actor": "workflow",
            "action": "WORKFLOW_ERROR",
            "summary": f"Investigation workflow failed: {str(e)}",
            "metadata": {"error": str(e)},
        })
        return state
