"""
Decision Agent — Agent 4.

Policy-driven decision logic. Deterministic. Auditable.
LLM cannot make independent financial decisions.

Possible outcomes:
- CLEAR: Risk is low and no significant signals
- MONITOR: Low-medium risk, warrants ongoing monitoring
- ESCALATE: High risk, requires senior investigator review
- SAR_RECOMMENDED: CRITICAL risk, Suspicious Activity Report recommended
- HUMAN_REVIEW: Inconclusive — human judgment required
"""
from __future__ import annotations

import time
from datetime import datetime, timezone

from app.agents.state import InvestigationState
from app.core.logging import get_logger

logger = get_logger("decision_agent")

POLICY_VERSION = "1.0"


def decision_agent(state: InvestigationState) -> InvestigationState:
    """
    Decision Agent node for LangGraph.

    Reads: risk_level, composite_risk_score, typology_matches,
           triggered_signals, anomaly_score, evidence
    Writes: decision, decision_reasons, required_human_action
    """
    start_time = time.monotonic()
    investigation_id = state["investigation_id"]

    logger.info("decision_agent.start", investigation_id=investigation_id)

    try:
        risk_level = state["risk_level"]
        composite_score = state["composite_risk_score"]
        typology_matches = state["typology_matches"]
        signals = state["triggered_signals"]
        anomaly_score = state["anomaly_score"]
        errors = state["errors"]

        decision_reasons: list[str] = []
        required_human_action: str | None = None

        # === Policy Rules (in priority order) ===

        # Rule 1: Any CRITICAL typology match → SAR recommended
        critical_typologies = [
            tm for tm in typology_matches
            if tm.get("confidence", 0) >= 0.85 and tm["typology"] in (
                "CIRCULAR_TRANSACTIONS", "STRUCTURING", "LAYERING"
            )
        ]
        if critical_typologies:
            decision = "SAR_RECOMMENDED"
            for tm in critical_typologies:
                decision_reasons.append(
                    f"High-confidence {tm['typology']} typology match (confidence: {tm['confidence']:.0%})."
                )
            required_human_action = (
                "Compliance officer must review this case within 24 hours. "
                "SAR filing recommended per AML policy. Do not alert subject."
            )

        # Rule 2: CRITICAL risk score → SAR recommended
        elif risk_level == "CRITICAL" and composite_score >= 0.85:
            decision = "SAR_RECOMMENDED"
            decision_reasons.append(f"CRITICAL risk level with composite score {composite_score:.2f}.")
            decision_reasons.append(f"Anomaly score: {anomaly_score:.2f}.")
            required_human_action = (
                "Compliance officer must review this case within 24 hours. "
                "Consider SAR filing. Do not alert subject."
            )

        # Rule 3: HIGH risk → Escalate
        elif risk_level == "HIGH":
            decision = "ESCALATE"
            decision_reasons.append(f"HIGH risk level detected (composite score: {composite_score:.2f}).")
            if signals:
                high_sigs = [s for s in signals if s.get("severity") in ("HIGH", "CRITICAL")]
                if high_sigs:
                    decision_reasons.append(f"{len(high_sigs)} high-severity signal(s) triggered.")
            required_human_action = "Senior investigator review required within 48 hours."

        # Rule 4: MEDIUM risk → Monitor
        elif risk_level == "MEDIUM":
            decision = "MONITOR"
            decision_reasons.append(f"MEDIUM risk level (composite score: {composite_score:.2f}).")
            decision_reasons.append("Insufficient evidence to escalate; continued monitoring recommended.")

        # Rule 5: Errors during investigation → Human review
        elif errors:
            decision = "HUMAN_REVIEW"
            decision_reasons.append("Investigation pipeline encountered errors — manual review required.")
            decision_reasons.append(f"Errors: {'; '.join(e.get('error', 'unknown') for e in errors[:3])}")
            required_human_action = "Investigate pipeline errors and manually assess this alert."

        # Rule 6: LOW risk → Clear
        else:
            decision = "CLEAR"
            decision_reasons.append(f"LOW risk level (composite score: {composite_score:.2f}).")
            decision_reasons.append("No significant signals or typology matches detected.")
            decision_reasons.append("No escalation warranted based on current evidence.")

        duration_ms = int((time.monotonic() - start_time) * 1000)
        audit_event = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "actor": "decision_agent",
            "action": "DECISION_MADE",
            "summary": f"Decision: {decision}. Risk: {risk_level} ({composite_score:.2f}). Policy v{POLICY_VERSION}.",
            "metadata": {
                "decision": decision,
                "risk_level": risk_level,
                "composite_score": composite_score,
                "policy_version": POLICY_VERSION,
                "duration_ms": duration_ms,
            },
        }

        logger.info(
            "decision_agent.complete",
            investigation_id=investigation_id,
            decision=decision,
            risk_level=risk_level,
            composite_score=composite_score,
            duration_ms=duration_ms,
        )

        return {
            **state,
            "decision": decision,
            "decision_reasons": decision_reasons,
            "required_human_action": required_human_action,
            "audit_events": state["audit_events"] + [audit_event],
        }

    except Exception as e:
        logger.error("decision_agent.error", investigation_id=investigation_id, error=str(e))
        error_event = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "actor": "decision_agent",
            "action": "DECISION_ERROR",
            "summary": f"Decision agent encountered an error: {str(e)}",
            "metadata": {"error": str(e)},
        }
        return {
            **state,
            "decision": "HUMAN_REVIEW",
            "decision_reasons": [f"Agent error: {str(e)}"],
            "errors": state["errors"] + [{"agent": "decision", "error": str(e)}],
            "audit_events": state["audit_events"] + [error_event],
        }
