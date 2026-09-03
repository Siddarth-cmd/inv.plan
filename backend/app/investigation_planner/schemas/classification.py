from typing import Optional
from pydantic import BaseModel

class AlertClassification(BaseModel):
    primary_category: str
    subcategory: Optional[str] = None
    confidence: float
    classification_status: str
    rationale: str
