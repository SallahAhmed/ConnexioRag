from pydantic import BaseModel, Field
from typing import Optional, List


class AgentChatRequest(BaseModel):
    """Main agent conversation request."""
    query: str = Field(..., min_length=1, description="The user's message")
    user_id: int = Field(..., description="Backend user ID")
    project_id: Optional[int] = Field(None, description="Project context ID")
    persona: Optional[str] = Field("student", description="student | early_career | educator | company")
    session_id: Optional[int] = Field(None, description="Existing session ID to continue conversation")
    limit: Optional[int] = Field(5, description="Max documents to retrieve from knowledge base")


class PortfolioRequest(BaseModel):
    """Request to generate a portfolio/resume entry for a user."""
    user_id: int = Field(..., description="Backend user ID")
    project_id: Optional[int] = Field(None, description="Specific project, or all if omitted")
    format: Optional[str] = Field("resume_entry", description="resume_entry | full_summary | linkedin")


class DocGenRequest(BaseModel):
    """Request to generate project documentation."""
    project_id: int = Field(..., description="Project to generate docs for")
    doc_type: Optional[str] = Field("readme", description="readme | retrospective | summary")


class CoachPathRequest(BaseModel):
    """Request for skill growth recommendations."""
    user_id: int = Field(..., description="Backend user ID")
    project_id: Optional[int] = Field(None, description="Optional project context")


class SupervisorRisksRequest(BaseModel):
    """Request for supervisor/educator team risk overview."""
    supervisor_id: Optional[int] = Field(None, description="Supervisor user ID")
    project_id: Optional[int] = Field(None, description="Specific project to check, or all")


class TaskArchitectRequest(BaseModel):
    """Request for step-by-step task resolution planning."""
    query: str = Field(..., min_length=1, description="The complex problem description")
    user_id: int = Field(..., description="Backend user ID")
    project_id: int = Field(..., description="Project context")
    limit: Optional[int] = Field(5, description="Max documents to retrieve")
