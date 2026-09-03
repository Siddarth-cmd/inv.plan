"""
Classification Rationale Stage.

Explains WHY the alert was classified into its category.
Each rationale item references a red flag ID → fact IDs → source fields.
No invented evidence. Traceable reasoning chain only.
"""
from __future__ import annotations

from typing import List

from ..schemas.classification import AlertClassification
from ..schemas.fact import Fact
from ..schemas.red_flag import RedFlag


def generate_classification_rationale(
    classification: AlertClassification,
    facts: List[Fact],
    red_flags: List[RedFlag],
) -> AlertClassification:
    """Stage 5 – Attach a traceable evidence-backed rationale to the classification."""

    fact_map = {f.fact_id: f for f in facts}

    lines: List[str] = [
        f"CATEGORY: {classification.primary_category}",
        f"SUBCATEGORY/TYPOLOGY: {classification.subcategory or 'Not specified'}",
        "",
        "RATIONALE:",
    ]

    if not red_flags:
        lines.append(
            "  No specific red flags identified. Classification defaulted to 'Unknown / Requires Review'."
        )
    else:
        for i, rf in enumerate(red_flags, 1):
            lines.append(f"  {i}. [{rf.red_flag_id}] {rf.description}")
            lines.append(f"     Severity: {rf.severity} | Confidence: {rf.confidence:.0%}")
            lines.append(f"     Rationale: {rf.rationale}")

            # Attach supporting facts
            supporting = [fact_map[fid] for fid in rf.evidence_refs if fid in fact_map]
            if supporting:
                lines.append("     Supporting Facts:")
                for sf in supporting:
                    lines.append(f"       • [{sf.fact_id}] {sf.statement}  (source: {sf.source})")
            lines.append("")

    lines.append(f"CLASSIFICATION CONFIDENCE: {classification.confidence:.0%}")
    lines.append(f"STATUS: {classification.classification_status}")
    lines.append("")
    lines.append("TRACEABILITY CHAIN:")
    lines.append(f"  Classification → {' | '.join(rf.red_flag_id for rf in red_flags)}")
    for rf in red_flags:
        supporting = [fact_map[fid] for fid in rf.evidence_refs if fid in fact_map]
        if supporting:
            lines.append(f"  {rf.red_flag_id} → {' | '.join(sf.fact_id for sf in supporting)}")
            for sf in supporting:
                lines.append(f"    {sf.fact_id} → source: {sf.source}")

    classification.rationale = "\n".join(lines)
    return classification
