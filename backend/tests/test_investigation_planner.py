"""
Comprehensive test suite for the FinSpectra Investigation Planner.

Tests all 8 scenario types. Verifies:
  - Normalization
  - Fact extraction (no hallucination)
  - Red flag identification with evidence references
  - Classification reasonableness
  - Classification rationale traceability
  - Information gap identification
  - Investigation question generation (actionable)
  - Evidence requirement mapping
  - Prioritization logic
  - Investigation sequencing
  - Decision point generation
  - Full plan validation
  - Materially different plans for different alerts
"""
from __future__ import annotations

import pytest

from app.investigation_planner.pipeline.engine import generate_plan
from app.investigation_planner.scenarios.sample_alerts import get_all_scenarios, get_scenario
from app.investigation_planner.schemas.alert import RawAlertInput
from app.investigation_planner.validation.plan_validator import PlanValidationError, validate_plan


@pytest.fixture(scope="module")
def all_scenarios():
    return get_all_scenarios()


@pytest.fixture(scope="module")
def all_plans(all_scenarios):
    plans = {}
    for sid, data in all_scenarios.items():
        alert = RawAlertInput(**data)
        plans[sid] = generate_plan(alert)
    return plans


# ─── 1. All scenarios generate valid plans ────────────────────────────────────

class TestAllScenariosGenerateValidPlans:

    def test_all_scenarios_pass_validation(self, all_plans):
        for sid, plan in all_plans.items():
            assert validate_plan(plan) is True, f"Scenario {sid} failed validation"

    def test_all_scenarios_have_facts(self, all_plans):
        for sid, plan in all_plans.items():
            assert len(plan.facts) > 0, f"Scenario {sid} has no facts"

    def test_all_scenarios_have_red_flags(self, all_plans):
        for sid, plan in all_plans.items():
            assert len(plan.red_flags) > 0, f"Scenario {sid} has no red flags"

    def test_all_scenarios_have_information_gaps(self, all_plans):
        for sid, plan in all_plans.items():
            assert len(plan.information_gaps) > 0, f"Scenario {sid} has no gaps"

    def test_all_scenarios_have_questions(self, all_plans):
        for sid, plan in all_plans.items():
            assert len(plan.investigation_questions) > 0, f"Scenario {sid} has no questions"

    def test_all_scenarios_have_evidence(self, all_plans):
        for sid, plan in all_plans.items():
            assert len(plan.evidence_requirements) > 0, f"Scenario {sid} has no evidence"

    def test_all_scenarios_have_steps(self, all_plans):
        for sid, plan in all_plans.items():
            assert len(plan.investigation_steps) > 0, f"Scenario {sid} has no steps"

    def test_all_scenarios_have_decisions(self, all_plans):
        for sid, plan in all_plans.items():
            assert len(plan.decision_points) > 0, f"Scenario {sid} has no decisions"

    def test_all_scenarios_have_possible_outcomes(self, all_plans):
        for sid, plan in all_plans.items():
            assert len(plan.possible_outcomes) > 0, f"Scenario {sid} has no outcomes"


# ─── 2. No hallucinated facts ─────────────────────────────────────────────────

class TestNoHallucination:

    def test_facts_reference_known_sources(self, all_plans):
        valid_source_prefixes = [
            "alert.transaction", "alert.origin_country", "alert.destination_country",
            "alert.sender", "alert.receiver", "alert.beneficiary", "alert.alert_type",
            "alert.alert_reason", "alert.customer_information", "alert.alert_id",
        ]
        for sid, plan in all_plans.items():
            for fact in plan.facts:
                matched = any(fact.source.startswith(p) for p in valid_source_prefixes)
                assert matched, (
                    f"Scenario {sid}: Fact {fact.fact_id} has an unknown source '{fact.source}'"
                )

    def test_red_flags_reference_valid_facts(self, all_plans):
        for sid, plan in all_plans.items():
            fact_ids = {f.fact_id for f in plan.facts}
            for rf in plan.red_flags:
                for fid in rf.evidence_refs:
                    assert fid in fact_ids or fid == "N/A", (
                        f"Scenario {sid}: Red flag {rf.red_flag_id} references unknown fact '{fid}'"
                    )

    def test_insufficient_info_scenario_has_no_invented_data(self, all_plans):
        """Scenario 7 has almost no data — facts must only reflect what was provided."""
        plan = all_plans[7]
        # Should not invent transaction amounts, countries etc.
        amount_facts = [f for f in plan.facts if "amount" in f.statement.lower()]
        assert len(amount_facts) == 0, "Scenario 7: No amount should be in facts (not provided)"


# ─── 3. Classification quality ────────────────────────────────────────────────

class TestClassification:

    def test_classification_categories_are_not_empty(self, all_plans):
        for sid, plan in all_plans.items():
            assert plan.classification.primary_category, f"Scenario {sid}: empty category"

    def test_classification_confidence_in_range(self, all_plans):
        for sid, plan in all_plans.items():
            conf = plan.classification.confidence
            assert 0.0 <= conf <= 1.0, f"Scenario {sid}: confidence out of range: {conf}"

    def test_classification_has_rationale(self, all_plans):
        for sid, plan in all_plans.items():
            assert len(plan.classification.rationale) > 50, (
                f"Scenario {sid}: classification rationale too short"
            )

    def test_rationale_references_red_flag_ids(self, all_plans):
        for sid, plan in all_plans.items():
            for rf in plan.red_flags:
                assert rf.red_flag_id in plan.classification.rationale, (
                    f"Scenario {sid}: red flag {rf.red_flag_id} not in rationale"
                )

    def test_high_value_scenario_is_not_classified_as_mule(self, all_plans):
        plan = all_plans[1]  # High-value international
        assert "Mule" not in plan.classification.primary_category

    def test_structuring_scenario_classification(self, all_plans):
        plan = all_plans[2]
        assert "Structuring" in plan.classification.primary_category or \
               plan.classification.primary_category == "Unknown / Requires Review"

    def test_mule_scenario_classification(self, all_plans):
        plan = all_plans[3]
        assert "Mule" in plan.classification.primary_category or \
               "Layering" in plan.classification.primary_category or \
               plan.classification.primary_category == "Unknown / Requires Review"

    def test_account_takeover_scenario_classification(self, all_plans):
        plan = all_plans[5]
        assert "Account Takeover" in plan.classification.primary_category or \
               plan.classification.primary_category == "Unknown / Requires Review"

    def test_kyc_scenario_classification(self, all_plans):
        plan = all_plans[6]
        assert "KYC" in plan.classification.primary_category or \
               "Identity" in plan.classification.primary_category or \
               plan.classification.primary_category == "Unknown / Requires Review"


# ─── 4. Questions are actionable ──────────────────────────────────────────────

class TestQuestions:

    def test_no_vague_questions(self, all_plans):
        vague_phrases = ["is this suspicious?", "is this fraud?", "is this money laundering?"]
        for sid, plan in all_plans.items():
            for q in plan.investigation_questions:
                q_lower = q.question.lower()
                for phrase in vague_phrases:
                    assert phrase not in q_lower, (
                        f"Scenario {sid}: vague question detected: '{q.question}'"
                    )

    def test_questions_reference_red_flags_or_gaps(self, all_plans):
        for sid, plan in all_plans.items():
            rf_ids  = {rf.red_flag_id for rf in plan.red_flags}
            gap_ids = {gap.gap_id for gap in plan.information_gaps}
            for q in plan.investigation_questions:
                has_rf  = any(rfid in rf_ids for rfid in q.related_red_flags)
                has_gap = q.information_gap and q.information_gap in gap_ids
                assert has_rf or has_gap, (
                    f"Scenario {sid}: Question {q.question_id} has no red flag or gap reference"
                )

    def test_high_priority_questions_come_first(self, all_plans):
        from app.investigation_planner.config.taxonomy import Priority
        priority_order = {Priority.HIGH: 0, Priority.MEDIUM: 1, Priority.LOW: 2}
        for sid, plan in all_plans.items():
            priorities = [priority_order[q.priority] for q in plan.investigation_questions]
            assert priorities == sorted(priorities), (
                f"Scenario {sid}: Questions not sorted by priority"
            )


# ─── 5. Steps are sequentially ordered ───────────────────────────────────────

class TestInvestigationSequence:

    def test_steps_are_ordered_sequentially(self, all_plans):
        for sid, plan in all_plans.items():
            orders = [s.order for s in plan.investigation_steps]
            assert orders == list(range(1, len(orders) + 1)), (
                f"Scenario {sid}: step orders not sequential: {orders}"
            )

    def test_step_references_question(self, all_plans):
        for sid, plan in all_plans.items():
            q_ids = {q.question_id for q in plan.investigation_questions}
            for step in plan.investigation_steps:
                for qid in step.question_ids:
                    assert qid in q_ids, (
                        f"Scenario {sid}: Step {step.step_id} references unknown question {qid}"
                    )


# ─── 6. Decision points are structurally valid ────────────────────────────────

class TestDecisionPoints:

    def test_decision_references_valid_step(self, all_plans):
        for sid, plan in all_plans.items():
            step_ids = {s.step_id for s in plan.investigation_steps}
            for dec in plan.decision_points:
                assert dec.after_step in step_ids, (
                    f"Scenario {sid}: Decision {dec.decision_id} references unknown step {dec.after_step}"
                )

    def test_decisions_have_both_branches(self, all_plans):
        for sid, plan in all_plans.items():
            for dec in plan.decision_points:
                assert dec.if_true, f"Scenario {sid}: Decision {dec.decision_id} has no if_true"
                assert dec.if_false, f"Scenario {sid}: Decision {dec.decision_id} has no if_false"
                assert dec.condition, f"Scenario {sid}: Decision {dec.decision_id} has no condition"


# ─── 7. Plans are materially different ───────────────────────────────────────

class TestMaterialDifferences:

    def test_different_scenarios_produce_different_classifications(self, all_plans):
        categories = {sid: all_plans[sid].classification.primary_category for sid in all_plans}
        # Not all scenarios should be the same category
        unique_cats = set(categories.values())
        assert len(unique_cats) > 1, "All scenarios produced the same classification category"

    def test_high_value_and_structuring_have_different_red_flags(self, all_plans):
        rf1 = {rf.description for rf in all_plans[1].red_flags}
        rf2 = {rf.description for rf in all_plans[2].red_flags}
        assert rf1 != rf2, "Scenario 1 and 2 have identical red flags"

    def test_takeover_and_kyc_have_different_red_flags(self, all_plans):
        rf5 = {rf.description for rf in all_plans[5].red_flags}
        rf6 = {rf.description for rf in all_plans[6].red_flags}
        assert rf5 != rf6, "Scenario 5 and 6 have identical red flags"

    def test_insufficient_info_scenario_has_fewer_facts(self, all_plans):
        """Scenario 7 (insufficient info) should have fewer facts than scenario 1."""
        plan7 = all_plans[7]
        plan1 = all_plans[1]
        assert len(plan7.facts) < len(plan1.facts), (
            "Scenario 7 (minimal data) should have fewer facts than scenario 1"
        )
