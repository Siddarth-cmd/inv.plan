from typing import List, Optional
from pydantic import BaseModel

class InvestigationStepPlan(BaseModel):
    step_id: str
    order: int
    objective: str
    question_ids: List[str]
    required_evidence: List[str]
    priority: str
    dependency: List[str]
    rationale: str
    expected_output: str
