"""
invest.planner — The reusable LangGraph investigation planner node.

Architecture:
  - One invest.planner function (not one per alert)
  - Called via LangGraph node with per-case thread (thread_id = case_id)
  - Produces a validated InvestigationPlan (Pydantic)
  - On re-plan, increments plan version and adjusts steps based on gaps

Traceability:
  case_id → plan_id → step_id  (then downstream: → evidence_id → finding_id → decision_id)

Design constraints:
  - Deterministic plan generation (LLM cannot override plan structure)
  - LLM may be used only for the human-readable 'rationale' field if available
  - Plan references tools by ToolPreference enum (not hardcoded logic)
  - Neo4j/graph access never embedded here — tool names only
"""
from __future__ import annotations

import time
import uuid
from typing import Any

import structlog

from app.agents.state import (
    AdaptivePlannerDecision,
    AlertContext,
    AuditRecord,
    CaseContext,
    EvidenceType,
    InvestigationPlan,
    InvestigationState,
    PlanStep,
    PlanStepAction,
    ToolPreference,
)

logger = structlog.get_logger("finspectra.agents.invest_planner")


# ── Plan templates keyed by primary signal ────────────────────────────────────

def _make_step(
    action: PlanStepAction,
    priority: int,
    description: str,
    required_evidence: list[EvidenceType],
    preferred_tool: ToolPreference,
    dependencies: list[str] | None = None,
    stop_conditions: list[str] | None = None,
    escalation_conditions: list[str] | None = None,
) -> PlanStep:
    return PlanStep(
        step_id=str(uuid.uuid4()),
        action=action,
        priority=priority,
        description=description,
        required_evidence=required_evidence,
        preferred_tool=preferred_tool,
        dependencies=dependencies or [],
        stop_conditions=stop_conditions or [],
        escalation_conditions=escalation_conditions or ["CRITICAL risk confirmed by independent evidence"],
    )


def _build_baseline_steps() -> list[PlanStep]:
    """Baseline steps present in every investigation."""
    s1 = _make_step(
        PlanStepAction.GATHER_TRANSACTION_HISTORY,
        priority=1,
        description="Retrieve full transaction history for all involved accounts.",
        required_evidence=[EvidenceType.TRANSACTION_HISTORY, EvidenceType.ACCOUNT_PROFILE],
        preferred_tool=ToolPreference.DB_QUERY,
        stop_conditions=["No transactions found for account"],
    )
    s2 = _make_step(
        PlanStepAction.RESOLVE_ENTITIES,
        priority=1,
        description="Identify all entities linked to involved accounts (shared phone, email, device, UPI).",
        required_evidence=[EvidenceType.ENTITY_RELATIONSHIP, EvidenceType.DEVICE_FINGERPRINT],
        preferred_tool=ToolPreference.DB_QUERY,
        dependencies=[s1.step_id],
    )
    s3 = _make_step(
        PlanStepAction.BUILD_RELATIONSHIP_GRAPH,
        priority=2,
        description="Construct transaction relationship graph for network-level analysis.",
        required_evidence=[EvidenceType.ENTITY_RELATIONSHIP],
        preferred_tool=ToolPreference.GRAPH_QUERY,
        dependencies=[s2.step_id],
    )
    return [s1, s2, s3]


def _build_structuring_steps(base_steps: list[PlanStep]) -> list[PlanStep]:
    base_ids = [s.step_id for s in base_steps]
    s4 = _make_step(
        PlanStepAction.ANALYZE_AMOUNT_PATTERNS,
        priority=1,
        description="Analyze transaction amounts for structuring pattern (amounts just below threshold).",
        required_evidence=[EvidenceType.AMOUNT_PATTERN, EvidenceType.RULE_SIGNAL],
        preferred_tool=ToolPreference.SIGNAL_COMPUTE,
        dependencies=[base_ids[0]],
        stop_conditions=["Amounts uniformly distributed with no clustering below threshold"],
    )
    s5 = _make_step(
        PlanStepAction.ANALYZE_TEMPORAL_PATTERNS,
        priority=2,
        description="Examine transaction timing to detect coordinated structuring bursts.",
        required_evidence=[EvidenceType.TEMPORAL_PATTERN],
        preferred_tool=ToolPreference.SIGNAL_COMPUTE,
        dependencies=[s4.step_id],
    )
    s6 = _make_step(
        PlanStepAction.MATCH_TYPOLOGIES,
        priority=1,
        description="Match against structuring/smurfing AML typology rules.",
        required_evidence=[EvidenceType.TYPOLOGY_MATCH],
        preferred_tool=ToolPreference.TYPOLOGY_MATCH,
        dependencies=[s4.step_id, s5.step_id],
        escalation_conditions=["Structuring confirmed across 3+ accounts"],
    )
    return [s4, s5, s6]


def _build_circular_steps(base_steps: list[PlanStep]) -> list[PlanStep]:
    base_ids = [s.step_id for s in base_steps]
    s4 = _make_step(
        PlanStepAction.DETECT_GRAPH_CYCLES,
        priority=1,
        description="Detect circular money flows in the transaction graph.",
        required_evidence=[EvidenceType.GRAPH_CYCLES],
        preferred_tool=ToolPreference.GRAPH_QUERY,
        dependencies=[base_ids[2]],  # after graph build
        stop_conditions=["No cycles found in transaction graph"],
        escalation_conditions=["Cycle confirmed with >3 hops and >500K INR"],
    )
    s5 = _make_step(
        PlanStepAction.MATCH_TYPOLOGIES,
        priority=1,
        description="Match against circular transfer and round-trip AML typologies.",
        required_evidence=[EvidenceType.TYPOLOGY_MATCH],
        preferred_tool=ToolPreference.TYPOLOGY_MATCH,
        dependencies=[s4.step_id],
    )
    return [s4, s5]


def _build_layering_steps(base_steps: list[PlanStep]) -> list[PlanStep]:
    base_ids = [s.step_id for s in base_steps]
    s4 = _make_step(
        PlanStepAction.COMPUTE_CENTRALITY,
        priority=1,
        description="Compute account centrality to identify hub/funnel accounts.",
        required_evidence=[EvidenceType.GRAPH_CENTRALITY],
        preferred_tool=ToolPreference.GRAPH_QUERY,
        dependencies=[base_ids[2]],
    )
    s5 = _make_step(
        PlanStepAction.ASSESS_COUNTERPARTIES,
        priority=2,
        description="Assess rapid pass-through ratios for potential layering behavior.",
        required_evidence=[EvidenceType.COUNTERPARTY_ANALYSIS],
        preferred_tool=ToolPreference.GRAPH_QUERY,
        dependencies=[s4.step_id],
    )
    s6 = _make_step(
        PlanStepAction.MATCH_TYPOLOGIES,
        priority=1,
        description="Match against layering and rapid movement typologies.",
        required_evidence=[EvidenceType.TYPOLOGY_MATCH],
        preferred_tool=ToolPreference.TYPOLOGY_MATCH,
        dependencies=[s5.step_id],
    )
    return [s4, s5, s6]


def _build_mule_steps(base_steps: list[PlanStep]) -> list[PlanStep]:
    base_ids = [s.step_id for s in base_steps]
    s4 = _make_step(
        PlanStepAction.EVALUATE_DEVICE_SIGNALS,
        priority=1,
        description="Identify accounts sharing device/IP identifiers (mule network indicator).",
        required_evidence=[EvidenceType.DEVICE_FINGERPRINT, EvidenceType.ENTITY_RELATIONSHIP],
        preferred_tool=ToolPreference.GRAPH_QUERY,
        dependencies=[base_ids[1]],  # after entity resolution
    )
    s5 = _make_step(
        PlanStepAction.MATCH_TYPOLOGIES,
        priority=1,
        description="Match against mule account network typology.",
        required_evidence=[EvidenceType.TYPOLOGY_MATCH],
        preferred_tool=ToolPreference.TYPOLOGY_MATCH,
        dependencies=[s4.step_id],
        escalation_conditions=["3+ accounts confirmed sharing single device"],
    )
    return [s4, s5]


def _build_large_transfer_steps(base_steps: list[PlanStep]) -> list[PlanStep]:
    base_ids = [s.step_id for s in base_steps]
    s4 = _make_step(
        PlanStepAction.ANALYZE_AMOUNT_PATTERNS,
        priority=1,
        description="Document the unusually large transfer amount against account baseline.",
        required_evidence=[EvidenceType.AMOUNT_PATTERN, EvidenceType.ANOMALY_SCORE],
        preferred_tool=ToolPreference.SIGNAL_COMPUTE,
        dependencies=[base_ids[0]],
    )
    s5 = _make_step(
        PlanStepAction.ASSESS_COUNTERPARTIES,
        priority=2,
        description="Assess the receiving counterparty for risk indicators.",
        required_evidence=[EvidenceType.COUNTERPARTY_ANALYSIS, EvidenceType.ENTITY_RELATIONSHIP],
        preferred_tool=ToolPreference.DB_QUERY,
        dependencies=[s4.step_id],
    )
    return [s4, s5]


def _build_synthesis_steps(domain_steps: list[PlanStep]) -> list[PlanStep]:
    """Final synthesis steps — always added after domain-specific steps."""
    dep_ids = [s.step_id for s in domain_steps if s.action == PlanStepAction.MATCH_TYPOLOGIES
               or s.action == PlanStepAction.ASSESS_COUNTERPARTIES]
    if not dep_ids and domain_steps:
        dep_ids = [domain_steps[-1].step_id]

    s_synth = _make_step(
        PlanStepAction.SYNTHESIZE_FINDINGS,
        priority=3,
        description="Synthesize all gathered evidence into investigation findings.",
        required_evidence=[EvidenceType.RULE_SIGNAL, EvidenceType.TYPOLOGY_MATCH],
        preferred_tool=ToolPreference.NONE,
        dependencies=dep_ids,
        stop_conditions=[
            "All hypotheses tested",
            "Evidence complete for all plan steps",
        ],
    )
    s_decision = _make_step(
        PlanStepAction.GENERATE_DECISION,
        priority=1,
        description="Apply deterministic decision policy to produce final outcome.",
        required_evidence=[],
        preferred_tool=ToolPreference.NONE,
        dependencies=[s_synth.step_id],
        stop_conditions=["Decision reached: CLEAR", "Decision reached: SAR_RECOMMENDED"],
        escalation_conditions=["CRITICAL risk with confirmed typology match"],
    )
    return [s_synth, s_decision]


def _select_primary_signals(alert: AlertContext, rule_signals: list[dict]) -> set[str]:
    """Extract primary signal types from the alert to drive plan selection."""
    signals = set()
    for sig in rule_signals:
        stype = sig.get("signal_type", "").upper()
        signals.add(stype)

    # Amount-based inference
    if alert.amount >= 500_000:
        signals.add("LARGE_TRANSFER")
    if alert.anomaly_score >= 0.7:
        signals.add("HIGH_ANOMALY")

    # Keyword inference from reasons
    for reason in alert.reasons:
        rl = reason.lower()
        if "structur" in rl or "smurp" in rl:
            signals.add("STRUCTURING")
        if "circular" in rl or "round" in rl:
            signals.add("CIRCULAR")
        if "layering" in rl or "pass-through" in rl or "rapid" in rl:
            signals.add("LAYERING")
        if "device" in rl or "mule" in rl:
            signals.add("MULE")

    return signals


def _build_objective(alert: AlertContext, signals: set[str]) -> str:
    """Generate a human-readable investigation objective."""
    patterns = []
    if "STRUCTURING" in signals:
        patterns.append("potential structuring/smurfing")
    if "CIRCULAR" in signals:
        patterns.append("circular money movement")
    if "LAYERING" in signals:
        patterns.append("rapid pass-through/layering")
    if "MULE" in signals:
        patterns.append("mule account network activity")
    if "LARGE_TRANSFER" in signals:
        patterns.append("large-value transfer")
    if not patterns:
        patterns.append("anomalous transaction activity")

    pattern_str = " and ".join(patterns)
    return (
        f"Investigate alert {alert.alert_id} for {pattern_str}. "
        f"Transaction amount: {alert.amount:,.0f} INR. "
        f"Anomaly score: {alert.anomaly_score:.3f}. "
        f"Determine risk level and produce a decision recommendation."
    )


def _build_rationale(alert: AlertContext, signals: set[str], is_replan: bool, replan_reason: str | None) -> str:
    """Build the plan rationale string."""
    if is_replan:
        return (
            f"Re-plan triggered: {replan_reason or 'Evidence insufficient'}. "
            f"Signals present: {', '.join(sorted(signals)) or 'general anomaly'}. "
            f"Expanding investigation scope with additional evidence steps."
        )
    signal_str = ", ".join(sorted(signals)) if signals else "general anomaly (score-based)"
    return (
        f"Alert priority: {alert.initial_priority}. "
        f"Triggered signals: {signal_str}. "
        f"Plan selected based on dominant signal types and amount ({alert.amount:,.0f} INR). "
        f"Deterministic plan generation — LLM not used for plan structure."
    )


# ── Main invest.planner node ──────────────────────────────────────────────────

def invest_planner(state: InvestigationState) -> InvestigationState:
    """
    invest.planner — Reusable LangGraph node.

    Called:
      1. At investigation start (initial plan)
      2. When adaptive_planner returns REPLAN

    Produces a validated InvestigationPlan with full step traceability.
    Does NOT embed graph logic — references ToolPreference by name only.
    """
    start_ts = time.time()
    case_id = state["case_id"]
    log = logger.bind(case_id=case_id)

    is_replan = state.get("current_plan") is not None
    replan_reason = state.get("replan_reason")
    iteration = state.get("iteration_count", 0)

    log.info("invest.planner starting", is_replan=is_replan, iteration=iteration)

    case_context: CaseContext = state["case_context"]
    alert: AlertContext = case_context.alert

    # Extract rule signals from alert
    rule_signals: list[dict] = alert.rule_signals or []

    # Determine primary signal set
    signals = _select_primary_signals(alert, rule_signals)
    log.info("Signals identified", signals=sorted(signals))

    # Build base steps (always present)
    base_steps = _build_baseline_steps()

    # Build domain-specific steps based on signals
    domain_steps: list[PlanStep] = []
    if "STRUCTURING" in signals:
        domain_steps.extend(_build_structuring_steps(base_steps))
    if "CIRCULAR" in signals:
        domain_steps.extend(_build_circular_steps(base_steps))
    if "LAYERING" in signals:
        domain_steps.extend(_build_layering_steps(base_steps))
    if "MULE" in signals:
        domain_steps.extend(_build_mule_steps(base_steps))
    if "LARGE_TRANSFER" in signals or "HIGH_ANOMALY" in signals:
        domain_steps.extend(_build_large_transfer_steps(base_steps))

    # On replan: if no new domain steps were found, add counterparty assessment
    if is_replan and not domain_steps:
        log.info("Replan with expanded scope — adding counterparty and temporal steps")
        domain_steps.extend(_build_large_transfer_steps(base_steps))

    # Synthesis steps (always at end)
    all_steps = base_steps + domain_steps
    synthesis = _build_synthesis_steps(domain_steps or base_steps)
    all_steps.extend(synthesis)

    # Remove duplicate actions (keep first occurrence, highest priority)
    seen_actions: set[PlanStepAction] = set()
    deduped: list[PlanStep] = []
    for step in all_steps:
        if step.action not in seen_actions:
            seen_actions.add(step.action)
            deduped.append(step)
    all_steps = deduped

    # Build the plan
    prev_plan = state.get("current_plan")
    plan = InvestigationPlan(
        case_id=case_id,
        alert_id=alert.alert_id,
        objective=_build_objective(alert, signals),
        rationale=_build_rationale(alert, signals, is_replan, replan_reason),
        steps=all_steps,
        version=(prev_plan.version + 1 if prev_plan else 1),
    )

    duration_ms = int((time.time() - start_ts) * 1000)
    log.info(
        "invest.planner complete",
        plan_id=plan.plan_id,
        steps=len(plan.steps),
        version=plan.version,
        duration_ms=duration_ms,
    )

    # Build audit record
    audit = AuditRecord(
        case_id=case_id,
        actor="system:invest.planner",
        action="PLAN_CREATED" if not is_replan else "PLAN_REVISED",
        plan_id=plan.plan_id,
        summary=(
            f"{'Initial' if not is_replan else 'Revised'} investigation plan created. "
            f"Plan ID: {plan.plan_id}. "
            f"Steps: {len(plan.steps)}. "
            f"Objective: {plan.objective[:100]}..."
        ),
        metadata={
            "plan_id": plan.plan_id,
            "step_count": len(plan.steps),
            "signals": sorted(signals),
            "version": plan.version,
            "duration_ms": duration_ms,
        },
    )

    plan_history = list(state.get("plan_history") or [])
    plan_history.append(plan)
    audit_trail = list(state.get("audit_trail") or [])
    audit_trail.append(audit)

    return {
        **state,
        "current_plan": plan,
        "plan_history": plan_history,
        "current_step_index": 0,
        "audit_trail": audit_trail,
        "adaptive_decision": None,    # Reset for new plan cycle
        "replan_reason": None,
    }
