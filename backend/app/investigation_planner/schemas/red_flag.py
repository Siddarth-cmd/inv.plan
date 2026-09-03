from typing import List, Optional, Any
from pydantic import BaseModel

class RedFlag(BaseModel):
    red_flag_id: str
    description: str
    severity: str
    evidence_refs: List[str]
    observed_value: Optional[Any] = None
    comparison_baseline: Optional[Any] = None
    confidence: float
    rationale: str
