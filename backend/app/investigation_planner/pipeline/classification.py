"""
Alert Classification Stage.

Determines which financial-crime category/typology the alert belongs to.
Uses the configurable CLASSIFICATION_RULES from taxonomy.py.
Uses "Potential X" language — never asserts guilt.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from ..config.taxonomy import (
    CLASSIFICATION_RULES,
    ClassificationStatus,
    CATEGORIES,
)
from ..schemas.case import NormalizedCase
from ..schemas.classification import AlertClassification
from ..schemas.fact import Fact
from ..schemas.red_flag import RedFlag
from .red_flags import get_signals


def classify_alert(
    case: NormalizedCase,
    facts: List[Fact],
    red_flags: List[RedFlag],
) -> AlertClassification:
    """Stage 4 – Classify the alert into a category using the taxonomy rule engine."""

    signals = get_signals(case, facts)
    signal_keys = set(signals.keys())

    # ── Try rules in priority order ───────────────────────────────────────────
    best_rule: Optional[Dict[str, Any]] = None
    best_match_count = 0

    for rule in CLASSIFICATION_RULES:
        required = set(rule["signals"])
        match_count = len(required & signal_keys)
        # Rule triggers only if ALL required signals are present
        if match_count == len(required) and match_count > best_match_count:
            best_rule = rule
            best_match_count = match_count

    if best_rule:
        category   = best_rule["category"]
        typology   = best_rule.get("typology")
        confidence = best_rule["base_confidence"]

        # Boost confidence if multiple red flags corroborate
        if len(red_flags) >= 2:
            confidence = min(confidence + 0.05, 0.95)

        # Prefix with "Potential" for non-confirmed classifications
        display_category = f"Potential {category}" if not category.startswith("Potential") else category
        status = ClassificationStatus.REQUIRES_REVIEW

    else:
        # No rule matched — escalate to manual review
        display_category = "Unknown / Requires Review"
        typology         = None
        confidence       = 0.40
        status           = ClassificationStatus.REQUIRES_REVIEW

    # Validate category is in taxonomy
    raw_category = display_category.replace("Potential ", "")
    if raw_category not in CATEGORIES and display_category not in CATEGORIES:
        display_category = "Unknown / Requires Review"
        typology         = None
        confidence       = 0.35

    return AlertClassification(
        primary_category=display_category,
        subcategory=typology,
        confidence=round(confidence, 3),
        classification_status=status,
        rationale="",   # Filled by rationale stage
    )
