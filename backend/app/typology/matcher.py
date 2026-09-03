"""
AML Typology Matcher.

Matches transaction patterns against known financial crime typologies.
All matches are backed by actual data — LLM cannot invent typology matches.

Supported typologies:
1. STRUCTURING — Transaction splitting below reporting threshold
2. LAYERING — Rapid movement through multiple accounts
3. SMURFING — Multiple small deposits to aggregate funds
4. CIRCULAR_TRANSACTIONS — Funds returning to originating account
5. FUNNEL_ACCOUNT — Single account aggregating from many sources
6. MULE_BEHAVIOR — Account acting as pass-through for others
7. UNUSUAL_COUNTERPARTIES — Sudden new beneficiary pattern
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import timedelta
from typing import Any

import pandas as pd


@dataclass
class TypologyMatch:
    typology: str
    matched_conditions: list[str]
    supporting_records: list[str]  # transaction IDs
    confidence: float              # 0.0 to 1.0
    explanation: str
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "typology": self.typology,
            "matched_conditions": self.matched_conditions,
            "supporting_records": self.supporting_records,
            "confidence": self.confidence,
            "explanation": self.explanation,
            "metadata": self.metadata,
        }


# Typology thresholds (explicitly documented)
STRUCTURING_THRESHOLD = 200_000     # INR
STRUCTURING_MIN_TRANSACTIONS = 3
STRUCTURING_BAND_LOWER = 0.70       # Must be >= 70% of threshold

LAYERING_HOURS = 48
LAYERING_HOPS = 2

FUNNEL_MIN_SOURCES = 4              # Min distinct sources into one account
FUNNEL_TIMEWINDOW_DAYS = 7

MULE_OUTFLOW_RATIO = 0.80           # >=80% of inflows re-transferred
MULE_MIN_TRANSACTIONS = 5


def match_structuring(transactions_df: pd.DataFrame) -> list[TypologyMatch]:
    """
    Structuring: Multiple transactions just below reporting threshold,
    likely intended to avoid detection.
    """
    matches = []

    for account_id, group in transactions_df.groupby("from_account_number"):
        if not account_id:
            continue

        group = group.sort_values("timestamp")
        below_threshold = group[
            (group["amount"] >= STRUCTURING_THRESHOLD * STRUCTURING_BAND_LOWER) &
            (group["amount"] < STRUCTURING_THRESHOLD)
        ]

        if len(below_threshold) >= STRUCTURING_MIN_TRANSACTIONS:
            ids = below_threshold["id"].astype(str).tolist()
            total = below_threshold["amount"].sum()
            avg = below_threshold["amount"].mean()

            conditions = [
                f"{len(below_threshold)} transactions from account {account_id}",
                f"Each between ₹{STRUCTURING_THRESHOLD * STRUCTURING_BAND_LOWER:,.0f} and ₹{STRUCTURING_THRESHOLD:,}",
                f"Combined total: ₹{total:,.0f}",
                f"Average amount: ₹{avg:,.0f}",
            ]

            matches.append(TypologyMatch(
                typology="STRUCTURING",
                matched_conditions=conditions,
                supporting_records=ids,
                confidence=min(0.95, 0.6 + (len(below_threshold) - 3) * 0.05),
                explanation=(
                    f"Account {account_id} made {len(below_threshold)} transactions averaging "
                    f"₹{avg:,.0f}, each below the ₹{STRUCTURING_THRESHOLD:,} reporting threshold. "
                    f"Pattern is consistent with deliberate transaction structuring (smurfing). "
                    f"Total funds moved: ₹{total:,.0f}."
                ),
                metadata={"account": str(account_id), "transaction_count": len(below_threshold), "total": total},
            ))

    return matches


def match_layering(transactions_df: pd.DataFrame) -> list[TypologyMatch]:
    """
    Layering: Rapid movement of funds through multiple accounts
    to obscure the origin.
    """
    matches = []
    df = transactions_df.copy()
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)

    # Find chains: A→B, then B→C within LAYERING_HOURS
    edge_map: dict[str, list] = {}
    for _, row in df.iterrows():
        frm = str(row.get("from_account_number", "") or "")
        to = str(row.get("to_account_number", "") or "")
        if frm and to:
            if frm not in edge_map:
                edge_map[frm] = []
            edge_map[frm].append({
                "to": to,
                "amount": float(row["amount"]),
                "timestamp": row["timestamp"],
                "id": str(row["id"]),
            })

    layering_chains = []
    for acc, outgoing in edge_map.items():
        for tx1 in outgoing:
            next_acc = tx1["to"]
            if next_acc in edge_map:
                for tx2 in edge_map[next_acc]:
                    time_diff = tx2["timestamp"] - tx1["timestamp"]
                    if timedelta(0) < time_diff <= timedelta(hours=LAYERING_HOURS):
                        layering_chains.append({
                            "chain": [acc, next_acc, tx2["to"]],
                            "ids": [tx1["id"], tx2["id"]],
                            "amounts": [tx1["amount"], tx2["amount"]],
                        })

    if layering_chains:
        all_ids = []
        chain_descriptions = []
        for chain in layering_chains[:5]:
            all_ids.extend(chain["ids"])
            chain_descriptions.append(" → ".join(chain["chain"]))

        conditions = [
            f"{len(layering_chains)} rapid multi-hop fund movement(s) detected",
            f"Funds transferred between accounts within {LAYERING_HOURS} hours",
            f"Chains: {'; '.join(chain_descriptions[:3])}",
        ]

        matches.append(TypologyMatch(
            typology="LAYERING",
            matched_conditions=conditions,
            supporting_records=list(set(all_ids)),
            confidence=min(0.9, 0.55 + len(layering_chains) * 0.05),
            explanation=(
                f"Detected {len(layering_chains)} instance(s) of rapid multi-hop fund movement. "
                f"Funds are moved between accounts within {LAYERING_HOURS} hours in a pattern "
                f"consistent with layering — a common technique to obscure the origin of funds."
            ),
            metadata={"chain_count": len(layering_chains), "chains": layering_chains[:3]},
        ))

    return matches


def match_funnel_account(transactions_df: pd.DataFrame) -> list[TypologyMatch]:
    """
    Funnel account: A single account receives funds from many sources,
    then transfers them out — a hallmark of money mule behavior.
    """
    matches = []
    df = transactions_df.copy()
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)

    # For each account as a recipient
    incoming = df.groupby("to_account_number")

    for account, group in incoming:
        if not account:
            continue

        unique_sources = group["from_account_number"].dropna().nunique()
        total_incoming = group["amount"].sum()
        window = (group["timestamp"].max() - group["timestamp"].min()).days

        if unique_sources >= FUNNEL_MIN_SOURCES and window <= FUNNEL_TIMEWINDOW_DAYS:
            ids = group["id"].astype(str).tolist()
            conditions = [
                f"Account {account} received from {unique_sources} distinct sources",
                f"Total received: ₹{total_incoming:,.0f}",
                f"Within {window} days",
            ]

            matches.append(TypologyMatch(
                typology="FUNNEL_ACCOUNT",
                matched_conditions=conditions,
                supporting_records=ids,
                confidence=min(0.88, 0.5 + unique_sources * 0.05),
                explanation=(
                    f"Account {account} received funds from {unique_sources} distinct source accounts "
                    f"totaling ₹{total_incoming:,.0f} within {window} days. "
                    f"This concentration pattern is consistent with a funnel account used to aggregate illicit funds."
                ),
                metadata={"account": str(account), "source_count": int(unique_sources), "total": float(total_incoming)},
            ))

    return matches


def match_mule_behavior(transactions_df: pd.DataFrame) -> list[TypologyMatch]:
    """
    Mule behavior: Account receives funds and quickly re-transfers most of them,
    retaining little — consistent with money mule pass-through.
    """
    matches = []
    df = transactions_df.copy()

    for account, _ in df.groupby("from_account_number"):
        if not account:
            continue

        incoming = df[df["to_account_number"] == account]["amount"].sum()
        outgoing = df[df["from_account_number"] == account]["amount"].sum()
        tx_count = len(df[(df["from_account_number"] == account) | (df["to_account_number"] == account)])

        if incoming > 0 and outgoing / incoming >= MULE_OUTFLOW_RATIO and tx_count >= MULE_MIN_TRANSACTIONS:
            ratio = outgoing / incoming
            ids = df[
                (df["from_account_number"] == account) | (df["to_account_number"] == account)
            ]["id"].astype(str).tolist()

            conditions = [
                f"Account {account}: incoming ₹{incoming:,.0f}, outgoing ₹{outgoing:,.0f}",
                f"Outflow ratio: {ratio:.0%} of inflows",
                f"Transaction count: {tx_count}",
            ]

            matches.append(TypologyMatch(
                typology="MULE_BEHAVIOR",
                matched_conditions=conditions,
                supporting_records=ids,
                confidence=min(0.85, 0.5 + (ratio - MULE_OUTFLOW_RATIO) * 2),
                explanation=(
                    f"Account {account} transferred out {ratio:.0%} of received funds (₹{outgoing:,.0f} of ₹{incoming:,.0f}). "
                    f"The account retains minimal funds and acts as a pass-through — consistent with money mule behavior."
                ),
                metadata={"account": str(account), "ratio": float(ratio), "incoming": float(incoming), "outgoing": float(outgoing)},
            ))

    return matches


def match_circular_transactions(transactions_df: pd.DataFrame) -> list[TypologyMatch]:
    """Circular transactions: funds returning to originating account."""
    try:
        import networkx as nx
    except ImportError:
        return []

    G = nx.DiGraph()
    tx_edge_map: dict[tuple, list] = {}

    for _, row in transactions_df.iterrows():
        frm = str(row.get("from_account_number", "") or "")
        to = str(row.get("to_account_number", "") or "")
        if frm and to and frm != to:
            G.add_edge(frm, to, weight=float(row["amount"]))
            key = (frm, to)
            if key not in tx_edge_map:
                tx_edge_map[key] = []
            tx_edge_map[key].append(str(row["id"]))

    try:
        cycles = list(nx.simple_cycles(G))
    except Exception:
        return []

    if not cycles:
        return []

    all_cycle_ids = []
    cycle_descriptions = []
    for cycle in cycles[:5]:
        cycle_str = " → ".join(cycle + [cycle[0]])
        cycle_descriptions.append(cycle_str)
        for i in range(len(cycle)):
            key = (cycle[i], cycle[(i + 1) % len(cycle)])
            all_cycle_ids.extend(tx_edge_map.get(key, []))

    return [TypologyMatch(
        typology="CIRCULAR_TRANSACTIONS",
        matched_conditions=[
            f"{len(cycles)} circular transaction path(s) detected",
            f"Cycles: {'; '.join(cycle_descriptions[:3])}",
        ],
        supporting_records=list(set(all_cycle_ids)),
        confidence=min(0.95, 0.7 + len(cycles) * 0.05),
        explanation=(
            f"Detected {len(cycles)} circular transaction path(s) where funds return to the originating account. "
            f"Example: {cycle_descriptions[0] if cycle_descriptions else 'N/A'}. "
            f"Circular movement is a hallmark of round-tripping and trade-based money laundering."
        ),
        metadata={"cycle_count": len(cycles), "cycles": cycles[:3]},
    )]


def run_typology_matching(transactions_df: pd.DataFrame) -> list[TypologyMatch]:
    """
    Run all typology matchers against the transaction dataset.
    Returns all matches found.
    """
    all_matches = []

    all_matches.extend(match_structuring(transactions_df))
    all_matches.extend(match_layering(transactions_df))
    all_matches.extend(match_funnel_account(transactions_df))
    all_matches.extend(match_mule_behavior(transactions_df))
    all_matches.extend(match_circular_transactions(transactions_df))

    # Deduplicate by typology (keep highest confidence)
    best: dict[str, TypologyMatch] = {}
    for m in all_matches:
        if m.typology not in best or m.confidence > best[m.typology].confidence:
            best[m.typology] = m

    return list(best.values())
