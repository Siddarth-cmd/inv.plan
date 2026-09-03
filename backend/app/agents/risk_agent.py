"""
Risk Agent — Agent 3.

Evaluates risk across:
- Transaction risk
- Customer risk
- Network/entity risk
- Typology evidence
- ML anomaly evidence

Returns: LOW, MEDIUM, HIGH, CRITICAL with full reasoning.
Scoring is deterministic. LLM can only summarize, not override.
"""
from __future__ import annotations

import time
from datetime import datetime, timezone

from app.agents.state import InvestigationState
from app.core.logging import get_logger
from app.typology.matcher import run_typology_matching

import pandas as pd

logger = get_logger("risk_agent")

# Policy-driven risk score thresholds
RISK_THRESHOLDS = {
    "LOW": 0.30,
    "MEDIUM": 0.55,
    "HIGH": 0.75,
    "CRITICAL": 0.90,
}

# Component weights (sum = 1.0)
WEIGHT_ANOMALY = 0.25
WEIGHT_SIGNALS = 0.30
WEIGHT_TYPOLOGY = 0.25
WEIGHT_NETWORK = 0.20


def risk_agent(state: InvestigationState) -> InvestigationState:
    """
    Risk Agent node for LangGraph.

    Reads: anomaly_score, triggered_signals, evidence, entity_relationships,
           graph_metrics, all_transactions
    Writes: risk_level, composite_risk_score, risk_factors, positive_evidence,
            negative_evidence, uncertainties, typology_matches, risk_narrative
    """
    start_time = time.monotonic()
    investigation_id = state["investigation_id"]

    logger.info("risk_agent.start", investigation_id=investigation_id)

    try:
        all_transactions = state["all_transactions"]
        txn_df = pd.DataFrame(all_transactions) if all_transactions else pd.DataFrame()

        # === Run Typology Matching ===
        typology_matches = []
        if not txn_df.empty:
            try:
                matches = run_typology_matching(txn_df)
                typology_matches = [m.to_dict() for m in matches]
            except Exception as e:
                logger.warning("risk_agent.typology_error", error=str(e))

        # === Component Risk Scores ===

        # 1. Anomaly score (model output)
        anomaly_score = state["anomaly_score"]
        anomaly_risk = anomaly_score  # Already normalized [0,1]

        # 2. Signal-based risk
        signals = state["triggered_signals"]
        if signals:
            signal_scores = [s.get("score", 0) for s in signals]
            signal_risk = min(max(signal_scores) * 0.7 + sum(signal_scores) / len(signal_scores) * 0.3, 1.0)
        else:
            signal_risk = 0.0

        # 3. Typology risk
        if typology_matches:
            typology_confidences = [m.get("confidence", 0) for m in typology_matches]
            typology_risk = min(max(typology_confidences) * 0.6 + sum(typology_confidences) / len(typology_confidences) * 0.4, 1.0)
        else:
            typology_risk = 0.0

        # 4. Network risk
        graph_metrics = state["graph_metrics"]
        cycle_count = graph_metrics.get("cycle_count", 0)
        entity_rel_count = len(state["entity_relationships"])
        network_risk = min(cycle_count * 0.3 + entity_rel_count * 0.05, 1.0)

        # === Composite Score ===
        composite_score = (
            WEIGHT_ANOMALY * anomaly_risk +
            WEIGHT_SIGNALS * signal_risk +
            WEIGHT_TYPOLOGY * typology_risk +
            WEIGHT_NETWORK * network_risk
        )
        composite_score = float(min(composite_score, 1.0))

        # === Risk Level (policy-driven) ===
        if composite_score >= RISK_THRESHOLDS["CRITICAL"]:
            risk_level = "CRITICAL"
        elif composite_score >= RISK_THRESHOLDS["HIGH"]:
            risk_level = "HIGH"
        elif composite_score >= RISK_THRESHOLDS["MEDIUM"]:
            risk_level = "MEDIUM"
        else:
            risk_level = "LOW"

        # === Risk Factor Analysis ===
        risk_factors = []
        positive_evidence = []
        negative_evidence = []
        uncertainties = []

        # Positive risk factors (increase suspicion)
        if anomaly_risk > 0.6:
            risk_factors.append(f"ML anomaly score {anomaly_risk:.2f} indicates statistically unusual behavior.")
        if signals:
            for sig in signals:
                if sig.get("severity") in ("HIGH", "CRITICAL"):
                    risk_factors.append(f"Rule signal: {sig.get('signal_type')} — {sig.get('reason', '')[:100]}")
        for tm in typology_matches:
            risk_factors.append(f"AML typology match: {tm['typology']} (confidence: {tm['confidence']:.0%})")
        if cycle_count > 0:
            risk_factors.append(f"Circular transaction paths detected ({cycle_count} cycle(s)).")
        if entity_rel_count > 3:
            risk_factors.append(f"Account linked to {entity_rel_count} entity relationships.")

        # Positive evidence (reduce suspicion)
        transaction = state["transaction"]
        amount = float(transaction.get("amount", 0))
        channel = transaction.get("channel", "UNKNOWN")
        if channel in ("NEFT", "RTGS"):
            positive_evidence.append("Transaction used regulated formal banking channel (NEFT/RTGS).")
        if amount < 10_000:
            positive_evidence.append(f"Transaction amount ₹{amount:,.0f} is below standard alert thresholds.")
        if not typology_matches:
            positive_evidence.append("No AML typology patterns matched in available transaction data.")
        if anomaly_risk < 0.3:
            positive_evidence.append("ML model indicates behavior is within normal range for this account.")

        # Uncertainties
        if len(all_transactions) < 20:
            uncertainties.append("Limited transaction history available — assessment based on incomplete data.")
        if not state["entity_relationships"]:
            uncertainties.append("No entity relationships resolved — network risk may be underestimated.")

        duration_ms = int((time.monotonic() - start_time) * 1000)
        audit_event = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "actor": "risk_agent",
            "action": "RISK_ASSESSMENT_COMPLETE",
            "summary": (
                f"Risk assessment complete. Level: {risk_level}. "
                f"Composite score: {composite_score:.3f}. "
                f"Typologies matched: {len(typology_matches)}."
            ),
            "metadata": {
                "risk_level": risk_level,
                "composite_score": composite_score,
                "anomaly_risk": anomaly_risk,
                "signal_risk": signal_risk,
                "typology_risk": typology_risk,
                "network_risk": network_risk,
                "typology_count": len(typology_matches),
                "duration_ms": duration_ms,
            },
        }

        logger.info(
            "risk_agent.complete",
            investigation_id=investigation_id,
            risk_level=risk_level,
            composite_score=composite_score,
            duration_ms=duration_ms,
        )

        return {
            **state,
            "typology_matches": typology_matches,
            "risk_level": risk_level,
            "composite_risk_score": composite_score,
            "risk_factors": risk_factors,
            "positive_evidence": positive_evidence,
            "negative_evidence": negative_evidence,
            "uncertainties": uncertainties,
            "audit_events": state["audit_events"] + [audit_event],
        }

    except Exception as e:
        logger.error("risk_agent.error", investigation_id=investigation_id, error=str(e))
        error_event = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "actor": "risk_agent",
            "action": "RISK_ERROR",
            "summary": f"Risk agent encountered an error: {str(e)}",
            "metadata": {"error": str(e)},
        }
        return {
            **state,
            "errors": state["errors"] + [{"agent": "risk", "error": str(e)}],
            "audit_events": state["audit_events"] + [error_event],
        }
