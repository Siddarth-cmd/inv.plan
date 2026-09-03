from typing import Any, Union, Optional
from pydantic import BaseModel

class Fact(BaseModel):
    fact_id: str
    statement: str
    source: str
    value: Optional[Any] = None
