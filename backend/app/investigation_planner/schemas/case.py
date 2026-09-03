from typing import List, Dict, Any, Optional
from pydantic import BaseModel

class MissingInformation(BaseModel):
    item: str
    reason: Optional[str] = None

class NormalizedCase(BaseModel):
    case_id: str
    alert_id: str
    entities: List[Dict[str, Any]]
    transactions: List[Dict[str, Any]]
    customer_context: Dict[str, Any]
    temporal_information: Dict[str, Any]
    geographic_information: Dict[str, Any]
    alert_trigger: Dict[str, Any]
    available_evidence: List[Dict[str, Any]]
    missing_information: List[MissingInformation]
