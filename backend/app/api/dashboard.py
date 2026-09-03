"""Dashboard API for metrics, summary stats, and high-level case overviews."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import func, select

from app.api.deps import DB, CurrentUser
from app.models import Alert, Decision, Evidence, Investigation, Transaction, EvidenceLog, ThreatIntel

router = APIRouter()


@router.get("/summary", response_model=dict)
async def get_dashboard_summary(_user: CurrentUser, db: DB):
    """Get top-level dashboard metrics for the platform."""
    # Transactions count & volume
    txn_count_res = await db.execute(select(func.count()).select_from(Transaction))
    total_txns = txn_count_res.scalar_one()

    vol_res = await db.execute(select(func.sum(Transaction.amount)).select_from(Transaction))
    total_volume = vol_res.scalar_one() or 0.0

    # Evidence logs & Threat intel
    evidence_res = await db.execute(select(func.count()).select_from(EvidenceLog))
    evidence_count = evidence_res.scalar_one()

    threat_res = await db.execute(select(func.count()).select_from(ThreatIntel))
    threat_count = threat_res.scalar_one()

    # Alerts breakdown by priority & status
    alerts_total_res = await db.execute(select(func.count()).select_from(Alert))
    total_alerts = alerts_total_res.scalar_one()

    open_alerts_res = await db.execute(
        select(func.count()).select_from(Alert).where(Alert.status == "OPEN")
    )
    open_alerts = open_alerts_res.scalar_one()

    high_critical_alerts_res = await db.execute(
        select(func.count()).select_from(Alert).where(Alert.initial_priority.in_(["HIGH", "CRITICAL"]))
    )
    high_critical_alerts = high_critical_alerts_res.scalar_one()

    # Investigations
    inv_total_res = await db.execute(select(func.count()).select_from(Investigation))
    total_investigations = inv_total_res.scalar_one()

    inv_completed_res = await db.execute(
        select(func.count()).select_from(Investigation).where(Investigation.status == "COMPLETED")
    )
    completed_investigations = inv_completed_res.scalar_one()

    # Decisions breakdown
    decisions_res = await db.execute(
        select(Decision.decision, func.count(Decision.id))
        .group_by(Decision.decision)
    )
    decision_counts = {row[0]: row[1] for row in decisions_res}

    return {
        "metrics": {
            "total_transactions": total_txns,
            "total_volume_inr": total_volume,
            "evidence_logs_count": evidence_count,
            "threat_intel_count": threat_count,
            "total_alerts": total_alerts,
            "open_alerts": open_alerts,
            "high_critical_alerts": high_critical_alerts,
            "total_investigations": total_investigations,
            "completed_investigations": completed_investigations,
        },
        "decisions_breakdown": decision_counts,
        "aml_scenarios_supported": [
            "Normal Baseline",
            "WAF Suspicious Web Traffic",
            "IP Abuse Threat Intelligence Match",
            "Large Transfer / High Volume",
            "Structuring / Smurfing",
            "Rapid Layering / Pass-through",
            "Shared Device / Mule Network",
        ],
    }


@router.post("/seed-demo", response_model=dict)
async def seed_demo(_user: CurrentUser, db: DB):
    """
    Seed real Evidence dataset, Threat dataset, and synthetic transactions, then run detection.
    """
    import os
    from app.services.ingestion import ingest_csv
    from app.services.detection import run_detection

    base_datasets_dir = os.path.abspath(os.path.join(
        os.path.dirname(__file__), "..", "..", "..", "datasets", "raw"
    ))

    ingest_summaries = {}

    # 1. Ingest Threat dataset
    threat_path = os.path.join(base_datasets_dir, "threat_dataset.csv")
    if os.path.exists(threat_path):
        with open(threat_path, "rb") as f:
            t_res = await ingest_csv(f.read(), db, filename="threat_dataset.csv")
            ingest_summaries["threat_dataset"] = t_res.model_dump()

    # 2. Ingest Evidence dataset (WAF Logs)
    evidence_path = os.path.join(base_datasets_dir, "evidence_dataset.csv")
    if os.path.exists(evidence_path):
        with open(evidence_path, "rb") as f:
            e_res = await ingest_csv(f.read(), db, filename="evidence_dataset.csv")
            ingest_summaries["evidence_dataset"] = e_res.model_dump()

    # 3. Ingest synthetic transactions
    txn_path = os.path.join(base_datasets_dir, "synthetic_transactions.csv")
    if os.path.exists(txn_path):
        with open(txn_path, "rb") as f:
            txn_res = await ingest_csv(f.read(), db, filename="synthetic_transactions.csv")
            ingest_summaries["synthetic_transactions"] = txn_res.model_dump()

    # 4. Run Detection Pipeline
    detection_res = await run_detection(db)
    await db.commit()

    return {
        "status": "SUCCESS",
        "message": "Real Evidence and Threat datasets seeded, and threat detection executed.",
        "ingestion": ingest_summaries,
        "detection": detection_res,
    }

