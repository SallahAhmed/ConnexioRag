from enum import Enum

class WorkflowNodeEnum(Enum):
    ONBOARDING = "onboarding"
    TEAM_FORMATION = "team_formation"
    PHASE_TRANSITION = "phase_transition"
    BLOCKER = "blocker"
    MILESTONE_WARNING = "milestone_warning"
    GENERAL = "general"
