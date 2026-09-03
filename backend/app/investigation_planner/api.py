"""
Investigation Planner API Router.

POST /api/investigation-planner/plan      — Generate validated InvestigationPlan from alert
POST /api/investigation-planner/validate  — Validate any plan JSON
GET  /api/investigation-planner/scenarios — List sample test scenarios
GET  /api/investigation-planner/taxonomy  — Return active taxonomy configuration
"""
from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, HTTPException

from .config.taxonomy import CATEGORIES, ALL_OUTCOMES
from .pipeline.engine import generate_plan
from .scenarios.sample_alerts import get_all_scenarios, get_scenario_labels
from .schemas.alert import RawAlertInput
from .schemas.plan import InvestigationPlan
from .validation.plan_validator import PlanValidationError, validate_plan

router = APIRouter()


@router.post("/plan", response_model=InvestigationPlan)
async def create_investigation_plan(alert: RawAlertInput) -> InvestigationPlan:
    """
    Generate a fully validated InvestigationPlan from an alert payload.
    The plan is dynamically derived — no static templates.
    """
    try:
        plan = generate_plan(alert)
        return plan
    except PlanValidationError as e:
        raise HTTPException(status_code=422, detail=f"Plan validation failed: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Plan generation failed: {str(e)}")


@router.post("/validate")
async def validate_existing_plan(plan: InvestigationPlan) -> Dict[str, Any]:
    """Validate any InvestigationPlan JSON against the deterministic validator."""
    try:
        validate_plan(plan)
        return {"status": "valid", "message": "Plan passed all validation checks."}
    except PlanValidationError as e:
        raise HTTPException(status_code=400, detail=f"Validation failed: {str(e)}")


@router.get("/scenarios")
async def get_scenarios() -> Dict[str, Any]:
    """Return all 8 pre-configured sample alert scenarios."""
    scenarios = get_all_scenarios()
    labels    = get_scenario_labels()
    return {
        "scenarios": {
            str(sid): {"label": labels.get(sid, f"Scenario {sid}"), "alert": data}
            for sid, data in scenarios.items()
        }
    }


@router.get("/taxonomy")
async def get_taxonomy() -> Dict[str, Any]:
    """Return the active taxonomy configuration."""
    return {
        "categories":  CATEGORIES,
        "severities":  ["HIGH", "MEDIUM", "LOW"],
        "priorities":  ["HIGH", "MEDIUM", "LOW"],
        "outcomes":    ALL_OUTCOMES,
    }
