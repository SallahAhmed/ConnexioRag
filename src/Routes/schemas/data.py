from pydantic import BaseModel
from typing import Optional

class ProcessRequest(BaseModel):
    file_id: str = None
    chunk_size: Optional[int]=800
    overlap_size: Optional[int]=150
    do_reset: Optional[int]=0 # do refers that he will make an action 
    