"""
Context/Data Loader Service.

Loads full case context for a given alert into CaseContext format.
This is the bridge between Alert Prioritization and the LangGraph workflow.
Called before initializing the LangGraph case state.

Returns a CaseContext containing all data the workflow needs.
"""
from __future__ import annotations

from typing import Any

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.state import AlertContext, CaseContext
from app.models import Account, Alert, Customer, Entity, EntityRelationship, Transaction, EvidenceLog, ThreatIntel

logger = structlog.get_logger("finspectra.services.context_loader")


async def load_case_context(
    alert_id: str,
    db: AsyncSession,
    max_transactions: int = 200,
) -> CaseContext:
    """
    Load the full case context for an alert.
    Correlates financial transactions, WAF evidence logs, and Threat Intelligence records.
    """
    logger.info("Loading case context", alert_id=alert_id)

    # Load alert
    result = await db.execute(select(Alert).where(Alert.id == alert_id))
    alert_model = result.scalar_one_or_none()
    if not alert_model:
        raise ValueError(f"Alert not found: {alert_id}")

    # Load the primary transaction
    result = await db.execute(select(Transaction).where(Transaction.id == alert_model.transaction_id))
    primary_txn = result.scalar_one_or_none()

    # Collect related account numbers & IPs
    related_accounts: set[str] = set()
    related_ips: set[str] = set()
    if primary_txn:
        if primary_txn.from_account_number:
            related_accounts.add(primary_txn.from_account_number)
        if primary_txn.to_account_number:
            related_accounts.add(primary_txn.to_account_number)
        if primary_txn.ip_address:
            related_ips.add(primary_txn.ip_address)

    # Load all transactions involving related accounts or IPs
    txn_results = await db.execute(
        select(Transaction)
        .where(
            (Transaction.from_account_number.in_(related_accounts)) |
            (Transaction.to_account_number.in_(related_accounts)) |
            (Transaction.ip_address.in_(related_ips))
        )
        .limit(max_transactions)
        .order_by(Transaction.timestamp)
    )
    related_transactions = list(txn_results.scalars())

    # Expand related accounts & IPs
    for t in related_transactions:
        if t.from_account_number:
            related_accounts.add(t.from_account_number)
        if t.to_account_number:
            related_accounts.add(t.to_account_number)
        if t.ip_address:
            related_ips.add(t.ip_address)

    # Load account records
    acc_results = await db.execute(
        select(Account).where(Account.account_number.in_(related_accounts))
    )
    accounts = list(acc_results.scalars())

    # Load customers
    customer_ids = {a.customer_id for a in accounts if a.customer_id and a.customer_id != "__unknown__"}
    customers = []
    if customer_ids:
        cust_results = await db.execute(
            select(Customer).where(Customer.id.in_(customer_ids))
        )
        customers = list(cust_results.scalars())

    # Load Threat Intelligence records for related IPs
    threat_intel_items = []
    if related_ips:
        threat_res = await db.execute(select(ThreatIntel).where(ThreatIntel.ip_address.in_(related_ips)))
        threat_intel_items = list(threat_res.scalars())

    # Load Evidence WAF logs for related IPs
    waf_evidence_items = []
    if related_ips:
        waf_res = await db.execute(select(EvidenceLog).where(EvidenceLog.src_ip.in_(related_ips)))
        waf_evidence_items = list(waf_res.scalars())

    # Load entity relationships
    entity_results = await db.execute(
        select(Entity).where(Entity.cluster_id.isnot(None))
    )
    entities = list(entity_results.scalars())

    # Build entity clusters
    clusters: dict[str, list[str]] = {}
    for ent in entities:
        if ent.cluster_id:
            clusters.setdefault(ent.cluster_id, []).append(
                f"{ent.entity_type}:{ent.normalized_value}"
            )

    entity_cluster_list = [
        {"cluster_id": cid, "members": members, "reason": "Shared identifier / threat cluster"}
        for cid, members in clusters.items()
    ]

    reasons = list(alert_model.reasons or [])
    for ti in threat_intel_items:
        reasons.append(f"Threat Intel Match: IP {ti.ip_address} has Abuse Score {ti.abuse_confidence_score}% ({ti.risk_level} Risk, Country: {ti.country_name or ti.country_code})")
    for r in waf_evidence_items[:3]:
        reasons.append(f"WAF Log Evidence: {r.rule_names} ({r.protocol}) from {r.src_ip} ({r.bytes_in} in / {r.bytes_out} out bytes)")

    # Build AlertContext
    alert_ctx = AlertContext(
        alert_id=alert_id,
        transaction_id=alert_model.transaction_id,
        customer_id=alert_model.customer_id,
        from_account=primary_txn.from_account_number if primary_txn else None,
        to_account=primary_txn.to_account_number if primary_txn else None,
        amount=primary_txn.amount if primary_txn else 0.0,
        anomaly_score=alert_model.anomaly_score,
        rule_signals=alert_model.rule_signals or [],
        initial_priority=alert_model.initial_priority,
        reasons=reasons,
    )

    # Serialize SQLAlchemy models to dicts
    def _txn_to_dict(t: Transaction) -> dict[str, Any]:
        return {
            "id": t.id,
            "txn_ref": t.txn_ref,
            "from_account_number": t.from_account_number,
            "to_account_number": t.to_account_number,
            "amount": t.amount,
            "currency": t.currency,
            "channel": t.channel,
            "transaction_type": t.transaction_type,
            "timestamp": t.timestamp.isoformat() if t.timestamp else None,
            "description": t.description,
            "device_id": t.device_id,
            "ip_address": t.ip_address,
            "location": t.location,
            "scenario_label": t.scenario_label,
        }

    def _acc_to_dict(a: Account) -> dict[str, Any]:
        return {
            "id": a.id,
            "account_number": a.account_number,
            "customer_id": a.customer_id,
            "account_type": a.account_type,
            "bank_name": a.bank_name,
            "upi_id": a.upi_id,
            "device_id": a.device_id,
        }

    def _cust_to_dict(c: Customer) -> dict[str, Any]:
        return {
            "id": c.id,
            "customer_ref": c.customer_ref,
            "full_name": c.full_name,
            "phone": c.phone,
            "email": c.email,
            "kyc_status": c.kyc_status,
            "risk_profile": c.risk_profile,
            "occupation": c.occupation,
            "city": c.city,
        }

    case_context = CaseContext(
        case_id="",  # Will be set by caller (= investigation_id)
        alert=alert_ctx,
        transactions=[_txn_to_dict(t) for t in related_transactions],
        accounts=[_acc_to_dict(a) for a in accounts],
        customers=[_cust_to_dict(c) for c in customers],
        entity_clusters=entity_cluster_list,
        graph_nodes=len(related_accounts) + len(related_ips),
        graph_edges=len(related_transactions) + len(waf_evidence_items),
    )

    logger.info(
        "Case context loaded",
        alert_id=alert_id,
        transactions=len(related_transactions),
        accounts=len(accounts),
        customers=len(customers),
        threat_intel=len(threat_intel_items),
        waf_logs=len(waf_evidence_items),
    )
    return case_context

