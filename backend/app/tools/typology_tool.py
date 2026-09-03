"""
TypologyMatchTool — Deterministic AML typology pattern matching.

invest.planner references this tool by name.
Evidence Retrieval calls it. Analysis interprets results.
The LLM cannot override or invent typology matches.
"""
from __future__ import annotations

from typing import Any

import structlog

logger = structlog.get_logger("finspectra.tools.typology")


class TypologyMatch:
    """A single typology match result."""
    def __init__(
        self,
        typology: str,
        matched_conditions: list[str],
        supporting_records: list[str],
        confidence: float,
        explanation: str,
    ):
        self.typology = typology
        self.matched_conditions = matched_conditions
        self.supporting_records = supporting_records
        self.confidence = confidence
        self.explanation = explanation

    def to_dict(self) -> dict[str, Any]:
        return {
            "typology": self.typology,
            "matched_conditions": self.matched_conditions,
            "supporting_records": self.supporting_records,
            "confidence": self.confidence,
            "explanation": self.explanation,
        }


class TypologyMatchTool:
    """
    AML typology matching engine.
    All matches are deterministic rule-based — no LLM involvement.
    Each match includes matched_conditions and supporting_records for auditability.
    """

    THRESHOLD_STRUCTURING = 100_000   # INR threshold for structuring detection
    THRESHOLD_LARGE_TRANSFER = 500_000
    THRESHOLD_RAPID_PASSTHROUGH = 0.80
    STRUCTURING_WINDOW_DAYS = 7
    STRUCTURING_MIN_TXNS = 3

    def run(
        self,
        transactions: list[dict[str, Any]],
        graph_cycles: list[dict[str, Any]],
        graph_passthrough: list[dict[str, Any]],
        shared_devices: list[dict[str, Any]],
        rule_signals: list[dict[str, Any]],
    ) -> list[TypologyMatch]:
        """
        Run all typology rules against the case evidence.
        Returns list of TypologyMatch objects (may be empty if no patterns detected).
        """
        matches: list[TypologyMatch] = []

        matches.extend(self._check_structuring(transactions))
        matches.extend(self._check_circular(graph_cycles))
        matches.extend(self._check_layering(graph_passthrough, transactions))
        matches.extend(self._check_mule_accounts(shared_devices))
        matches.extend(self._check_large_transfers(transactions))
        matches.extend(self._check_rapid_velocity(transactions))

        logger.info("Typology matching complete", matches=len(matches))
        return matches

    def _check_structuring(self, transactions: list[dict]) -> list[TypologyMatch]:
        """
        Structuring / Smurfing: multiple transactions just below reporting threshold
        by the same account within a short window.
        """
        results = []
        # Group by from_account
        by_account: dict[str, list[dict]] = {}
        for txn in transactions:
            acc = txn.get("from_account_number") or txn.get("from_account", "")
            if acc:
                by_account.setdefault(acc, []).append(txn)

        for acc, txns in by_account.items():
            just_below = [
                t for t in txns
                if self.THRESHOLD_STRUCTURING * 0.75 <= t.get("amount", 0) < self.THRESHOLD_STRUCTURING
            ]
            if len(just_below) >= self.STRUCTURING_MIN_TXNS:
                total = sum(t.get("amount", 0) for t in just_below)
                conditions = [
                    f"{len(just_below)} transactions between "
                    f"{self.THRESHOLD_STRUCTURING * 0.75:,.0f}–{self.THRESHOLD_STRUCTURING:,.0f} INR",
                    f"Total structured amount: {total:,.0f} INR",
                    f"Account: {acc}",
                ]
                results.append(TypologyMatch(
                    typology="STRUCTURING_SMURFING",
                    matched_conditions=conditions,
                    supporting_records=[t.get("id", t.get("txn_ref", "")) for t in just_below],
                    confidence=min(0.5 + 0.1 * len(just_below), 0.95),
                    explanation=(
                        f"Account {acc} made {len(just_below)} transactions with amounts "
                        f"consistently just below the {self.THRESHOLD_STRUCTURING:,} INR threshold, "
                        f"totaling {total:,.0f} INR. This pattern is consistent with structuring "
                        f"to avoid reporting requirements."
                    ),
                ))
        return results

    def _check_circular(self, graph_cycles: list[dict]) -> list[TypologyMatch]:
        """Circular money movement: funds flow in a cycle back to the originator."""
        results = []
        for cycle in graph_cycles:
            if cycle.get("length", 0) >= 3 and cycle.get("total_amount", 0) > 50_000:
                nodes = cycle.get("nodes", [])
                results.append(TypologyMatch(
                    typology="CIRCULAR_TRANSFER",
                    matched_conditions=[
                        f"Cycle length: {cycle['length']} accounts",
                        f"Total circulated amount: {cycle['total_amount']:,.0f} INR",
                        f"Transaction count: {cycle.get('txn_count', '?')}",
                    ],
                    supporting_records=cycle.get("txn_ids", []),
                    confidence=0.75 + min(0.05 * cycle.get("length", 3), 0.2),
                    explanation=(
                        f"Detected a circular money flow among accounts: "
                        f"{' -> '.join(str(n) for n in nodes)} -> (back to start). "
                        f"Total amount circulated: {cycle['total_amount']:,.0f} INR. "
                        f"Circular patterns can indicate money laundering through layering."
                    ),
                ))
        return results

    def _check_layering(
        self, graph_passthrough: list[dict], transactions: list[dict]
    ) -> list[TypologyMatch]:
        """Rapid pass-through / layering: account receives and immediately forwards funds."""
        results = []
        txn_map = {t.get("id", t.get("txn_ref", "")): t for t in transactions}

        for node in graph_passthrough:
            ratio = node.get("passthrough_ratio", 0)
            if ratio >= self.THRESHOLD_RAPID_PASSTHROUGH and node.get("in_volume", 0) > 100_000:
                results.append(TypologyMatch(
                    typology="LAYERING_RAPID_PASSTHROUGH",
                    matched_conditions=[
                        f"Pass-through ratio: {ratio:.0%}",
                        f"Incoming volume: {node['in_volume']:,.0f} INR",
                        f"Outgoing volume: {node['out_volume']:,.0f} INR",
                        f"Account: {node.get('account', '?')}",
                    ],
                    supporting_records=node.get("out_destinations", []),
                    confidence=min(0.6 + ratio * 0.3, 0.95),
                    explanation=(
                        f"Account {node.get('account', '?')} forwarded {ratio:.0%} of received funds "
                        f"({node.get('out_volume', 0):,.0f} INR) to {len(node.get('out_destinations', []))} "
                        f"other accounts. This rapid pass-through behavior is consistent with layering — "
                        f"a money laundering technique to obscure the source of funds."
                    ),
                ))
        return results

    def _check_mule_accounts(self, shared_devices: list[dict]) -> list[TypologyMatch]:
        """Mule accounts: multiple accounts controlled from the same device."""
        results = []
        for device in shared_devices:
            if device.get("account_count", 0) >= 3:
                results.append(TypologyMatch(
                    typology="MULE_ACCOUNT_NETWORK",
                    matched_conditions=[
                        f"Device {device['device']} used by {device['account_count']} accounts",
                        f"Accounts: {', '.join(str(a) for a in device.get('accounts', [])[:5])}",
                    ],
                    supporting_records=device.get("accounts", []),
                    confidence=0.6 + 0.05 * device.get("account_count", 3),
                    explanation=(
                        f"Device {device['device']} was used to operate {device['account_count']} "
                        f"separate accounts. This is consistent with a mule account network where "
                        f"a single operator controls multiple accounts to distribute funds."
                    ),
                ))
        return results

    def _check_large_transfers(self, transactions: list[dict]) -> list[TypologyMatch]:
        """Unusually large single transfers with no documented purpose."""
        results = []
        large = [t for t in transactions if t.get("amount", 0) >= self.THRESHOLD_LARGE_TRANSFER]
        if large:
            top = sorted(large, key=lambda x: x.get("amount", 0), reverse=True)[:5]
            results.append(TypologyMatch(
                typology="LARGE_VALUE_TRANSFER",
                matched_conditions=[
                    f"{len(large)} transactions >= {self.THRESHOLD_LARGE_TRANSFER:,} INR",
                    f"Largest: {top[0].get('amount', 0):,.0f} INR",
                    f"Total: {sum(t.get('amount', 0) for t in large):,.0f} INR",
                ],
                supporting_records=[t.get("id", t.get("txn_ref", "")) for t in top],
                confidence=0.5 + min(0.05 * len(large), 0.4),
                explanation=(
                    f"Detected {len(large)} large-value transfers totaling "
                    f"{sum(t.get('amount', 0) for t in large):,.0f} INR, "
                    f"each exceeding {self.THRESHOLD_LARGE_TRANSFER:,} INR. "
                    f"Large-value transfers require enhanced due diligence."
                ),
            ))
        return results

    def _check_rapid_velocity(self, transactions: list[dict]) -> list[TypologyMatch]:
        """High transaction velocity: many transactions in a short window."""
        results = []
        from collections import Counter
        acc_counts: Counter = Counter()
        for txn in transactions:
            acc = txn.get("from_account_number") or txn.get("from_account", "")
            if acc:
                acc_counts[acc] += 1

        for acc, count in acc_counts.items():
            if count >= 10:
                results.append(TypologyMatch(
                    typology="HIGH_VELOCITY_TRANSACTIONS",
                    matched_conditions=[
                        f"Account {acc}: {count} transactions in dataset window",
                        f"Threshold: 10+ transactions",
                    ],
                    supporting_records=[
                        t.get("id", t.get("txn_ref", ""))
                        for t in transactions
                        if (t.get("from_account_number") or t.get("from_account", "")) == acc
                    ],
                    confidence=min(0.4 + 0.04 * count, 0.85),
                    explanation=(
                        f"Account {acc} executed {count} transactions in the analysis window. "
                        f"High transaction velocity may indicate account takeover, "
                        f"automated fraud, or intentional fund dispersal."
                    ),
                ))
        return results
