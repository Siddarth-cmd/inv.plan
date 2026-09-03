"""
LangGraph Investigation Workflow.

Architecture:
  load_case_context
    → invest.planner (reusable node)
    → hypothesis_generation
    → evidence_retrieval
    → analysis_reasoning
    → adaptive_planner
        ↓ STOP → decision_node → report_generation → persist_results
        ↓ REPLAN → invest.planner (loop back)

One StateGraph, separate thread per case (thread_id = case_id).
invest.planner is called via the same node function on both initial and replan paths.

Checkpointing: MemorySaver for in-process state persistence.
"""
from __future__ import annotations

import time
from typing import Any

import structlog
from langgraph.graph import END, START, StateGraph
from langgraph.checkpoint.memory import MemorySaver 

from app.agents.state import (
    AdaptivePlannerDecision,
    AuditRecord,
    InvestigationState,
)
from app.agents.planner import invest_planner
from app.agents.hypothesis import hypothesis_generation
from app.agents.evidence_retrieval import evidence_retrieval
from app.agents.analysis import analysis_reasoning
from app.agents.adaptive_planner import adaptive_planner
from app.agents.decision import decision_node
from app.agents.report_agent import report_generation

logger = structlog.get_logger("finspectra.workflow")

# Module-level checkpointer and compiled graph
_checkpointer = MemorySaver()
_compiled_graph = None


def _persist_results(state: InvestigationState) -> InvestigationState:
    """
    Persist final investigation results to the database.
    This node runs at the END of both STOP paths.
    Database writes are handled asynchronously by the caller after the workflow returns.
    """
    case_id = state["case_id"]
    decision = state.get("decision")
    audit_trail = list(state.get("audit_trail") or [])

    audit = AuditRecord(
        case_id=case_id,
        actor="system:workflow",
        action="INVESTIGATION_COMPLETE",
        summary=(
            f"Investigation workflow complete. "
            f"Decision: {decision.outcome.value if decision else 'PENDING'}. "
            f"Evidence: {len(state.get('evidence') or [])}. "
            f"Audit events: {len(audit_trail)}."
        ),
        metadata={
            "decision": decision.outcome.value if decision else None,
            "evidence_count": len(state.get("evidence") or []),
            "finding_count": len(state.get("findings") or []),
            "plan_count": len(state.get("plan_history") or []),
        },
    )
    audit_trail.append(audit)
    logger.info("Investigation workflow complete", case_id=case_id,
                decision=decision.outcome.value if decision else None)
    return {**state, "audit_trail": audit_trail}


def _adaptive_planner_router(state: InvestigationState) -> str:
    """
    Conditional edge function for the adaptive planner.
    Returns node name: 'invest_planner' (for REPLAN) or 'decision_node' (for STOP).
    """
    decision = state.get("adaptive_decision")
    iteration = state.get("iteration_count", 0)
    max_iterations = state.get("max_iterations", 3)

    if decision == AdaptivePlannerDecision.REPLAN and iteration < max_iterations:
        return "invest_planner"
    return "decision_node"


def build_investigation_graph() -> Any:
    """
    Build and compile the LangGraph StateGraph for financial crime investigation.
    
    Node: invest_planner — reusable, called on both initial and replan paths.
    Thread isolation: each case uses thread_id = case_id via config={"configurable": {"thread_id": case_id}}.
    """
    builder = StateGraph(InvestigationState)

    # Add all nodes
    builder.add_node("invest_planner", invest_planner)
    builder.add_node("hypothesis_generation", hypothesis_generation)
    builder.add_node("evidence_retrieval", evidence_retrieval)
    builder.add_node("analysis_reasoning", analysis_reasoning)
    builder.add_node("adaptive_planner", adaptive_planner)
    builder.add_node("decision_node", decision_node)
    builder.add_node("report_generation", report_generation)
    builder.add_node("persist_results", _persist_results)

    # Define the linear path: START → invest_planner → ...
    builder.add_edge(START, "invest_planner")
    builder.add_edge("invest_planner", "hypothesis_generation")
    builder.add_edge("hypothesis_generation", "evidence_retrieval")
    builder.add_edge("evidence_retrieval", "analysis_reasoning")
    builder.add_edge("analysis_reasoning", "adaptive_planner")

    # Conditional edge: REPLAN → invest_planner (loop), STOP → decision_node
    builder.add_conditional_edges(
        "adaptive_planner",
        _adaptive_planner_router,
        {
            "invest_planner": "invest_planner",
            "decision_node": "decision_node",
        },
    )

    # Linear path after decision
    builder.add_edge("decision_node", "report_generation")
    builder.add_edge("report_generation", "persist_results")
    builder.add_edge("persist_results", END)

    return builder.compile(checkpointer=_checkpointer)


def get_investigation_graph():
    """Get or create the compiled investigation graph (singleton)."""
    global _compiled_graph
    if _compiled_graph is None:
        _compiled_graph = build_investigation_graph()
        logger.info("Investigation graph compiled")
    return _compiled_graph


def run_investigation(initial_state: InvestigationState) -> InvestigationState:
    """
    Execute a full investigation workflow for a single case.
    
    Args:
        initial_state: Pre-populated InvestigationState with case_context loaded.
    
    Returns:
        Final InvestigationState after all nodes complete.
    
    Thread isolation: thread_id = case_id ensures state is isolated per case.
    The invest.planner node is shared but state is thread-isolated by LangGraph.
    """
    case_id = initial_state["case_id"]
    log = logger.bind(case_id=case_id)
    start_ts = time.time()

    log.info("Starting investigation workflow")
    graph = get_investigation_graph()

    config = {
        "configurable": {
            "thread_id": case_id,  # One thread per case
        }
    }

    try:
        final_state = graph.invoke(initial_state, config=config)
        duration_s = time.time() - start_ts
        decision_val = final_state["decision"].outcome.value if final_state.get("decision") else None
        log.info(
            "Investigation workflow completed",
            duration_s=round(duration_s, 2),
            decision=decision_val,
        )
        return final_state
    except Exception as exc:
        log.error("Investigation workflow failed", error=str(exc))
        raise


def get_graph_visualization() -> dict[str, Any]:
    """Return the graph structure for frontend visualization."""
    return {
        "nodes": [
            {"id": "invest_planner", "label": "invest.planner", "type": "PLANNER",
             "description": "Generates structured investigation plan (reusable)"},
            {"id": "hypothesis_generation", "label": "Hypothesis Generation", "type": "ANALYSIS",
             "description": "Generates testable AML hypotheses from plan steps"},
            {"id": "evidence_retrieval", "label": "Evidence Retrieval", "type": "TOOL_CALLING",
             "description": "Executes plan steps via tool dispatch (GRAPH/DB/TYPOLOGY)"},
            {"id": "analysis_reasoning", "label": "Analysis & Reasoning", "type": "ANALYSIS",
             "description": "Synthesizes evidence into findings and risk scores"},
            {"id": "adaptive_planner", "label": "Adaptive Planner", "type": "ROUTER",
             "description": "STOP or REPLAN decision based on evidence sufficiency"},
            {"id": "decision_node", "label": "Decision", "type": "DECISION",
             "description": "Deterministic policy-driven decision (policy v1.0)"},
            {"id": "report_generation", "label": "Report Generation", "type": "REPORT",
             "description": "Structured report + ReportLab PDF generation"},
            {"id": "persist_results", "label": "Persist Results", "type": "STORAGE",
             "description": "Persist all results to database"},
        ],
        "edges": [
            {"source": "START", "target": "invest_planner", "label": "initialize"},
            {"source": "invest_planner", "target": "hypothesis_generation", "label": "plan_ready"},
            {"source": "hypothesis_generation", "target": "evidence_retrieval", "label": "hypotheses_ready"},
            {"source": "evidence_retrieval", "target": "analysis_reasoning", "label": "evidence_gathered"},
            {"source": "analysis_reasoning", "target": "adaptive_planner", "label": "analysis_done"},
            {"source": "adaptive_planner", "target": "invest_planner", "label": "REPLAN", "conditional": True},
            {"source": "adaptive_planner", "target": "decision_node", "label": "STOP", "conditional": True},
            {"source": "decision_node", "target": "report_generation", "label": "decision_made"},
            {"source": "report_generation", "target": "persist_results", "label": "report_ready"},
            {"source": "persist_results", "target": "END", "label": "complete"},
        ],
        "traceability_chain": "case_id → plan_id → step_id → evidence_id → finding_id → decision_id",
        "thread_isolation": "thread_id = case_id (per-case LangGraph state)",
        "replan_guard": "max_iterations = 3",
    }
