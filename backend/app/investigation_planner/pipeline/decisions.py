"""
Decision Point Generation Stage.

Produces conditional decision objects for each investigation step.
Decisions are structured, not executable code.
The future orchestration layer will evaluate conditions and follow branches.
"""
from __future__ import annotations

from typing import List

from ..schemas.decision import DecisionPoint
from ..schemas.sequence import InvestigationStepPlan

_CONDITION_MAP = {
    "source_of_funds":     ("source_of_funds_is_verified_and_legitimate", "reduce_source_of_funds_concern", "continue_enhanced_source_investigation"),
    "historical behav":    ("transaction_is_significantly_outside_historical_behaviour", "continue_enhanced_investigation", "reduce_transaction_anomaly_concern"),
    "beneficiary":         ("beneficiary_relationship_is_established_and_plausible", "reduce_beneficiary_concern", "continue_enhanced_beneficiary_investigation"),
    "jurisdiction":        ("jurisdiction_exposure_is_explainable_and_compliant", "reduce_jurisdiction_concern", "escalate_for_sanctions_and_aml_review"),
    "structuring":         ("structuring_pattern_is_confirmed_across_transactions", "escalate_for_regulatory_reporting", "reduce_structuring_concern"),
    "device":              ("device_change_was_authorised_by_account_holder", "reduce_account_takeover_concern", "escalate_for_account_takeover_response"),
    "kyc":                 ("identity_documents_are_valid_and_consistent", "reduce_identity_concern", "escalate_for_identity_fraud_review"),
    "purpose":             ("transaction_purpose_is_plausible_and_documented", "reduce_purpose_concern", "continue_enhanced_purpose_investigation"),
    "default":             ("finding_supports_risk_escalation", "escalate_risk_assessment", "reduce_concern_and_continue"),
}


def _get_condition_triplet(objective: str):
    obj_lower = objective.lower()
    for key, triplet in _CONDITION_MAP.items():
        if key in obj_lower:
            return triplet
    return _CONDITION_MAP["default"]


def generate_decision_points(steps: List[InvestigationStepPlan]) -> List[DecisionPoint]:
    """Stage 11 – Create conditional decision branching for each investigation step."""
    decisions: List[DecisionPoint] = []

    for i, step in enumerate(steps):
        condition, if_true, if_false = _get_condition_triplet(step.objective)

        decisions.append(DecisionPoint(
            decision_id=f"D{i + 1:03d}",
            after_step=step.step_id,
            condition=condition,
            if_true=if_true,
            if_false=if_false,
            reason=(
                f"After completing {step.step_id} ('{step.objective[:60]}...'), "
                f"the investigator evaluates the condition '{condition}' to determine the next path. "
                f"A positive finding triggers '{if_true}'; a negative finding triggers '{if_false}'."
            ),
        ))

    return decisions
