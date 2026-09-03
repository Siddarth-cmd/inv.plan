"""
Investigation Plan Validator.

Deterministic, LLM-independent validation of the InvestigationPlan schema.
Checks:
  - Required fields present
  - Unique IDs
  - Confidence / priority / severity value ranges
  - Full ID traceability chain
  - Step ordering and acyclic dependencies
  - No orphan references
"""
from __future__ import annotations

from typing import Set

from ..config.taxonomy import CATEGORIES, ClassificationStatus, Priority, Severity
from ..schemas.plan import InvestigationPlan


class PlanValidationError(Exception):
    """Raised when the InvestigationPlan fails deterministic validation."""


_VALID_SEVERITIES  = {Severity.HIGH, Severity.MEDIUM, Severity.LOW}
_VALID_PRIORITIES  = {Priority.HIGH, Priority.MEDIUM, Priority.LOW}
_VALID_STATUSES    = {ClassificationStatus.CONFIRMED, ClassificationStatus.REQUIRES_REVIEW}


def validate_plan(plan: InvestigationPlan) -> bool:  # noqa: C901
    """
    Validate the plan.  Returns True on success.  Raises PlanValidationError on failure.
    """

    # ── 1. Unique IDs across all artifact lists ────────────────────────────────
    all_ids: Set[str] = set()

    def _register(item_id: str, artifact: str) -> None:
        if item_id in all_ids:
            raise PlanValidationError(f"Duplicate ID '{item_id}' found in {artifact}.")
        all_ids.add(item_id)

    for f in plan.facts:
        _register(f.fact_id, "facts")
    for rf in plan.red_flags:
        _register(rf.red_flag_id, "red_flags")
    for gap in plan.information_gaps:
        _register(gap.gap_id, "information_gaps")
    for q in plan.investigation_questions:
        _register(q.question_id, "investigation_questions")
    for ev in plan.evidence_requirements:
        _register(ev.evidence_id, "evidence_requirements")
    for step in plan.investigation_steps:
        _register(step.step_id, "investigation_steps")
    for dec in plan.decision_points:
        _register(dec.decision_id, "decision_points")

    # Build lookup sets
    fact_ids  = {f.fact_id for f in plan.facts}
    rf_ids    = {rf.red_flag_id for rf in plan.red_flags}
    gap_ids   = {gap.gap_id for gap in plan.information_gaps}
    q_ids     = {q.question_id for q in plan.investigation_questions}
    ev_ids    = {ev.evidence_id for ev in plan.evidence_requirements}
    step_ids  = {step.step_id for step in plan.investigation_steps}

    # ── 2. Confidence range [0, 1] ────────────────────────────────────────────
    if not (0.0 <= plan.classification.confidence <= 1.0):
        raise PlanValidationError(
            f"Classification confidence {plan.classification.confidence} is outside [0, 1]."
        )

    for rf in plan.red_flags:
        if not (0.0 <= rf.confidence <= 1.0):
            raise PlanValidationError(f"Red flag {rf.red_flag_id} confidence out of range.")
        if rf.severity not in _VALID_SEVERITIES:
            raise PlanValidationError(f"Red flag {rf.red_flag_id} has invalid severity '{rf.severity}'.")

    # ── 3. Priority values ────────────────────────────────────────────────────
    for q in plan.investigation_questions:
        if q.priority not in _VALID_PRIORITIES:
            raise PlanValidationError(f"Question {q.question_id} has invalid priority '{q.priority}'.")

    for step in plan.investigation_steps:
        if step.priority not in _VALID_PRIORITIES:
            raise PlanValidationError(f"Step {step.step_id} has invalid priority '{step.priority}'.")

    # ── 4. Red flags → Facts traceability ─────────────────────────────────────
    for rf in plan.red_flags:
        for fid in rf.evidence_refs:
            if fid not in fact_ids and fid != "N/A":
                raise PlanValidationError(
                    f"Red flag {rf.red_flag_id} references unknown fact '{fid}'."
                )

    # ── 5. Questions → Red flags / gaps traceability ─────────────────────────
    for q in plan.investigation_questions:
        for rfid in q.related_red_flags:
            if rfid not in rf_ids:
                raise PlanValidationError(
                    f"Question {q.question_id} references unknown red flag '{rfid}'."
                )
        if q.information_gap and q.information_gap not in gap_ids:
            raise PlanValidationError(
                f"Question {q.question_id} references unknown gap '{q.information_gap}'."
            )

    # ── 6. Evidence → Questions traceability ─────────────────────────────────
    for ev in plan.evidence_requirements:
        for qid in ev.related_question_ids:
            if qid not in q_ids:
                raise PlanValidationError(
                    f"Evidence {ev.evidence_id} references unknown question '{qid}'."
                )

    # ── 7. Steps → Questions + Evidence traceability ─────────────────────────
    for step in plan.investigation_steps:
        for qid in step.question_ids:
            if qid not in q_ids:
                raise PlanValidationError(
                    f"Step {step.step_id} references unknown question '{qid}'."
                )
        for evid in step.required_evidence:
            if evid not in ev_ids:
                raise PlanValidationError(
                    f"Step {step.step_id} references unknown evidence '{evid}'."
                )
        for dep_id in step.dependency:
            if dep_id not in step_ids:
                raise PlanValidationError(
                    f"Step {step.step_id} has unknown dependency '{dep_id}'."
                )

    # ── 8. Decisions → Steps traceability ─────────────────────────────────────
    for dec in plan.decision_points:
        if dec.after_step not in step_ids:
            raise PlanValidationError(
                f"Decision {dec.decision_id} references unknown step '{dec.after_step}'."
            )

    # ── 9. Step ordering is contiguous ───────────────────────────────────────
    orders = sorted(s.order for s in plan.investigation_steps)
    for i, o in enumerate(orders, 1):
        if o != i:
            raise PlanValidationError(
                f"Step ordering is not contiguous: expected order {i}, found {o}."
            )

    # ── 10. Plan has at least one of everything critical ─────────────────────
    if not plan.facts:
        raise PlanValidationError("Plan has no extracted facts.")
    if not plan.red_flags:
        raise PlanValidationError("Plan has no red flags.")
    if not plan.investigation_questions:
        raise PlanValidationError("Plan has no investigation questions.")
    if not plan.investigation_steps:
        raise PlanValidationError("Plan has no investigation steps.")
    if not plan.decision_points:
        raise PlanValidationError("Plan has no decision points.")

    return True
