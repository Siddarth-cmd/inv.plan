from typing import List, Optional
from pydantic import BaseModel

from .case import NormalizedCase
from .classification import AlertClassification
from .fact import Fact
from .red_flag import RedFlag
from .information_gap import InformationGap
from .question import InvestigationQuestion
from .evidence import EvidenceRequirement
from .sequence import InvestigationStepPlan
from .decision import DecisionPoint

class AuditMetadata(BaseModel):
    generator_info: str
    timestamp: str
    mode: str

class InvestigationPlan(BaseModel):
    plan_version: str = "1.0"
    case: NormalizedCase
    classification: AlertClassification
    facts: List[Fact]
    red_flags: List[RedFlag]
    information_gaps: List[InformationGap]
    investigation_questions: List[InvestigationQuestion]
    evidence_requirements: List[EvidenceRequirement]
    investigation_steps: List[InvestigationStepPlan]
    decision_points: List[DecisionPoint]
    possible_outcomes: List[str]
    audit: AuditMetadata
