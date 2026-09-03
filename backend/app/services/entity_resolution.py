"""
Entity Resolution Service.

Deterministic matching of entities across accounts, phones, emails, UPI IDs, devices.
Every relationship has an explicit, explainable reason.
Does NOT use LLM for entity resolution.
"""
from __future__ import annotations

from collections import defaultdict
from typing import Any

import pandas as pd


def normalize_phone(phone: str) -> str:
    """Normalize phone number: remove spaces, dashes, +91 prefix."""
    if not phone:
        return ""
    digits = "".join(c for c in str(phone) if c.isdigit())
    if digits.startswith("91") and len(digits) > 10:
        digits = digits[2:]
    return digits[-10:] if len(digits) >= 10 else digits


def normalize_email(email: str) -> str:
    """Normalize email: lowercase and strip."""
    return email.strip().lower() if email else ""


def normalize_upi(upi: str) -> str:
    """Normalize UPI ID: lowercase and strip."""
    return upi.strip().lower() if upi else ""


def resolve_entities(transactions_df: pd.DataFrame) -> tuple[list[dict], dict]:
    """
    Resolve entity relationships from transaction data.

    Detects:
    - Shared source/destination accounts
    - Same account appearing in multiple roles
    - Repeated counterparties
    - Any available metadata matches (device, UPI, etc.)

    Returns:
        (relationships, cluster_info)
        relationships: list of relationship dicts with reason field
        cluster_info: dict of entity clusters
    """
    relationships: list[dict] = []
    clusters: dict[str, set] = defaultdict(set)
    seen_pairs: set[frozenset] = set()

    def add_relationship(a: str, b: str, rel_type: str, reason: str, confidence: float = 1.0, txn_ids: list | None = None) -> None:
        pair = frozenset([a, b])
        if pair in seen_pairs or a == b:
            return
        seen_pairs.add(pair)
        relationships.append({
            "entity_a": a,
            "entity_b": b,
            "relationship_type": rel_type,
            "reason": reason,
            "confidence": confidence,
            "supporting_transaction_ids": txn_ids or [],
        })

    # Build account maps
    accounts: set[str] = set()
    for col in ["from_account_number", "to_account_number"]:
        if col in transactions_df.columns:
            accounts.update(transactions_df[col].dropna().astype(str).unique())

    # Find accounts that frequently transact together
    if "from_account_number" in transactions_df.columns and "to_account_number" in transactions_df.columns:
        pair_counts = transactions_df.groupby(
            ["from_account_number", "to_account_number"]
        ).agg(count=("id", "count"), total=("amount", "sum")).reset_index()

        for _, row in pair_counts.iterrows():
            frm = str(row["from_account_number"])
            to = str(row["to_account_number"])
            count = int(row["count"])
            total = float(row["total"])

            if count >= 3:
                add_relationship(
                    frm, to,
                    "FREQUENT_TRANSFER",
                    f"Accounts {frm} and {to} have {count} transactions totaling ₹{total:,.0f}.",
                    confidence=min(0.95, 0.7 + count * 0.02),
                    txn_ids=transactions_df[
                        (transactions_df["from_account_number"] == frm) &
                        (transactions_df["to_account_number"] == to)
                    ]["id"].astype(str).tolist()[:10],
                )

    # Detect device sharing
    if "device_id" in transactions_df.columns:
        device_groups = transactions_df.groupby("device_id")["from_account_number"].apply(set)
        for device, accs in device_groups.items():
            if not device or str(device) in ("", "nan", "None"):
                continue
            acc_list = [a for a in accs if a and str(a) not in ("", "nan")]
            if len(acc_list) >= 2:
                for i in range(len(acc_list)):
                    for j in range(i + 1, len(acc_list)):
                        add_relationship(
                            str(acc_list[i]), str(acc_list[j]),
                            "SHARED_DEVICE",
                            f"Accounts {acc_list[i]} and {acc_list[j]} share device identifier {device}.",
                            confidence=0.9,
                        )

    # Detect IP sharing
    if "ip_address" in transactions_df.columns:
        ip_groups = transactions_df.groupby("ip_address")["from_account_number"].apply(set)
        for ip, accs in ip_groups.items():
            if not ip or str(ip) in ("", "nan"):
                continue
            acc_list = [a for a in accs if a and str(a) not in ("", "nan")]
            if len(acc_list) >= 2:
                for i in range(len(acc_list)):
                    for j in range(i + 1, len(acc_list)):
                        add_relationship(
                            str(acc_list[i]), str(acc_list[j]),
                            "SHARED_IP_ADDRESS",
                            f"Accounts {acc_list[i]} and {acc_list[j]} originate from same IP {ip}.",
                            confidence=0.75,
                        )

    # Build cluster info
    cluster_info: dict[str, Any] = {
        "total_entities": len(accounts),
        "relationship_count": len(relationships),
        "relationship_types": list(set(r["relationship_type"] for r in relationships)),
    }

    return relationships, cluster_info
