"""
Detection Service — Alert Prioritization.

Runs Isolation Forest + Rule Signals on ingested transactions.
Creates Alert records with combined scores.
This is the Alert Triage step before the LangGraph workflow.

Flow:
  transactions → Feature Engineering → Isolation Forest → Rule Signals
    → Alert Triage / Prioritization → Alert records in DB
"""
from __future__ import annotations

import math
from typing import Any

import pandas as pd
import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ml.detector import IsolationForestDetector
from app.ml.signals import compute_signals
from app.models import Alert, Transaction, Account
from app.schemas import IngestionSummary

logger = structlog.get_logger("finspectra.services.detection")

ALERT_SCORE_THRESHOLD = 0.5  # Minimum anomaly score to create an alert
PRIORITY_THRESHOLDS = {
    "CRITICAL": 0.85,
    "HIGH": 0.70,
    "MEDIUM": 0.50,
    "LOW": 0.0,
}


def _determine_priority(anomaly_score: float, rule_signal_count: int) -> str:
    """
    Alert prioritization combining ML score and rule signals.
    Higher rule signals can bump priority.
    """
    base_score = anomaly_score
    if rule_signal_count >= 3:
        base_score = min(base_score + 0.15, 1.0)
    elif rule_signal_count >= 1:
        base_score = min(base_score + 0.08, 1.0)

    for priority, threshold in PRIORITY_THRESHOLDS.items():
        if base_score >= threshold:
            return priority
    return "LOW"


def _build_alert_reasons(
    txn: dict[str, Any],
    anomaly_score: float,
    signals: list[dict[str, Any]],
) -> list[str]:
    """Build human-readable reasons for an alert from actual data."""
    reasons = []
    reasons.append(f"ML anomaly score: {anomaly_score:.4f} (threshold: {ALERT_SCORE_THRESHOLD})")
    if txn.get("amount", 0) >= 500_000:
        reasons.append(f"Large amount: {txn['amount']:,.0f} INR")
    for sig in signals[:4]:
        reasons.append(sig.get("reason", sig.get("signal_type", "?")))
    return reasons


async def run_detection(db: AsyncSession) -> dict[str, Any]:
    """
    Run the complete detection pipeline on all un-alerted transactions.
    
    Steps:
      1. Load transactions from DB
      2. Build features
      3. Train/load Isolation Forest model
      4. Compute anomaly scores (MODEL SCORE)
      5. Compute rule signals (deterministic)
      6. Alert Triage: combine scores → create Alert records
    
    Returns:
        Summary dict with detection statistics.
    """
    # Load transactions without existing alerts
    existing_alert_txn_ids_result = await db.execute(
        select(Alert.transaction_id)
    )
    existing_alert_txn_ids = {row[0] for row in existing_alert_txn_ids_result}

    result = await db.execute(select(Transaction).order_by(Transaction.timestamp))
    all_transactions = list(result.scalars())

    if not all_transactions:
        return {"message": "No transactions to analyze", "alerts_created": 0}

    logger.info("Running detection pipeline", total_transactions=len(all_transactions))

    from app.models import ThreatIntel
    # Fetch Threat Intel map (ip -> ThreatIntel)
    threat_res = await db.execute(select(ThreatIntel))
    threat_map = {t.ip_address: t for t in threat_res.scalars()}

    # Convert to DataFrame for ML pipeline
    rows = []
    for t in all_transactions:
        rows.append({
            "id": t.id,
            "from_account_number": t.from_account_number or "",
            "to_account_number": t.to_account_number or "",
            "amount": t.amount,
            "currency": t.currency,
            "channel": t.channel,
            "transaction_type": t.transaction_type,
            "timestamp": t.timestamp,
            "device_id": t.device_id or "",
            "ip_address": t.ip_address or "",
            "description": t.description or "",
            "scenario_label": t.scenario_label or "",
        })
    df = pd.DataFrame(rows)

    # Train or load Isolation Forest
    detector = IsolationForestDetector()
    if not detector.is_trained():
        logger.info("Training Isolation Forest model")
        meta = detector.train(df)
        logger.info("Model trained", **meta)

    # Score all transactions
    scores_df = detector.score(df)
    score_map = dict(zip(scores_df["id"], scores_df["model_anomaly_score"]))

    # Compute rule signals on full dataset
    all_signals = compute_signals(df)
    signals_by_txn: dict[str, list[dict[str, Any]]] = {}
    for sig in all_signals:
        for txn_id in sig.get("supporting_transaction_ids", []):
            signals_by_txn.setdefault(txn_id, []).append(sig)

    # Alert Triage / Prioritization
    alerts_created = 0
    alerts_skipped_existing = 0
    alerts_below_threshold = 0

    for txn in all_transactions:
        if txn.id in existing_alert_txn_ids:
            alerts_skipped_existing += 1
            continue

        anomaly_score = score_map.get(txn.id, 0.0)
        txn_signals = list(signals_by_txn.get(txn.id, []))

        # Check Threat Intel correlation by IP
        if txn.ip_address and txn.ip_address in threat_map:
            threat = threat_map[txn.ip_address]
            anomaly_score = max(anomaly_score, 0.95)
            threat_sig = {
                "signal_type": "CRITICAL_THREAT_INTEL_MATCH",
                "severity": threat.risk_level.upper() if threat.risk_level else "CRITICAL",
                "score": float(threat.abuse_confidence_score / 100.0),
                "reason": f"IP {txn.ip_address} matched Threat Intelligence database ({threat.risk_level} Risk, Abuse Confidence {threat.abuse_confidence_score}%, Severity {threat.severity}, Reported {threat.reported_date}).",
                "supporting_transaction_ids": [txn.id],
            }
            txn_signals.insert(0, threat_sig)

        # Only alert if score is above threshold or any signals triggered
        if anomaly_score < ALERT_SCORE_THRESHOLD and not txn_signals:
            alerts_below_threshold += 1
            continue

        # Get customer_id for the from_account
        cust_id: str | None = None
        if txn.from_account_id:
            acc_result = await db.execute(
                select(Account).where(Account.id == txn.from_account_id)
            )
            acc = acc_result.scalar_one_or_none()
            if acc:
                cust_id = acc.customer_id

        txn_dict = {
            "id": txn.id,
            "from_account_number": txn.from_account_number,
            "to_account_number": txn.to_account_number,
            "amount": txn.amount,
            "channel": txn.channel,
        }

        priority = _determine_priority(anomaly_score, len(txn_signals))
        if any(s.get("signal_type") == "CRITICAL_THREAT_INTEL_MATCH" for s in txn_signals):
            priority = "CRITICAL"

        reasons = _build_alert_reasons(txn_dict, anomaly_score, txn_signals)

        alert = Alert(
            transaction_id=txn.id,
            customer_id=cust_id,
            anomaly_score=float(anomaly_score),
            rule_signals=txn_signals,
            initial_priority=priority,
            status="OPEN",
            reasons=reasons,
        )
        db.add(alert)
        alerts_created += 1

    await db.flush()

    summary = {
        "total_transactions_analyzed": len(all_transactions),
        "alerts_created": alerts_created,
        "alerts_skipped_existing": alerts_skipped_existing,
        "alerts_below_threshold": alerts_below_threshold,
        "rule_signals_total": len(all_signals),
        "threat_intel_matches": len([t for t in all_transactions if t.ip_address in threat_map]),
        "model_threshold": ALERT_SCORE_THRESHOLD,
    }
    logger.info("Detection complete", **summary)
    return summary

