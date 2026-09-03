from pydantic import BaseModel

class InformationGap(BaseModel):
    gap_id: str
    description: str
