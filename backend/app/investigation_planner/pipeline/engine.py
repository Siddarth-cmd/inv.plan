"""
Investigation Plan Generation Engine.

Orchestrates the 12-stage planning pipeline:
  1. normalize_case
  2. extract_facts
  3. identify_red_flags
  4. classify_alert
  5. generate_classification_rationale
  6. identify_information_gaps
  7. generate_investigation_questions
  8. map_evidence_requirements
  9. prioritize_questions
  10. generate_investigation_sequence
  11. generate_decision_points
  12. validate_investigation_plan → return InvestigationPlan

No hypothesis generation. No agent orchestration. No hard-coded plans.
All output is dynamically derived from the specific alert input.
"""
from __future__ import annotations

from datetime import datetime, timezone

from ..config.taxonomy import ALL_OUTCOMES
from ..schemas.alert import RawAlertInput
from ..schemas.plan import AuditMetadata, InvestigationPlan
from ..validation.plan_validator import PlanValidationError, validate_plan
from .classification import classify_alert
from .decisions import generate_decision_points
from .evidence import map_evidence_requirements
from .facts import extract_facts
from .information_gaps import identify_information_gaps
from .normalize import normalize_case
from .prioritization import prioritize_questions
from .questions import generate_investigation_questions
from .rationale import generate_classification_rationale
from .red_flags import identify_red_flags
from .sequencing import generate_investigation_sequence


def generate_plan(alert: RawAlertInput) -> InvestigationPlan:
    """Generate a fully validated InvestigationPlan from a raw alert input."""

    # ── Stage 1: Normalize ────────────────────────────────────────────────────
    case = normalize_case(alert)

    # ── Stage 2: Extract Facts ────────────────────────────────────────────────
    facts = extract_facts(case)

    # ── Stage 3: Identify Red Flags ───────────────────────────────────────────
    red_flags = identify_red_flags(case, facts)

    # ── Stage 4: Classify Alert ───────────────────────────────────────────────
    classification = classify_alert(case, facts, red_flags)

    # ── Stage 5: Classification Rationale ─────────────────────────────────────
    classification = generate_classification_rationale(classification, facts, red_flags)

    # ── Stage 6: Information Gaps ─────────────────────────────────────────────
    gaps = identify_information_gaps(case, red_flags)

    # ── Stage 7: Investigation Questions ─────────────────────────────────────
    questions = generate_investigation_questions(gaps, red_flags)

    # ── Stage 8: Evidence Requirements ───────────────────────────────────────
    evidence_reqs = map_evidence_requirements(questions)

    # ── Stage 9: Prioritize Questions ────────────────────────────────────────
    questions = prioritize_questions(questions)

    # ── Stage 10: Investigation Sequence ─────────────────────────────────────
    steps = generate_investigation_sequence(questions)

    # ── Stage 11: Decision Points ─────────────────────────────────────────────
    decisions = generate_decision_points(steps)

    # ── Stage 12: Assemble & Validate Plan ───────────────────────────────────
    plan = InvestigationPlan(
        plan_version="1.0",
        case=case,
        classification=classification,
        facts=facts,
        red_flags=red_flags,
        information_gaps=gaps,
        investigation_questions=questions,
        evidence_requirements=evidence_reqs,
        investigation_steps=steps,
        decision_points=decisions,
        possible_outcomes=ALL_OUTCOMES,
        audit=AuditMetadata(
            generator_info="FinSpectra Investigation Planner Engine v1.0",
            timestamp=datetime.now(timezone.utc).isoformat(),
            mode="Rule-Based Dynamic Pipeline",
        ),
    )

    # Deterministic validation — will raise PlanValidationError if plan is malformed
    validate_plan(plan)

    return plan
