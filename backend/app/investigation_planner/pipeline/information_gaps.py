"""
Information Gap Identification Stage.

Determines what information is MISSING from the alert.
Missing information is never treated as negative evidence.
"""
from __future__ import annotations

from typing import List

from ..schemas.case import MissingInformation, NormalizedCase
from ..schemas.information_gap import InformationGap
from ..schemas.red_flag import RedFlag

_GAP_ALWAYS_PRESENT = [
    ("transaction_purpose", "Transaction purpose and customer intent are not part of the alert payload."),
    ("source_of_funds", "Source of funds for this transaction is unknown."),
]


def identify_information_gaps(case: NormalizedCase, red_flags: List[RedFlag] = None) -> List[InformationGap]:
    """Stage 6 – Identify missing information gaps from the normalized case."""
    gaps: List[InformationGap] = []
    counter = 1
    seen = set()

    def add_gap(description: str) -> None:
        nonlocal counter
        if description not in seen:
            gaps.append(InformationGap(gap_id=f"GAP{counter:03d}", description=description))
            seen.add(description)
            counter += 1

    # ── Gaps derived from missing_information on the case ─────────────────────
    gap_templates = {
        "customer_information":    "Customer profile information is not available.",
        "customer_id":             "Customer ID is not provided; customer cannot be uniquely identified.",
        "sender_information":      "Sender details are not provided.",
        "receiver_information":    "Receiver details are not provided.",
        "beneficiary_information": "Beneficiary identity and relationship to customer are unknown.",
        "transaction_amount":      "Transaction amount is not provided.",
        "currency":                "Transaction currency is not specified.",
        "transaction_type":        "Transaction type is not specified.",
        "timestamp":               "Transaction timestamp is not provided.",
        "historical_information":  (
            "Customer historical transaction data is not available. "
            "It is not possible to assess whether this transaction is consistent with the customer's "
            "historical behaviour without this data."
        ),
    }

    for missing in case.missing_information:
        desc = gap_templates.get(missing.item, f"Information missing: {missing.item} — {missing.reason}.")
        add_gap(desc)

    # ── Always-present gaps about intent & source-of-funds ────────────────────
    for _item, desc in _GAP_ALWAYS_PRESENT:
        add_gap(desc)

    # ── Gaps derived from red flags ────────────────────────────────────────────
    if red_flags:
        for rf in red_flags:
            desc_lower = rf.description.lower()
            if "beneficiary" in desc_lower:
                add_gap("Beneficiary relationship to customer is not established.")
            if "jurisdiction" in desc_lower or "high-risk" in desc_lower:
                add_gap("Business purpose for the cross-border destination is unknown.")
            if "device" in desc_lower or "account takeover" in desc_lower:
                add_gap("Device session and IP information at time of transaction is unavailable.")
            if "kyc" in desc_lower or "identity" in desc_lower:
                add_gap("Identity verification documents and KYC records are not available in the alert.")
            if "structuring" in desc_lower or "threshold" in desc_lower:
                add_gap("Full transaction history required to assess structuring pattern.")

    return gaps
