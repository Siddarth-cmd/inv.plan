from typing import List
from pydantic import BaseModel

class EvidenceRequirement(BaseModel):
    evidence_id: str
    evidence_type: str
    description: str
    why_required: str
    source_category: str
    availability: str
    related_question_ids: List[str]
