"""
Decision Node — Deterministic, Policy-Driven.

Takes analysis result and findings to produce a final decision.
LLMs cannot override the decision policy.
All decisions are traceable: finding_ids → decision_id.

Policy version: 1.0
"""
from __future__ import annotations

import time

import structlog

from app.agents.state import (
    AuditRecord,
    DecisionOutcome,
    Finding,
    FindingSeverity,
    InvestigationDecision,
    InvestigationState,
)

logger = structlog.get_logger("finspectra.agents.decision")

POLICY_VERSION = "1.0"


def decision_node(state: InvestigationState) -> InvestigationState:
    """
    Deterministic decision node.
    
    Policy matrix (policy_version=1.0):
      CRITICAL risk + typology → SAR_RECOMMENDED
      CRITICAL risk, no typology → ESCALATE
      HIGH risk + typology → ESCALATE
      HIGH risk, no typology → HUMAN_REVIEW
      MEDIUM risk → MONITOR
      LOW risk → CLEAR
    
    Traceability: finding_ids → decision_id
    """
    start_ts = time.time()
    case_id = state["case_id"]
    analysis = state.get("analysis_result")
    findings: list[Finding] = state.get("findings") or []
    evidence = state.get("evidence") or []
    plan = state.get("current_plan")

    log = logger.bind(case_id=case_id)

    if not analysis:
        log.warning("No analysis result — defaulting to HUMAN_REVIEW")
        outcome = DecisionOutcome.HUMAN_REVIEW
        risk_level = "UNKNOWN"
        reasons = ["Investigation completed without risk analysis — human review required"]
        required_human = "Manual review required: automated analysis could not be completed"
    else:
        risk_level = analysis.risk_level
        typology_confirmed = len(analysis.typology_matches) > 0
        critical_findings = [f for f in findings if f.severity == FindingSeverity.CRITICAL]
        high_findings = [f for f in findings if f.severity == FindingSeverity.HIGH]

        # Apply policy matrix
        if risk_level == "CRITICAL" and typology_confirmed:
            outcome = DecisionOutcome.SAR_RECOMMENDED
            required_human = (
                "Suspicious Activity Report (SAR) filing recommended. "
                "Compliance officer must review and file within regulatory deadline."
            )
        elif risk_level == "CRITICAL":
            outcome = DecisionOutcome.ESCALATE
            required_human = "CRITICAL risk without typology confirmation. Senior investigator review required."
        elif risk_level == "HIGH" and typology_confirmed:
            outcome = DecisionOutcome.ESCALATE
            required_human = "HIGH risk with confirmed typology. Escalate to compliance team."
        elif risk_level == "HIGH":
            outcome = DecisionOutcome.HUMAN_REVIEW
            required_human = "HIGH risk detected. Manual review required to confirm before escalation."
        elif risk_level == "MEDIUM":
            outcome = DecisionOutcome.MONITOR
            required_human = "Monitor account for 30 days. Re-evaluate if new suspicious activity detected."
        else:
            outcome = DecisionOutcome.CLEAR
            required_human = None

        # Build reasons
        reasons = []
        if analysis.risk_factors:
            reasons.extend(analysis.risk_factors[:5])
        if critical_findings:
            reasons.append(f"{len(critical_findings)} critical finding(s) identified")
        if typology_confirmed:
            types = [tm.get("typology", "?") for tm in analysis.typology_matches]
            reasons.append(f"Typology matches confirmed: {', '.join(types)}")
        if analysis.composite_risk_score:
            reasons.append(
                f"Composite risk score: {analysis.composite_risk_score:.3f} "
                f"(transaction: {analysis.transaction_risk_score:.3f}, "
                f"network: {analysis.network_risk_score:.3f}, "
                f"typology: {analysis.typology_risk_score:.3f})"
            )

    # Collect finding_ids and evidence_ids for traceability
    finding_ids = [f.finding_id for f in findings]
    evidence_ids = [e.evidence_id for e in evidence]

    decision = InvestigationDecision(
        case_id=case_id,
        plan_id=plan.plan_id if plan else "unknown",
        finding_ids=finding_ids,
        outcome=outcome,
        risk_level=risk_level,
        reasons=reasons,
        required_human_action=required_human,
        supporting_evidence_ids=evidence_ids,
        policy_version=POLICY_VERSION,
    )

    duration_ms = int((time.time() - start_ts) * 1000)
    log.info(
        "Decision reached",
        outcome=outcome.value,
        risk_level=risk_level,
        reasons=len(reasons),
        duration_ms=duration_ms,
    )

    audit = AuditRecord(
        case_id=case_id,
        actor="system:decision_node",
        action="DECISION_REACHED",
        plan_id=plan.plan_id if plan else None,
        entity_id=decision.decision_id,
        summary=(
            f"Decision: {outcome.value}. Risk: {risk_level}. Policy: v{POLICY_VERSION}. "
            f"Based on {len(findings)} findings and {len(evidence)} evidence items."
        ),
        metadata={
            "decision_id": decision.decision_id,
            "outcome": outcome.value,
            "risk_level": risk_level,
            "policy_version": POLICY_VERSION,
            "finding_count": len(findings),
            "evidence_count": len(evidence),
            "duration_ms": duration_ms,
        },
    )

    audit_trail = list(state.get("audit_trail") or [])
    audit_trail.append(audit)

    return {
        **state,
        "decision": decision,
        "audit_trail": audit_trail,
    }
