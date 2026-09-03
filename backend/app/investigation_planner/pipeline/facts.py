"""
Fact Extraction Stage.

Extracts objective, observable facts from the NormalizedCase.
Facts are separated from interpretation — no conclusions, no labels of guilt.
Every fact references the source field in the alert payload.
"""
from __future__ import annotations

from typing import List, Any, Optional

from ..schemas.case import NormalizedCase
from ..schemas.fact import Fact

_SENTINEL_VALUES = {"UNKNOWN", "NOT_PROVIDED", "NOT_AVAILABLE", "NOT_APPLICABLE"}


def _is_available(value: Any) -> bool:
    return value is not None and str(value) not in _SENTINEL_VALUES


def extract_facts(case: NormalizedCase) -> List[Fact]:
    """Stage 2 – Extract objective, sourced facts from a normalized case."""
    facts: List[Fact] = []
    counter = 1

    def add(statement: str, source: str, value: Any = None) -> None:
        nonlocal counter
        facts.append(Fact(
            fact_id=f"F{counter:03d}",
            statement=statement,
            source=source,
            value=value,
        ))
        counter += 1

    # ── Transaction facts ─────────────────────────────────────────────────────
    for txn in case.transactions:
        amt = txn.get("amount")
        cur = txn.get("currency")
        typ = txn.get("type")
        txn_id = txn.get("transaction_id")
        ts = txn.get("timestamp")

        if _is_available(amt):
            cur_label = f" {cur}" if _is_available(cur) else ""
            add(f"Transaction amount is {amt}{cur_label}.", "alert.transaction.amount", value=amt)

        if _is_available(cur):
            add(f"Transaction currency is {cur}.", "alert.transaction.currency", value=cur)

        if _is_available(typ):
            add(f"Transaction type is {typ}.", "alert.transaction.type", value=typ)

        if _is_available(txn_id):
            add(f"Transaction reference ID is {txn_id}.", "alert.transaction.id", value=txn_id)

        if _is_available(ts):
            add(f"Transaction timestamp is {ts}.", "alert.transaction.timestamp", value=ts)

    # ── Geographic facts ──────────────────────────────────────────────────────
    origin = case.geographic_information.get("origin")
    destination = case.geographic_information.get("destination")

    if _is_available(origin):
        add(f"Transaction origin country is {origin}.", "alert.origin_country", value=origin)

    if _is_available(destination):
        add(f"Transaction destination country is {destination}.", "alert.destination_country", value=destination)

    if _is_available(origin) and _is_available(destination) and origin != destination:
        add(
            f"Transaction is cross-border: from {origin} to {destination}.",
            "alert.origin_country + alert.destination_country",
            value={"origin": origin, "destination": destination},
        )

    # ── Entity facts ──────────────────────────────────────────────────────────
    for entity in case.entities:
        role = entity.get("role", "UNKNOWN_ROLE")
        name = entity.get("name") or entity.get("account_name")
        acc  = entity.get("account_number") or entity.get("account")
        status = entity.get("status")

        if name and _is_available(name):
            add(f"{role.capitalize()} name is {name}.", f"alert.{role.lower()}_information.name", value=name)
        if acc and _is_available(acc):
            add(f"{role.capitalize()} account number is {acc}.", f"alert.{role.lower()}_information.account", value=acc)
        if status and _is_available(status):
            add(f"{role.capitalize()} status is {status}.", f"alert.{role.lower()}_information.status", value=status)

    # ── Alert trigger facts ────────────────────────────────────────────────────
    alert_type   = case.alert_trigger.get("type")
    alert_reason = case.alert_trigger.get("reason")

    if _is_available(alert_type):
        add(f"Alert type is '{alert_type}'.", "alert.alert_type", value=alert_type)
    if _is_available(alert_reason):
        add(f"Alert reason: {alert_reason}.", "alert.alert_reason", value=alert_reason)

    # ── Customer context facts ────────────────────────────────────────────────
    for key, val in case.customer_context.items():
        if _is_available(val):
            add(f"Customer {key} is {val}.", f"alert.customer_information.{key}", value=val)

    # ── Guarantee at least one fact exists ────────────────────────────────────
    if not facts:
        add(
            "Alert triggered with alert ID present; other transaction details not provided.",
            "alert.alert_id",
            value=case.alert_id,
        )

    return facts
