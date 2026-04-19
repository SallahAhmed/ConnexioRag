from pydantic import BaseModel
from typing import Optional

class PushRequest(BaseModel):
    project_id: int
    do_reset: Optional[int] = 0

class SearchRequest(BaseModel):
    project_id: int
    text: str
    limit: Optional[int] = 5