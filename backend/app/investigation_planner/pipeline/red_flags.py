"""
Red Flag / Issue Identification Stage.

Identifies unusual, suspicious, or risk-relevant indicators from extracted facts.
Each red flag references fact IDs.  Baselines are stated as UNKNOWN when unavailable.
No criminal conclusions are drawn here.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from ..config.taxonomy import (
    HIGH_RISK_JURISDICTIONS,
    HIGH_VALUE_THRESHOLD_INR,
    HIGH_VALUE_THRESHOLD_USD,
    STRUCTURING_THRESHOLD_INR,
    Severity,
)
from ..schemas.case import NormalizedCase
from ..schemas.fact import Fact
from ..schemas.red_flag import RedFlag

_SENTINEL_VALUES = {"UNKNOWN", "NOT_PROVIDED", "NOT_AVAILABLE", "NOT_APPLICABLE"}


def _is_available(value: Any) -> bool:
    return value is not None and str(value) not in _SENTINEL_VALUES


def _find_fact(facts: List[Fact], source_contains: str) -> Optional[Fact]:
    return next((f for f in facts if source_contains in f.source), None)


def _find_facts(facts: List[Fact], source_contains: str) -> List[Fact]:
    return [f for f in facts if source_contains in f.source]


def _detect_signals(case: NormalizedCase, facts: List[Fact]) -> Dict[str, Any]:
    """
    Derive a set of boolean/value signals from the case and facts.
    These signals feed both red-flag detection AND classification.
    """
    signals: Dict[str, Any] = {}

    # ── Amount signals ────────────────────────────────────────────────────────
    amount_fact = _find_fact(facts, "transaction.amount")
    currency_fact = _find_fact(facts, "transaction.currency")

    if amount_fact and isinstance(amount_fact.value, (int, float)):
        amt = float(amount_fact.value)
        cur = str(currency_fact.value).upper() if currency_fact and _is_available(currency_fact.value) else "INR"

        if cur in ("INR", "₹") and amt >= HIGH_VALUE_THRESHOLD_INR:
            signals["high_value"] = {"amount": amt, "currency": cur, "fact_id": amount_fact.fact_id}
        elif cur in ("USD", "$") and amt >= HIGH_VALUE_THRESHOLD_USD:
            signals["high_value"] = {"amount": amt, "currency": cur, "fact_id": amount_fact.fact_id}
        elif cur not in ("INR", "₹", "USD", "$") and amt >= HIGH_VALUE_THRESHOLD_INR:
            # For unknown currencies apply INR threshold
            signals["high_value"] = {"amount": amt, "currency": cur, "fact_id": amount_fact.fact_id}

        # Structuring signal — just below threshold
        if cur in ("INR", "₹") and STRUCTURING_THRESHOLD_INR * 0.80 <= amt < STRUCTURING_THRESHOLD_INR:
            signals["below_threshold_amount"] = {"amount": amt, "fact_id": amount_fact.fact_id}

    # ── Geographic signals ────────────────────────────────────────────────────
    dest = case.geographic_information.get("destination", "")
    origin = case.geographic_information.get("origin", "")

    if _is_available(dest) and _is_available(origin) and dest != origin:
        signals["international_transfer"] = {"destination": dest, "origin": origin}

    if _is_available(dest) and any(
        risk.lower() in str(dest).lower() for risk in HIGH_RISK_JURISDICTIONS
    ):
        signals["high_risk_jurisdiction"] = {"destination": dest}

    # ── Beneficiary signals ───────────────────────────────────────────────────
    for entity in case.entities:
        if entity.get("role") == "BENEFICIARY":
            status = entity.get("status", "")
            if isinstance(status, str) and status.upper() in ("NEW", "UNKNOWN", "UNVERIFIED"):
                signals["new_beneficiary"] = {"status": status}

    # ── Alert-type-derived signals ─────────────────────────────────────────────
    alert_type   = str(case.alert_trigger.get("type", "")).lower()
    alert_reason = str(case.alert_trigger.get("reason", "")).lower()
    combined     = alert_type + " " + alert_reason

    if "structuring" in combined or "below threshold" in combined or "multiple deposit" in combined:
        signals["multiple_transactions"] = True
        signals.setdefault("below_threshold_amount", {"amount": None, "fact_id": None})

    if "mule" in combined or "pass-through" in combined or "pass through" in combined:
        signals["pass_through_pattern"] = True
        signals["new_account"] = True

    if "account takeover" in combined or "device" in combined:
        signals["device_change"] = True
        signals["rapid_transfer_after_device_change"] = True

    if "kyc" in combined or "identity" in combined or "synthetic" in combined:
        signals["kyc_anomaly"] = True

    if "international" in combined or "cross-border" in combined:
        signals.setdefault("international_transfer", {"destination": dest, "origin": origin})

    if "structuring" in combined:
        signals["multiple_transactions"] = True

    return signals


def identify_red_flags(case: NormalizedCase, facts: List[Fact]) -> List[RedFlag]:
    """Stage 3 – Identify red flags grounded in facts."""
    signals = _detect_signals(case, facts)
    red_flags: List[RedFlag] = []
    counter = 1

    def add_rf(
        description: str,
        severity: str,
        evidence_refs: List[str],
        observed_value: Any,
        baseline: Optional[str],
        confidence: float,
        rationale: str,
    ) -> None:
        nonlocal counter
        red_flags.append(RedFlag(
            red_flag_id=f"RF{counter:03d}",
            description=description,
            severity=severity,
            evidence_refs=evidence_refs,
            observed_value=observed_value,
            comparison_baseline=baseline if baseline else "UNKNOWN — historical data not available",
            confidence=confidence,
            rationale=rationale,
        ))
        counter += 1

    # ── High-value transaction ────────────────────────────────────────────────
    if "high_value" in signals:
        hv = signals["high_value"]
        amt = hv["amount"]
        cur = hv["currency"]
        add_rf(
            description="Unusually high transaction amount",
            severity=Severity.HIGH,
            evidence_refs=[hv["fact_id"]],
            observed_value=f"{cur} {amt:,.2f}",
            baseline="UNKNOWN — customer historical transaction amounts unavailable",
            confidence=0.87,
            rationale=(
                f"Transaction amount {cur} {amt:,.2f} significantly exceeds standard thresholds. "
                "Without historical baseline confirmation, this warrants investigation."
            ),
        )

    # ── New / unverified beneficiary ──────────────────────────────────────────
    if "new_beneficiary" in signals:
        bene_facts = [f for f in facts if "beneficiary" in f.source]
        add_rf(
            description="New or unverified beneficiary",
            severity=Severity.HIGH,
            evidence_refs=[f.fact_id for f in bene_facts] or ["N/A"],
            observed_value=signals["new_beneficiary"].get("status"),
            baseline="Established, verified beneficiary relationship",
            confidence=0.80,
            rationale=(
                "The beneficiary does not appear in established records. "
                "Transfers to new or unknown beneficiaries carry elevated risk."
            ),
        )

    # ── High-risk / sanctioned jurisdiction ──────────────────────────────────
    if "high_risk_jurisdiction" in signals:
        dest = signals["high_risk_jurisdiction"]["destination"]
        dest_facts = [f for f in facts if "destination" in f.source]
        add_rf(
            description=f"Transaction destination is a high-risk or sanctioned jurisdiction: {dest}",
            severity=Severity.HIGH,
            evidence_refs=[f.fact_id for f in dest_facts] or ["N/A"],
            observed_value=dest,
            baseline="Low-risk, FATF-compliant jurisdiction",
            confidence=0.85,
            rationale=(
                f"Destination '{dest}' is on the high-risk jurisdiction reference list. "
                "Transactions to such jurisdictions require enhanced due diligence."
            ),
        )

    # ── International / cross-border transfer ────────────────────────────────
    elif "international_transfer" in signals:
        xb = signals["international_transfer"]
        xb_facts = [f for f in facts if "destination" in f.source or "cross-border" in f.source]
        add_rf(
            description=f"International transfer to {xb.get('destination', 'UNKNOWN')}",
            severity=Severity.MEDIUM,
            evidence_refs=[f.fact_id for f in xb_facts] or ["N/A"],
            observed_value=f"From {xb.get('origin','UNKNOWN')} to {xb.get('destination','UNKNOWN')}",
            baseline="UNKNOWN — international transfer history unavailable",
            confidence=0.70,
            rationale=(
                "Cross-border transfers carry inherent financial crime risk and require verification "
                "of the purpose and beneficiary relationship."
            ),
        )

    # ── Below-threshold structuring pattern ──────────────────────────────────
    if "below_threshold_amount" in signals:
        bt = signals["below_threshold_amount"]
        bt_facts = [f for f in facts if "amount" in f.source]
        add_rf(
            description="Transaction amount just below regulatory reporting threshold — potential structuring",
            severity=Severity.HIGH,
            evidence_refs=[f.fact_id for f in bt_facts] or ["N/A"],
            observed_value=bt.get("amount"),
            baseline=f"Reporting threshold: INR {STRUCTURING_THRESHOLD_INR:,}",
            confidence=0.82,
            rationale=(
                "Amount is positioned just below the standard cash transaction reporting threshold. "
                "This pattern is consistent with structuring behavior designed to avoid reporting."
            ),
        )

    if "multiple_transactions" in signals:
        add_rf(
            description="Multiple transactions in pattern potentially indicative of structuring",
            severity=Severity.MEDIUM,
            evidence_refs=[f.fact_id for f in facts if "amount" in f.source or "type" in f.source][:2] or ["N/A"],
            observed_value="Multiple transaction pattern",
            baseline="UNKNOWN — transaction frequency baseline unavailable",
            confidence=0.75,
            rationale=(
                "Alert reason suggests a pattern of multiple transactions. "
                "Without full transaction history, the structuring risk cannot be fully assessed."
            ),
        )

    # ── Pass-through / mule signal ────────────────────────────────────────────
    if "pass_through_pattern" in signals:
        add_rf(
            description="Rapid pass-through transfer pattern — potential mule account activity",
            severity=Severity.HIGH,
            evidence_refs=[f.fact_id for f in facts if "type" in f.source or "amount" in f.source][:2] or ["N/A"],
            observed_value="Rapid in-out transfer",
            baseline="Normal account holding period",
            confidence=0.80,
            rationale=(
                "Funds appear to transit through the account without normal retention, "
                "consistent with mule account pass-through behaviour."
            ),
        )

    # ── Account takeover signals ──────────────────────────────────────────────
    if "device_change" in signals:
        add_rf(
            description="Rapid device change followed by fund transfer — potential account takeover indicator",
            severity=Severity.HIGH,
            evidence_refs=[f.fact_id for f in facts if "reason" in f.source or "type" in f.source][:2] or ["N/A"],
            observed_value="Device change + immediate transfer",
            baseline="Normal device usage pattern",
            confidence=0.85,
            rationale=(
                "A device change immediately preceding a fund transfer is a recognised "
                "account takeover indicator that requires verification of account holder identity."
            ),
        )

    # ── KYC / Identity anomaly ────────────────────────────────────────────────
    if "kyc_anomaly" in signals:
        kyc_facts = [f for f in facts if "reason" in f.source or "type" in f.source]
        add_rf(
            description="KYC or identity anomaly detected — potential synthetic or fraudulent identity",
            severity=Severity.HIGH,
            evidence_refs=[f.fact_id for f in kyc_facts][:2] or ["N/A"],
            observed_value="Identity/KYC flag",
            baseline="Verified customer identity",
            confidence=0.82,
            rationale=(
                "The alert signals a KYC or identity-related anomaly. "
                "This may indicate synthetic identity, document fraud, or identity mismatch."
            ),
        )

    # ── Fallback — generic system-triggered alert ─────────────────────────────
    if not red_flags:
        primary_fact = facts[0] if facts else None
        add_rf(
            description="System-triggered alert — anomalous pattern requiring human review",
            severity=Severity.MEDIUM,
            evidence_refs=[primary_fact.fact_id] if primary_fact else ["N/A"],
            observed_value="System alert signal",
            baseline="UNKNOWN — insufficient data for baseline comparison",
            confidence=0.50,
            rationale=(
                "The system triggered an alert. Without sufficient alert details, "
                "a manual review is required to determine the nature of the anomaly."
            ),
        )

    return red_flags


def get_signals(case: NormalizedCase, facts: List[Fact]) -> Dict[str, Any]:
    """Expose signal detection for use by the classification stage."""
    return _detect_signals(case, facts)
