"""
Deterministic Rule Signals.

Computes AML rule signals from raw transaction data.
Each signal includes: signal_type, severity, score, reason, supporting_transaction_ids.
No ML inference — purely deterministic rules.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any

import pandas as pd


def _parse_ts(ts_str: str) -> datetime:
    try:
        return datetime.fromisoformat(str(ts_str).replace("Z", "+00:00"))
    except Exception:
        return datetime.now(timezone.utc)


def compute_signals(transactions_df: pd.DataFrame) -> list[dict[str, Any]]:
    """
    Compute deterministic rule signals from transactions DataFrame.
    
    Returns:
        List of signal dicts, each with:
          signal_type, severity, score (0-1), reason, supporting_transaction_ids
    """
    signals: list[dict[str, Any]] = []
    df = transactions_df.copy()

    if df.empty:
        return signals

    # Normalize columns
    df["amount"] = pd.to_numeric(df["amount"], errors="coerce").fillna(0)
    df["timestamp"] = df["timestamp"].apply(_parse_ts)
    from_col = "from_account_number" if "from_account_number" in df.columns else "from_account"
    to_col = "to_account_number" if "to_account_number" in df.columns else "to_account"
    id_col = "id" if "id" in df.columns else "txn_ref"

    df["_from"] = df[from_col].fillna("").astype(str)
    df["_to"] = df[to_col].fillna("").astype(str)

    # ── Signal 1: Unusually large transactions ─────────────────────────────
    mean_amt = df["amount"].mean()
    std_amt = df["amount"].std() or 1.0
    threshold = mean_amt + 3 * std_amt
    large_txns = df[df["amount"] > max(threshold, 500_000)]
    if not large_txns.empty:
        for _, row in large_txns.iterrows():
            signals.append({
                "signal_type": "UNUSUALLY_LARGE_TRANSACTION",
                "severity": "HIGH",
                "score": min(0.5 + (row["amount"] - mean_amt) / (6 * std_amt + 1), 1.0),
                "reason": (
                    f"Transaction of {row['amount']:,.0f} INR is "
                    f"{(row['amount'] - mean_amt) / std_amt:.1f} std devs above account mean ({mean_amt:,.0f} INR)."
                ),
                "supporting_transaction_ids": [str(row.get(id_col, ""))],
            })

    # ── Signal 2: Structuring (amounts 75K–100K) ──────────────────────────
    by_account = df.groupby("_from")
    for acc, group in by_account:
        if not acc:
            continue
        struct_txns = group[(group["amount"] >= 75_000) & (group["amount"] < 100_000)]
        if len(struct_txns) >= 3:
            signals.append({
                "signal_type": "STRUCTURING_PATTERN",
                "severity": "HIGH",
                "score": min(0.6 + 0.05 * len(struct_txns), 0.95),
                "reason": (
                    f"Account {acc} made {len(struct_txns)} transactions between 75,000–100,000 INR "
                    f"(structuring zone), totaling {struct_txns['amount'].sum():,.0f} INR."
                ),
                "supporting_transaction_ids": struct_txns[id_col].tolist(),
            })

    # ── Signal 3: Transaction velocity ────────────────────────────────────
    for acc, group in by_account:
        if not acc or len(group) < 5:
            continue
        group_sorted = group.sort_values("timestamp")
        # Check for 5+ transactions in any 24-hour window
        for i in range(len(group_sorted)):
            window_start = group_sorted.iloc[i]["timestamp"]
            window_end = window_start + timedelta(hours=24)
            in_window = group_sorted[
                (group_sorted["timestamp"] >= window_start) &
                (group_sorted["timestamp"] <= window_end)
            ]
            if len(in_window) >= 5:
                signals.append({
                    "signal_type": "HIGH_TRANSACTION_VELOCITY",
                    "severity": "MEDIUM",
                    "score": min(0.3 + 0.08 * len(in_window), 0.85),
                    "reason": (
                        f"Account {acc} made {len(in_window)} transactions within 24 hours "
                        f"(total: {in_window['amount'].sum():,.0f} INR)."
                    ),
                    "supporting_transaction_ids": in_window[id_col].tolist(),
                })
                break  # Only report once per account

    # ── Signal 4: Round-amount concentration ──────────────────────────────
    round_txns = df[df["amount"] % 10000 == 0]
    if len(round_txns) >= 5:
        signals.append({
            "signal_type": "ROUND_AMOUNT_CONCENTRATION",
            "severity": "LOW",
            "score": min(0.2 + 0.04 * len(round_txns), 0.6),
            "reason": (
                f"{len(round_txns)} transactions are exact multiples of 10,000 INR, "
                f"which may indicate non-arm's-length transactions."
            ),
            "supporting_transaction_ids": round_txns[id_col].tolist()[:10],
        })

    # ── Signal 5: Shared device multiple accounts ──────────────────────────
    if "device_id" in df.columns:
        device_accounts = defaultdict(set)
        device_txns = defaultdict(list)
        for _, row in df.iterrows():
            dev = str(row.get("device_id", "")).strip()
            if dev and dev.upper() not in ("", "NAN", "NONE", "DEV_UNKNOWN"):
                device_accounts[dev].add(str(row["_from"]))
                device_txns[dev].append(str(row.get(id_col, "")))
        for dev, accounts in device_accounts.items():
            if len(accounts) >= 3:
                signals.append({
                    "signal_type": "SHARED_DEVICE_MULTIPLE_ACCOUNTS",
                    "severity": "HIGH",
                    "score": min(0.5 + 0.1 * len(accounts), 0.9),
                    "reason": (
                        f"Device {dev} used by {len(accounts)} different accounts: "
                        f"{', '.join(list(accounts)[:5])}."
                    ),
                    "supporting_transaction_ids": device_txns[dev][:10],
                })

    # ── Signal 6: Rapid pass-through (credit then immediate debit) ─────────
    for acc, group in by_account:
        credits = group[group.get("transaction_type", pd.Series(dtype=str)) == "CREDIT"].sort_values("timestamp")
        debits = group[group.get("transaction_type", pd.Series(dtype=str)) == "DEBIT"].sort_values("timestamp")
        if not credits.empty and not debits.empty:
            for _, credit_row in credits.iterrows():
                rapid_debits = debits[
                    (debits["timestamp"] >= credit_row["timestamp"]) &
                    (debits["timestamp"] <= credit_row["timestamp"] + timedelta(hours=2))
                ]
                if not rapid_debits.empty:
                    rapid_vol = rapid_debits["amount"].sum()
                    if rapid_vol / max(credit_row["amount"], 1) > 0.7 and rapid_vol > 50_000:
                        signals.append({
                            "signal_type": "RAPID_FUND_MOVEMENT",
                            "severity": "HIGH",
                            "score": 0.75,
                            "reason": (
                                f"Account {acc} received {credit_row['amount']:,.0f} INR and "
                                f"forwarded {rapid_vol:,.0f} INR within 2 hours."
                            ),
                            "supporting_transaction_ids": (
                                [str(credit_row.get(id_col, ""))] +
                                rapid_debits[id_col].tolist()
                            ),
                        })
                        break

    # ── Signal 7: Threat Intelligence IP Match / WAF Suspicious Traffic ──────
    for idx, row in df.iterrows():
        scenario = str(row.get("scenario_label", "")).upper()
        desc = str(row.get("description", "")).upper()
        ip = str(row.get("ip_address", "")).strip()
        if "WAF" in scenario or "WAF" in desc or "SUSPICIOUS" in desc:
            signals.append({
                "signal_type": "WAF_SUSPICIOUS_WEB_TRAFFIC",
                "severity": "CRITICAL" if "WAF" in scenario else "HIGH",
                "score": 0.90,
                "reason": (
                    f"WAF Security Rule triggered for IP {ip}: {row.get('description', 'Suspicious Web Traffic')}."
                ),
                "supporting_transaction_ids": [str(row.get(id_col, ""))],
            })

    # Deduplicate by signal_type+supporting_ids
    seen = set()
    unique_signals = []
    for sig in signals:
        key = (sig["signal_type"], tuple(sig["supporting_transaction_ids"][:3]))
        if key not in seen:
            seen.add(key)
            unique_signals.append(sig)

    return unique_signals

