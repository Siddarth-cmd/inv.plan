"""
Hypothesis Generation Node.

Takes the invest.planner's plan and generates testable hypotheses
for each domain-specific plan step. No hallucination — hypotheses
come only from plan steps and detected signals.

Traceability: plan_id → step_id → hypothesis_id
"""
from __future__ import annotations

import time
from typing import Any

import structlog

from app.agents.state import (
    AuditRecord,
    Hypothesis,
    HypothesisStatus,
    InvestigationState,
    PlanStep,
    PlanStepAction,
)

logger = structlog.get_logger("finspectra.agents.hypothesis")

# Map plan actions to AML typology hypotheses
ACTION_HYPOTHESIS_MAP: dict[PlanStepAction, list[dict[str, Any]]] = {
    PlanStepAction.ANALYZE_AMOUNT_PATTERNS: [
        {
            "statement": "The account may be structuring transactions to stay below reporting thresholds.",
            "typology": "STRUCTURING_SMURFING",
            "signals": ["AMOUNT_BELOW_THRESHOLD", "MULTIPLE_TRANSACTIONS"],
        },
        {
            "statement": "The transaction amount is anomalously large relative to the account's historical baseline.",
            "typology": "LARGE_VALUE_TRANSFER",
            "signals": ["HIGH_ANOMALY_SCORE", "LARGE_AMOUNT"],
        },
    ],
    PlanStepAction.DETECT_GRAPH_CYCLES: [
        {
            "statement": "Funds may be flowing in a circular pattern among a set of connected accounts.",
            "typology": "CIRCULAR_TRANSFER",
            "signals": ["CIRCULAR_MOVEMENT", "GRAPH_CYCLE"],
        },
    ],
    PlanStepAction.ASSESS_COUNTERPARTIES: [
        {
            "statement": "The account may be acting as a pass-through to layer funds before final placement.",
            "typology": "LAYERING_RAPID_PASSTHROUGH",
            "signals": ["HIGH_PASSTHROUGH_RATIO", "RAPID_FORWARDING"],
        },
        {
            "statement": "The counterparty may be a high-risk entity with no legitimate business justification.",
            "typology": "UNUSUAL_COUNTERPARTY",
            "signals": ["UNKNOWN_COUNTERPARTY"],
        },
    ],
    PlanStepAction.EVALUATE_DEVICE_SIGNALS: [
        {
            "statement": "Multiple accounts may be controlled by the same actor via shared device identifiers.",
            "typology": "MULE_ACCOUNT_NETWORK",
            "signals": ["SHARED_DEVICE"],
        },
    ],
    PlanStepAction.ANALYZE_TEMPORAL_PATTERNS: [
        {
            "statement": "Transactions may be timed to avoid detection or automated monitoring windows.",
            "typology": "TEMPORAL_EVASION",
            "signals": ["OFF_HOURS_TRANSACTIONS", "BURST_ACTIVITY"],
        },
    ],
    PlanStepAction.COMPUTE_CENTRALITY: [
        {
            "statement": "A hub account may be aggregating funds from multiple sources before dispersal.",
            "typology": "FUNNEL_ACCOUNT",
            "signals": ["HIGH_CENTRALITY"],
        },
    ],
}


def hypothesis_generation(state: InvestigationState) -> InvestigationState:
    """
    Generate testable hypotheses from the investigation plan.
    
    Each hypothesis is tied to:
      - plan_id (which plan generated this)
      - step_id (which plan step it tests)
    """
    start_ts = time.time()
    case_id = state["case_id"]
    plan = state["current_plan"]
    log = logger.bind(case_id=case_id, plan_id=plan.plan_id if plan else "none")

    if not plan:
        log.warning("No plan found — skipping hypothesis generation")
        return state

    hypotheses: list[Hypothesis] = list(state.get("hypotheses") or [])
    existing_statements = {h.statement for h in hypotheses}

    new_hypotheses: list[Hypothesis] = []
    for step in plan.steps:
        if step.action in ACTION_HYPOTHESIS_MAP:
            for hyp_def in ACTION_HYPOTHESIS_MAP[step.action]:
                if hyp_def["statement"] in existing_statements:
                    continue  # Don't duplicate on replan
                hyp = Hypothesis(
                    plan_id=plan.plan_id,
                    step_id=step.step_id,
                    statement=hyp_def["statement"],
                    typology=hyp_def.get("typology"),
                    supporting_signals=hyp_def.get("signals", []),
                    status=HypothesisStatus.UNTESTED,
                )
                new_hypotheses.append(hyp)
                existing_statements.add(hyp_def["statement"])

    all_hypotheses = hypotheses + new_hypotheses
    duration_ms = int((time.time() - start_ts) * 1000)

    log.info(
        "Hypothesis generation complete",
        new_hypotheses=len(new_hypotheses),
        total_hypotheses=len(all_hypotheses),
        duration_ms=duration_ms,
    )

    audit = AuditRecord(
        case_id=case_id,
        actor="system:hypothesis_generation",
        action="HYPOTHESES_GENERATED",
        plan_id=plan.plan_id,
        summary=f"Generated {len(new_hypotheses)} new hypotheses ({len(all_hypotheses)} total).",
        metadata={"new": len(new_hypotheses), "total": len(all_hypotheses), "duration_ms": duration_ms},
    )

    audit_trail = list(state.get("audit_trail") or [])
    audit_trail.append(audit)

    return {
        **state,
        "hypotheses": all_hypotheses,
        "audit_trail": audit_trail,
    }
