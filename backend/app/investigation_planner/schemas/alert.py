from typing import Optional, Dict, Any

from pydantic import BaseModel

class RawAlertInput(BaseModel):
    alert_id: str
    customer_id: Optional[str] = None
    transaction_id: Optional[str] = None
    alert_type: Optional[str] = None
    alert_reason: Optional[str] = None
    transaction_amount: Optional[float] = None
    currency: Optional[str] = None
    transaction_type: Optional[str] = None
    timestamp: Optional[str] = None
    origin_country: Optional[str] = None
    destination_country: Optional[str] = None
    sender_information: Optional[Dict[str, Any]] = None
    receiver_information: Optional[Dict[str, Any]] = None
    beneficiary_information: Optional[Dict[str, Any]] = None
    customer_information: Optional[Dict[str, Any]] = None
    historical_information: Optional[Dict[str, Any]] = None
    additional_metadata: Optional[Dict[str, Any]] = None
