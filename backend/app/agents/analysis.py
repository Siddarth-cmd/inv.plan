"""
Analysis & Reasoning Node.

Synthesizes all gathered evidence into structured findings and
a composite risk assessment. Deterministic scoring — no LLM inference
of facts. LLM used only for narrative summary if configured.

Traceability: evidence_id → finding_id → (feeds into decision_id)
"""
from __future__ import annotations

import time
from typing import Any

import structlog

from app.agents.state import (
    AlertContext,
    AnalysisResult,
    AuditRecord,
    CaseContext,
    EvidenceItem,
    EvidenceType,
    Finding,
    FindingSeverity,
    Hypothesis,
    HypothesisStatus,
    InvestigationState,
)

logger = structlog.get_logger("finspectra.agents.analysis")


# ── Risk scoring ──────────────────────────────────────────────────────────────

def _score_transaction_risk(alert: AlertContext, evidence: list[EvidenceItem]) -> float:
    """Score based on anomaly score, amount, and amount pattern evidence."""
    score = alert.anomaly_score * 0.4  # ML component (max 0.4)

    # Amount risk
    if alert.amount >= 2_000_000:
        score += 0.3
    elif alert.amount >= 500_000:
        score += 0.2
    elif alert.amount >= 100_000:
        score += 0.1

    # Amount pattern deviations
    for ev in evidence:
        if ev.evidence_type == EvidenceType.AMOUNT_PATTERN:
            z = ev.data.get("z_score", 0)
            if z > 3:
                score += 0.15
            elif z > 2:
                score += 0.1
            below_thresh = ev.data.get("below_threshold_count", 0)
            if below_thresh >= 3:
                score += 0.15  # structuring signal

    return min(score, 1.0)


def _score_network_risk(evidence: list[EvidenceItem]) -> float:
    """Score based on graph evidence: cycles, high centrality, shared devices."""
    score = 0.0

    for ev in evidence:
        if ev.evidence_type == EvidenceType.GRAPH_CYCLES:
            cycles = ev.data.get("cycles", [])
            if cycles:
                score += 0.3 + 0.05 * len(cycles)

        elif ev.evidence_type == EvidenceType.GRAPH_CENTRALITY:
            hubs = ev.data.get("high_centrality_nodes", [])
            if hubs:
                score += 0.2

        elif ev.evidence_type == EvidenceType.DEVICE_FINGERPRINT:
            shared = ev.data.get("shared_devices", [])
            if shared:
                max_acc = max((d.get("account_count", 0) for d in shared), default=0)
                score += min(0.1 * max_acc, 0.4)

        elif ev.evidence_type == EvidenceType.COUNTERPARTY_ANALYSIS:
            passthrough = ev.data.get("passthrough_accounts", [])
            if passthrough:
                top_ratio = max((p.get("passthrough_ratio", 0) for p in passthrough), default=0)
                score += top_ratio * 0.3

    return min(score, 1.0)


def _score_typology_risk(evidence: list[EvidenceItem]) -> float:
    """Score based on confirmed typology matches and their confidence."""
    score = 0.0
    for ev in evidence:
        if ev.evidence_type == EvidenceType.TYPOLOGY_MATCH:
            typology = ev.data.get("typology", "")
            if not typology:
                continue
            # Weight by typology severity
            severity_weight = {
                "CIRCULAR_TRANSFER": 0.9,
                "STRUCTURING_SMURFING": 0.85,
                "LAYERING_RAPID_PASSTHROUGH": 0.85,
                "MULE_ACCOUNT_NETWORK": 0.8,
                "LARGE_VALUE_TRANSFER": 0.6,
                "HIGH_VELOCITY_TRANSACTIONS": 0.5,
            }.get(typology, 0.5)
            score = max(score, ev.confidence * severity_weight)
    return min(score, 1.0)


def _risk_level_from_score(score: float) -> str:
    if score >= 0.8:
        return "CRITICAL"
    elif score >= 0.6:
        return "HIGH"
    elif score >= 0.35:
        return "MEDIUM"
    return "LOW"


def _build_findings(
    case_id: str,
    plan_id: str,
    evidence: list[EvidenceItem],
    hypotheses: list[Hypothesis],
) -> list[Finding]:
    """Derive findings from evidence items. Each finding traces back to evidence_ids."""
    findings: list[Finding] = []

    # Finding from typology matches
    typology_evidence = [e for e in evidence if e.evidence_type == EvidenceType.TYPOLOGY_MATCH
                         and e.data.get("typology")]
    for ev in typology_evidence:
        typology = ev.data.get("typology", "")
        confidence = ev.confidence
        severity_map = {
            "CIRCULAR_TRANSFER": FindingSeverity.CRITICAL,
            "STRUCTURING_SMURFING": FindingSeverity.HIGH,
            "LAYERING_RAPID_PASSTHROUGH": FindingSeverity.HIGH,
            "MULE_ACCOUNT_NETWORK": FindingSeverity.HIGH,
            "LARGE_VALUE_TRANSFER": FindingSeverity.MEDIUM,
            "HIGH_VELOCITY_TRANSACTIONS": FindingSeverity.MEDIUM,
        }
        severity = severity_map.get(typology, FindingSeverity.MEDIUM)

        # Link to hypothesis
        hyp_id = next(
            (h.hypothesis_id for h in hypotheses if h.typology == typology), None
        )

        findings.append(Finding(
            case_id=case_id,
            plan_id=plan_id,
            evidence_ids=[ev.evidence_id],
            hypothesis_id=hyp_id,
            title=f"AML Typology Match: {typology.replace('_', ' ').title()}",
            description=ev.description,
            severity=severity,
            typology=typology,
            confidence=confidence,
            tags=["typology", typology.lower()],
        ))

    # Finding from graph cycles
    cycle_evidence = [e for e in evidence if e.evidence_type == EvidenceType.GRAPH_CYCLES
                      and e.data.get("cycles")]
    if cycle_evidence:
        hyp_id = next(
            (h.hypothesis_id for h in hypotheses if h.typology == "CIRCULAR_TRANSFER"), None
        )
        findings.append(Finding(
            case_id=case_id,
            plan_id=plan_id,
            evidence_ids=[e.evidence_id for e in cycle_evidence],
            hypothesis_id=hyp_id,
            title="Circular Money Flow Detected in Transaction Graph",
            description=cycle_evidence[0].description,
            severity=FindingSeverity.CRITICAL,
            typology="CIRCULAR_TRANSFER",
            confidence=0.85,
            tags=["graph", "circular"],
        ))

    # Finding from device sharing
    device_evidence = [e for e in evidence if e.evidence_type == EvidenceType.DEVICE_FINGERPRINT
                       and e.data.get("shared_devices")]
    if device_evidence:
        shared = device_evidence[0].data.get("shared_devices", [])
        findings.append(Finding(
            case_id=case_id,
            plan_id=plan_id,
            evidence_ids=[e.evidence_id for e in device_evidence],
            title=f"Shared Device: {len(shared)} Device(s) Linked to Multiple Accounts",
            description=device_evidence[0].description,
            severity=FindingSeverity.HIGH,
            typology="MULE_ACCOUNT_NETWORK",
            confidence=0.8,
            tags=["device", "entity_resolution"],
        ))

    # Finding from anomaly score
    for ev in evidence:
        if ev.evidence_type == EvidenceType.ANOMALY_SCORE:
            findings.append(Finding(
                case_id=case_id,
                plan_id=plan_id,
                evidence_ids=[ev.evidence_id],
                title=f"High ML Anomaly Score: {ev.data.get('anomaly_score', 0):.3f}",
                description=ev.description,
                severity=FindingSeverity.MEDIUM,
                confidence=ev.confidence,
                tags=["ml", "anomaly"],
            ))

    return findings


def analysis_reasoning(state: InvestigationState) -> InvestigationState:
    """
    Analysis & Reasoning Node.
    
    Synthesizes evidence into findings and risk scores.
    Deterministic scoring — no LLM fact invention.
    """
    start_ts = time.time()
    case_id = state["case_id"]
    plan = state["current_plan"]
    case_context: CaseContext = state["case_context"]
    evidence: list[EvidenceItem] = state.get("evidence") or []
    hypotheses: list[Hypothesis] = state.get("hypotheses") or []

    log = logger.bind(case_id=case_id, plan_id=plan.plan_id if plan else "none")
    log.info("Analysis starting", evidence_count=len(evidence))

    alert: AlertContext = case_context.alert
    plan_id = plan.plan_id if plan else "unknown"

    # Score each risk dimension
    txn_risk = _score_transaction_risk(alert, evidence)
    net_risk = _score_network_risk(evidence)
    typology_risk = _score_typology_risk(evidence)

    # Composite score (weighted)
    composite = (txn_risk * 0.35 + net_risk * 0.30 + typology_risk * 0.35)
    risk_level = _risk_level_from_score(composite)

    # Build findings (evidence_id → finding_id)
    findings = list(state.get("findings") or [])
    new_findings = _build_findings(case_id, plan_id, evidence, hypotheses)
    all_findings = findings + new_findings

    # Build risk factors and evidence lists
    risk_factors: list[str] = []
    positive_evidence: list[str] = []
    negative_evidence: list[str] = []
    uncertainties: list[str] = []
    typology_matches: list[dict] = []

    for ev in evidence:
        if ev.evidence_type == EvidenceType.TYPOLOGY_MATCH:
            data = ev.data
            if data.get("typology"):
                typology_matches.append(data)
                risk_factors.append(f"Typology match: {data['typology']} (confidence: {ev.confidence:.0%})")

        if ev.evidence_type == EvidenceType.GRAPH_CYCLES:
            cycles = ev.data.get("cycles", [])
            if cycles:
                risk_factors.append(f"Circular money flow: {len(cycles)} cycle(s) detected")
            else:
                negative_evidence.append("No circular flows in transaction graph")

        if ev.evidence_type == EvidenceType.DEVICE_FINGERPRINT:
            shared = ev.data.get("shared_devices", [])
            if shared:
                risk_factors.append(f"Shared device identifiers: {len(shared)} device(s) used by multiple accounts")
            else:
                negative_evidence.append("No shared device identifiers detected")

        if ev.evidence_type == EvidenceType.AMOUNT_PATTERN:
            z = ev.data.get("z_score", 0)
            below = ev.data.get("below_threshold_count", 0)
            if z > 2:
                risk_factors.append(f"Transaction amount is {z:.1f} std deviations above account mean")
            if below >= 3:
                risk_factors.append(f"{below} transactions in structuring zone (75K–100K INR)")
            if z <= 1:
                negative_evidence.append("Transaction amount is within normal range")

        if ev.evidence_type == EvidenceType.COUNTERPARTY_ANALYSIS:
            passthrough = ev.data.get("passthrough_accounts", [])
            if passthrough:
                top = passthrough[0]
                risk_factors.append(
                    f"High pass-through ratio: {top['account']} forwarded {top['passthrough_ratio']:.0%} of received funds"
                )

    # Uncertainties from unsupported hypotheses
    for hyp in hypotheses:
        if hyp.status == HypothesisStatus.INCONCLUSIVE:
            uncertainties.append(f"Hypothesis inconclusive: {hyp.statement[:80]}...")
        elif hyp.status == HypothesisStatus.UNTESTED:
            uncertainties.append(f"Hypothesis untested due to missing data: {hyp.statement[:60]}...")

    if alert.anomaly_score >= 0.7:
        risk_factors.append(f"ML anomaly score {alert.anomaly_score:.3f} indicates statistical outlier")
    elif alert.anomaly_score <= 0.3:
        negative_evidence.append(f"ML anomaly score {alert.anomaly_score:.3f} is relatively low")

    # Evidence sufficiency check
    supported_hypotheses = sum(1 for h in hypotheses if h.status == HypothesisStatus.SUPPORTED)
    total_hypotheses = len(hypotheses)
    evidence_sufficient = (
        len(evidence) >= 5
        and (total_hypotheses == 0 or supported_hypotheses / max(total_hypotheses, 1) >= 0.5)
    )

    narrative = _build_narrative(
        case_id=case_id,
        risk_level=risk_level,
        composite=composite,
        risk_factors=risk_factors,
        negative_evidence=negative_evidence,
        typology_matches=typology_matches,
        findings=all_findings,
    )

    analysis = AnalysisResult(
        case_id=case_id,
        plan_id=plan_id,
        composite_risk_score=round(composite, 4),
        transaction_risk_score=round(txn_risk, 4),
        network_risk_score=round(net_risk, 4),
        typology_risk_score=round(typology_risk, 4),
        risk_level=risk_level,
        risk_factors=risk_factors,
        positive_evidence=positive_evidence,
        negative_evidence=negative_evidence,
        uncertainties=uncertainties,
        typology_matches=typology_matches,
        narrative=narrative,
        evidence_sufficient=evidence_sufficient,
    )

    duration_ms = int((time.time() - start_ts) * 1000)
    log.info(
        "Analysis complete",
        risk_level=risk_level,
        composite=composite,
        findings=len(new_findings),
        evidence_sufficient=evidence_sufficient,
        duration_ms=duration_ms,
    )

    audit = AuditRecord(
        case_id=case_id,
        actor="system:analysis_reasoning",
        action="ANALYSIS_COMPLETE",
        plan_id=plan_id,
        summary=(
            f"Risk analysis complete. Level: {risk_level}. Score: {composite:.3f}. "
            f"Findings: {len(new_findings)}. "
            f"Typology matches: {len(typology_matches)}. Evidence sufficient: {evidence_sufficient}."
        ),
        metadata={
            "risk_level": risk_level,
            "composite_score": composite,
            "txn_risk": txn_risk,
            "net_risk": net_risk,
            "typology_risk": typology_risk,
            "findings": len(new_findings),
            "evidence_sufficient": evidence_sufficient,
            "duration_ms": duration_ms,
        },
    )

    audit_trail = list(state.get("audit_trail") or [])
    audit_trail.append(audit)

    return {
        **state,
        "analysis_result": analysis,
        "findings": all_findings,
        "audit_trail": audit_trail,
    }


def _build_narrative(
    case_id: str,
    risk_level: str,
    composite: float,
    risk_factors: list[str],
    negative_evidence: list[str],
    typology_matches: list[dict],
    findings: list[Finding],
) -> str:
    """Build a deterministic narrative from structured data. LLM not required."""
    lines = [
        f"Case {case_id}: Risk Assessment — {risk_level} (score: {composite:.2f})",
        "",
    ]
    if risk_factors:
        lines.append("Risk Factors Identified:")
        for rf in risk_factors[:8]:
            lines.append(f"  • {rf}")
        lines.append("")
    if typology_matches:
        lines.append("AML Typology Matches:")
        for tm in typology_matches:
            lines.append(f"  • {tm.get('typology', '?')}: confidence {tm.get('confidence', 0):.0%}")
        lines.append("")
    if negative_evidence:
        lines.append("Mitigating Evidence:")
        for ne in negative_evidence[:4]:
            lines.append(f"  • {ne}")
    lines.append("")
    lines.append(f"Total findings: {len(findings)}")
    return "\n".join(lines)
