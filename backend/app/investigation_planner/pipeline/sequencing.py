"""
Investigation Sequencing Stage.

Converts prioritised questions into an ordered investigation plan.
Sequences by: priority, dependencies, logical investigative progression.
"""
from __future__ import annotations

from typing import List

from ..schemas.question import InvestigationQuestion
from ..schemas.sequence import InvestigationStepPlan

_RATIONALE_MAP = {
    "high_value": "Validating the transaction anomaly first establishes the base risk level for the rest of the investigation.",
    "source_of_funds": "Source-of-funds verification is the foundational step in assessing fund legitimacy.",
    "beneficiary": "Establishing the beneficiary relationship determines whether the transfer has a plausible legitimate purpose.",
    "international": "Assessing cross-border risk and jurisdiction exposure early guides the depth of subsequent steps.",
    "structuring": "Identifying the structuring pattern requires full transaction context, which should be retrieved early.",
    "device": "Verifying account access authenticity must be prioritised to confirm whether the instruction was authorised.",
    "kyc": "Identity verification is a prerequisite before assessing the legitimacy of any transaction.",
    "purpose": "Understanding the transaction's stated purpose supports or challenges the other investigation findings.",
    "default": "Investigation step proceeds in logical sequence based on priority and evidence availability.",
}


def _get_rationale(question: str) -> str:
    q_lower = question.lower()
    for key, rationale in _RATIONALE_MAP.items():
        if key in q_lower:
            return rationale
    return _RATIONALE_MAP["default"]


def generate_investigation_sequence(questions: List[InvestigationQuestion]) -> List[InvestigationStepPlan]:
    """Stage 10 – Generate an ordered investigation sequence from prioritised questions."""
    steps: List[InvestigationStepPlan] = []

    for i, q in enumerate(questions):
        step_id = f"STEP{i + 1:03d}"
        # Each step depends on the immediately preceding step (linear for now)
        dependency = [f"STEP{i:03d}"] if i > 0 else []

        steps.append(InvestigationStepPlan(
            step_id=step_id,
            order=i + 1,
            objective=q.objective,
            question_ids=[q.question_id],
            required_evidence=q.required_evidence,
            priority=q.priority,
            dependency=dependency,
            rationale=_get_rationale(q.question),
            expected_output=q.expected_answer_type,
        ))

    return steps
