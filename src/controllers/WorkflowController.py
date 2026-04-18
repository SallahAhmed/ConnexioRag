from .BaseController import BaseController
from models.enums.WorkflowNodeEnum import WorkflowNodeEnum
import re

class WorkflowController(BaseController):
    def __init__(self, generation_client, template_parser):
        super().__init__()
        self.generation_client = generation_client
        self.template_parser = template_parser

    async def detect_node(self, query: str) -> WorkflowNodeEnum:
        """
        Detects the workflow node from the user query.
        Uses keywords first, falls back to LLM if needed.
        """
        query_lower = query.lower()
        
        # Keyword mappings (as defined in v2 docs)
        keywords = {
            WorkflowNodeEnum.ONBOARDING: ["where do i start", "new here", "how it works", "start"],
            WorkflowNodeEnum.TEAM_FORMATION: ["find teammate", "need a dev", "looking for", "join team"],
            WorkflowNodeEnum.PHASE_TRANSITION: ["next phase", "done with", "advance", "transition"],
            WorkflowNodeEnum.BLOCKER: ["stuck", "not responding", "error", "help", "problem"],
            WorkflowNodeEnum.MILESTONE_WARNING: ["behind", "overdue", "late", "deadline"],
        }

        for node, triggers in keywords.items():
            if any(trigger in query_lower for trigger in triggers):
                return node

        # Fallback to LLM for classification
        language = await self.detect_language(query)
        self.template_parser.set_language(language)

        system_prompt = self.template_parser.get("workflow", "classification_system_prompt")
        user_prompt = self.template_parser.get("workflow", "classification_user_prompt", {"query": query})

        chat_history = [
            self.generation_client.construct_prompt(prompt=system_prompt, role=self.generation_client.enums.SYSTEM.value)
        ]

        response = self.generation_client.generate_text(prompt=user_prompt, chat_history=chat_history)

        if response:
            try:
                return WorkflowNodeEnum[response.strip().upper()]
            except (KeyError, ValueError):
                pass

        return WorkflowNodeEnum.GENERAL

    async def detect_persona(self, query: str, chat_history: list = None) -> str:
        """
        Detects if the user is a student, early_career, educator, or company.
        Defaults to student for now or pulls from session.
        """
        # Logic to extract persona from context or session
        # For now, we'll keep it simple: defaults to 'student'
        return "student"

    async def detect_language(self, query: str) -> str:
        """
        Detects if the language is English or Arabic.
        """
        # Simple Arabic char detection
        if re.search(r'[\u0600-\u06FF]', query):
            return "ar"
        return "en"
