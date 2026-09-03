from typing import List, Optional
from pydantic import BaseModel

class InvestigationQuestion(BaseModel):
    question_id: str
    question: str
    objective: str
    related_red_flags: List[str]
    information_gap: Optional[str] = None
    priority: str
    required_evidence: List[str]
    expected_answer_type: str
