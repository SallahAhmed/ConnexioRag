from pydantic import BaseModel, Field
from typing import Optional, List


class AgentChatRequest(BaseModel):
    """Main agent conversation request."""
    query: str = Field(..., min_length=1, max_length=5000, description="The user's message")
    user_id: int = Field(..., description="Backend user ID")
    persona: Optional[str] = Field("student", description="student | early_career | educator | company")
    session_id: Optional[int] = Field(None, description="Existing session ID to continue conversation")
    limit: Optional[int] = Field(5, description="Max documents to retrieve from knowledge base")
    model_tier: Optional[str] = Field("auto", description="auto | utility | generation — force which model to use")

