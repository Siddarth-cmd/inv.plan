"""
Adaptive Planner Node — STOP or REPLAN decision.

Evaluates whether the investigation has sufficient evidence to conclude
or needs another planning cycle. Implements guard rails:
  - max 3 re-plan iterations
  - concrete sufficiency criteria (not arbitrary)
  
Returns STOP → decision node, or REPLAN → back to invest.planner.
"""
from __future__ import annotations

import time

import structlog

from app.agents.state import (
    AdaptivePlannerDecision,
    AuditRecord,
    EvidenceItem,
    EvidenceType,
    Finding,
    FindingSeverity,
    Hypothesis,
    HypothesisStatus,
    InvestigationState,
)

logger = structlog.get_logger("finspectra.agents.adaptive_planner")

MAX_ITERATIONS = 3
MIN_EVIDENCE_ITEMS = 3
MIN_HYPOTHESES_TESTED_RATIO = 0.5


def _compute_completeness_gaps(
    evidence: list[EvidenceItem],
    hypotheses: list[Hypothesis],
) -> list[str]:
    """Identify what's missing from the investigation."""
    gaps = []
    evidence_types_present = {e.evidence_type for e in evidence}

    if EvidenceType.TYPOLOGY_MATCH not in evidence_types_present:
        gaps.append("No typology matching has been performed")

    if EvidenceType.GRAPH_CYCLES not in evidence_types_present:
        gaps.append("Circular flow analysis not yet completed")

    untested_critical = [
        h for h in hypotheses
        if h.status == HypothesisStatus.UNTESTED
        and h.typology in ("STRUCTURING_SMURFING", "CIRCULAR_TRANSFER", "LAYERING_RAPID_PASSTHROUGH")
    ]
    if untested_critical:
        gaps.append(f"{len(untested_critical)} critical hypothesis(es) remain untested")

    return gaps


def adaptive_planner(state: InvestigationState) -> InvestigationState:
    """
    Adaptive Planner Node.
    
    Checks evidence sufficiency. Returns STOP or REPLAN.
    On REPLAN: sets replan_reason so invest.planner can adjust scope.
    On STOP: evidence is sufficient to proceed to Decision.
    """
    start_ts = time.time()
    case_id = state["case_id"]
    iteration = state.get("iteration_count", 0)
    evidence: list[EvidenceItem] = state.get("evidence") or []
    hypotheses: list[Hypothesis] = state.get("hypotheses") or []
    findings: list[Finding] = state.get("findings") or []
    analysis = state.get("analysis_result")
    plan = state.get("current_plan")

    log = logger.bind(case_id=case_id, iteration=iteration)
    log.info("Adaptive planner evaluating", evidence=len(evidence), hypotheses=len(hypotheses))

    # Hard stop: max iterations reached
    if iteration >= MAX_ITERATIONS:
        decision = AdaptivePlannerDecision.STOP
        reason = f"Max iterations ({MAX_ITERATIONS}) reached — proceeding to decision"
        log.info("Max iterations reached — STOP")
    else:
        # Evaluate sufficiency criteria
        criteria_met = 0
        total_criteria = 4
        gaps = _compute_completeness_gaps(evidence, hypotheses)

        # Criterion 1: Minimum evidence volume
        if len(evidence) >= MIN_EVIDENCE_ITEMS:
            criteria_met += 1

        # Criterion 2: Typology analysis done
        typology_done = any(e.evidence_type == EvidenceType.TYPOLOGY_MATCH for e in evidence)
        if typology_done:
            criteria_met += 1

        # Criterion 3: Hypothesis testing rate
        tested = sum(1 for h in hypotheses if h.status != HypothesisStatus.UNTESTED)
        test_rate = tested / max(len(hypotheses), 1)
        if test_rate >= MIN_HYPOTHESES_TESTED_RATIO:
            criteria_met += 1

        # Criterion 4: Analysis complete with clear signal
        if analysis and analysis.evidence_sufficient:
            criteria_met += 1

        # Escalation shortcut: if CRITICAL risk confirmed, stop immediately
        critical_findings = [f for f in findings if f.severity == FindingSeverity.CRITICAL]
        if critical_findings and analysis and analysis.risk_level in ("CRITICAL", "HIGH"):
            decision = AdaptivePlannerDecision.STOP
            reason = f"Critical risk confirmed ({len(critical_findings)} critical finding(s)) — escalating immediately"
            log.info("Critical risk shortcut — STOP", findings=len(critical_findings))
        elif criteria_met >= 3 or (analysis and analysis.evidence_sufficient):
            decision = AdaptivePlannerDecision.STOP
            reason = f"Evidence sufficient ({criteria_met}/{total_criteria} criteria met)"
            log.info("Sufficient evidence — STOP", criteria_met=criteria_met)
        elif iteration < MAX_ITERATIONS - 1 and gaps:
            decision = AdaptivePlannerDecision.REPLAN
            reason = f"Evidence gaps identified: {'; '.join(gaps[:2])}"
            log.info("Gaps found — REPLAN", gaps=len(gaps), reason=reason)
        else:
            decision = AdaptivePlannerDecision.STOP
            reason = f"Proceeding to decision with available evidence ({len(evidence)} items)"
            log.info("Default STOP", evidence=len(evidence))

    duration_ms = int((time.time() - start_ts) * 1000)

    audit = AuditRecord(
        case_id=case_id,
        actor="system:adaptive_planner",
        action=f"ADAPTIVE_DECISION_{decision.value}",
        plan_id=plan.plan_id if plan else None,
        summary=f"Adaptive decision: {decision.value}. Reason: {reason}",
        metadata={
            "decision": decision.value,
            "reason": reason,
            "iteration": iteration,
            "evidence_count": len(evidence),
            "duration_ms": duration_ms,
        },
    )

    audit_trail = list(state.get("audit_trail") or [])
    audit_trail.append(audit)

    return {
        **state,
        "adaptive_decision": decision,
        "replan_reason": reason if decision == AdaptivePlannerDecision.REPLAN else None,
        "iteration_count": iteration + 1,
        "audit_trail": audit_trail,
    }
