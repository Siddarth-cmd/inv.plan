"""
Case Normalization Stage.

Converts a RawAlertInput into a NormalizedCase — the planner's working state.
Missing information is represented explicitly using UNKNOWN / NOT_PROVIDED /
NOT_AVAILABLE / NOT_APPLICABLE. Nothing is invented.
"""
from __future__ import annotations

import uuid
from typing import Any, Dict, List, Optional

from ..schemas.alert import RawAlertInput
from ..schemas.case import MissingInformation, NormalizedCase

# ─── Sentinel values ──────────────────────────────────────────────────────────
UNKNOWN = "UNKNOWN"
NOT_PROVIDED = "NOT_PROVIDED"
NOT_AVAILABLE = "NOT_AVAILABLE"
NOT_APPLICABLE = "NOT_APPLICABLE"


def _sentinel(value: Optional[Any], default: str = UNKNOWN) -> Any:
    """Return value if truthy, else the sentinel string."""
    return value if value is not None else default


def normalize_case(alert: RawAlertInput) -> NormalizedCase:
    """Stage 1 – Convert raw alert into a structured NormalizedCase."""
    case_id = f"CASE-{uuid.uuid4().hex[:8].upper()}"
    missing: List[MissingInformation] = []

    # ── Entities ─────────────────────────────────────────────────────────────
    entities: List[Dict[str, Any]] = []
    if alert.sender_information:
        sender = dict(alert.sender_information)
        sender.setdefault("role", "SENDER")
        entities.append(sender)
    else:
        missing.append(MissingInformation(item="sender_information", reason="NOT_PROVIDED"))

    if alert.receiver_information:
        receiver = dict(alert.receiver_information)
        receiver.setdefault("role", "RECEIVER")
        entities.append(receiver)
    else:
        missing.append(MissingInformation(item="receiver_information", reason="NOT_PROVIDED"))

    if alert.beneficiary_information:
        bene = dict(alert.beneficiary_information)
        bene.setdefault("role", "BENEFICIARY")
        entities.append(bene)
    else:
        missing.append(MissingInformation(item="beneficiary_information", reason="NOT_PROVIDED"))

    # ── Transactions ─────────────────────────────────────────────────────────
    transactions: List[Dict[str, Any]] = [{
        "transaction_id": _sentinel(alert.transaction_id, NOT_PROVIDED),
        "amount":          _sentinel(alert.transaction_amount, NOT_PROVIDED),
        "currency":        _sentinel(alert.currency, NOT_PROVIDED),
        "type":            _sentinel(alert.transaction_type, NOT_PROVIDED),
        "timestamp":       _sentinel(alert.timestamp, NOT_PROVIDED),
    }]

    if alert.transaction_amount is None:
        missing.append(MissingInformation(item="transaction_amount", reason="NOT_PROVIDED"))
    if alert.currency is None:
        missing.append(MissingInformation(item="currency", reason="NOT_PROVIDED"))
    if alert.transaction_type is None:
        missing.append(MissingInformation(item="transaction_type", reason="NOT_PROVIDED"))
    if alert.timestamp is None:
        missing.append(MissingInformation(item="timestamp", reason="NOT_PROVIDED"))

    # ── Customer Context ──────────────────────────────────────────────────────
    customer_ctx: Dict[str, Any] = {}
    if alert.customer_information:
        customer_ctx = dict(alert.customer_information)
    else:
        missing.append(MissingInformation(item="customer_information", reason="NOT_PROVIDED"))

    if not alert.customer_id:
        missing.append(MissingInformation(item="customer_id", reason="NOT_PROVIDED"))

    # ── Historical Context ────────────────────────────────────────────────────
    if not alert.historical_information:
        missing.append(MissingInformation(item="historical_information", reason="NOT_AVAILABLE"))

    # ── Geographic Information ────────────────────────────────────────────────
    geo: Dict[str, Any] = {
        "origin":      _sentinel(alert.origin_country, UNKNOWN),
        "destination": _sentinel(alert.destination_country, UNKNOWN),
    }

    # ── Alert Trigger ─────────────────────────────────────────────────────────
    alert_trigger: Dict[str, Any] = {
        "type":   _sentinel(alert.alert_type, UNKNOWN),
        "reason": _sentinel(alert.alert_reason, UNKNOWN),
    }

    # ── Available Evidence ────────────────────────────────────────────────────
    available_evidence: List[Dict[str, Any]] = []
    if alert.additional_metadata:
        available_evidence.append({"source": "additional_metadata", "data": alert.additional_metadata})

    return NormalizedCase(
        case_id=case_id,
        alert_id=alert.alert_id,
        entities=entities,
        transactions=transactions,
        customer_context=customer_ctx,
        temporal_information={"timestamp": _sentinel(alert.timestamp, UNKNOWN)},
        geographic_information=geo,
        alert_trigger=alert_trigger,
        available_evidence=available_evidence,
        missing_information=missing,
    )
