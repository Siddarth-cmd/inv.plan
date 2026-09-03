"""
Detection Agent — Agent 1.

Identifies suspicious activity from:
- ML anomaly model outputs
- Deterministic rule signals
- Contextual transaction features

Does NOT hallucinate evidence. All outputs are traceable.
"""
from __future__ import annotations

import time
from datetime import datetime, timezone

from app.agents.state import InvestigationState
from app.core.logging import get_logger
from app.ml.anomaly import get_detector
from app.ml.signals import run_all_signals

import pandas as pd

logger = get_logger("detection_agent")


def detection_agent(state: InvestigationState) -> InvestigationState:
    """
    Detection Agent node for LangGraph.

    Reads: transaction, all_transactions
    Writes: anomaly_score, model_score, triggered_signals,
            suspicious_transaction_ids, alert_priority
    """
    start_time = time.monotonic()
    investigation_id = state["investigation_id"]

    logger.info("detection_agent.start", investigation_id=investigation_id)

    try:
        transaction = state["transaction"]
        all_transactions = state["all_transactions"]

        # Build DataFrame for analysis
        txn_df = pd.DataFrame(all_transactions)
        if txn_df.empty:
            raise ValueError("No transactions provided for detection.")

        # Ensure required columns exist
        required_cols = ["id", "from_account_number", "to_account_number", "amount", "timestamp", "channel", "transaction_type"]
        for col in required_cols:
            if col not in txn_df.columns:
                txn_df[col] = None

        txn_df["amount"] = pd.to_numeric(txn_df["amount"], errors="coerce").fillna(0)
        txn_df["timestamp"] = pd.to_datetime(txn_df["timestamp"], utc=True, errors="coerce")

        # === ML Anomaly Scoring ===
        detector = get_detector()
        anomaly_score = 0.5
        model_score = 0.0

        if detector.is_trained and len(txn_df) >= 10:
            try:
                results = detector.score_transactions(txn_df)
                # Find the score for the triggering transaction
                txn_id = transaction["id"]
                for r in results:
                    if r.transaction_id == txn_id:
                        anomaly_score = r.normalized_score
                        model_score = r.model_score
                        break
            except Exception as e:
                logger.warning("detection_agent.anomaly_scoring_failed", error=str(e))
                state["errors"].append({"agent": "detection", "error": str(e), "step": "anomaly_scoring"})
                anomaly_score = 0.5  # Conservative default
        else:
            # Model not trained — use heuristic based on amount
            amount = float(transaction.get("amount", 0))
            anomaly_score = min(amount / 1_000_000, 1.0)
            logger.info("detection_agent.model_not_trained_using_heuristic")

        # === Rule-Based Signal Detection ===
        all_signals_map = run_all_signals(txn_df)
        txn_id = str(transaction["id"])

        # Get signals for the triggering transaction
        triggered_signals = all_signals_map.get(txn_id, [])
        triggered_signal_dicts = [s.to_dict() for s in triggered_signals]

        # Collect all suspicious transaction IDs from signals
        suspicious_ids = set([txn_id]) if triggered_signals or anomaly_score > 0.6 else set()
        for signals in all_signals_map.values():
            for sig in signals:
                if sig.score >= 0.7:
                    suspicious_ids.update(sig.supporting_transaction_ids)

        # === Alert Priority ===
        max_signal_score = max((s.score for s in triggered_signals), default=0.0)
        combined_score = max(anomaly_score * 0.4 + max_signal_score * 0.6, anomaly_score)

        if combined_score >= 0.85:
            priority = "CRITICAL"
        elif combined_score >= 0.65:
            priority = "HIGH"
        elif combined_score >= 0.40:
            priority = "MEDIUM"
        else:
            priority = "LOW"

        # === Audit event ===
        duration_ms = int((time.monotonic() - start_time) * 1000)
        audit_event = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "actor": "detection_agent",
            "action": "DETECTION_COMPLETE",
            "summary": (
                f"Detection complete. Anomaly score: {anomaly_score:.3f}. "
                f"Signals: {len(triggered_signals)}. Priority: {priority}."
            ),
            "metadata": {
                "anomaly_score": anomaly_score,
                "signal_count": len(triggered_signals),
                "priority": priority,
                "duration_ms": duration_ms,
            },
        }

        logger.info(
            "detection_agent.complete",
            investigation_id=investigation_id,
            anomaly_score=anomaly_score,
            signal_count=len(triggered_signals),
            priority=priority,
            duration_ms=duration_ms,
        )

        return {
            **state,
            "anomaly_score": anomaly_score,
            "model_score": model_score,
            "triggered_signals": triggered_signal_dicts,
            "suspicious_transaction_ids": list(suspicious_ids),
            "alert_priority": priority,
            "audit_events": state["audit_events"] + [audit_event],
        }

    except Exception as e:
        logger.error("detection_agent.error", investigation_id=investigation_id, error=str(e))
        error_event = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "actor": "detection_agent",
            "action": "DETECTION_ERROR",
            "summary": f"Detection agent encountered an error: {str(e)}",
            "metadata": {"error": str(e)},
        }
        return {
            **state,
            "errors": state["errors"] + [{"agent": "detection", "error": str(e)}],
            "audit_events": state["audit_events"] + [error_event],
        }
