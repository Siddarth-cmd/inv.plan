from pydantic import BaseModel

class DecisionPoint(BaseModel):
    decision_id: str
    after_step: str
    condition: str
    if_true: str
    if_false: str
    reason: str
