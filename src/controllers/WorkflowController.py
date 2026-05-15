from .BaseController import BaseController
from models.enums.WorkflowNodeEnum import WorkflowNodeEnum
import re
# pyrefly: ignore [missing-import]
import guidance

# Short queries matching these patterns bypass the fast-path and go to the LLM classifier,
# because they could be trivia, jailbreak attempts, or historical questions.
_SKIP_FAST_PATH = (
    "who is ", "who was ", "who were ", "who's ",
    "من هو ", "من كان ", "من هي ", "من كانت ",
    "system prompt", "your prompt", "your instructions",
    "ignore your", "ignore previous", "disregard your",
    "forget your", "pretend you", "act as if", "bypass your",
    "jailbreak", "تجاهل تعليم", "تجاوز قيود", "تظاهر أنك",
)

class WorkflowController(BaseController):
    def __init__(self, generation_client, template_parser, utility_client=None):
        super().__init__()
        self.generation_client = generation_client
        self.utility_client = utility_client if utility_client else generation_client
        self.template_parser = template_parser

    async def detect_node(self, query: str) -> WorkflowNodeEnum:
        """
        Detects the workflow node from the user query.
        Order: OOS keywords → project keywords → GENERAL keywords → fast path → LLM.
        """
        query_lower = query.lower().strip()

        # 1. OOS KEYWORDS FIRST: Catch off-topic queries immediately before anything else
        OOS_KEYWORDS = [
            "capital of", "who is the president", "who is the current",
            "who won the election", "population of", "located in",
            "mayor of", "prime minister", "king of",
            "tell me a joke", "who won the game", "who won the match",
            "celebrity", "actor", "movie plot", "movie about",
            "singer", "album", "song by", "lyrics",
            # Food / Cooking
            "recipe for", "recipe ", "how do i cook", "how to bake",
            "how to make ", "ingredients for", "cook ", "bake ",
            "how to cook", "how to fry", "how to boil",
            "كيف أطبخ", "وصفة", "مكونات الطبق", "طريقة عمل", "طريقة تحضير",
            # Weather
            "weather in", "temperature in", "forecast for", "weather forecast",
            # History & trivia
            "what happened on", "born on", "died in", "year ",
            # Personal/off-topic
            "wearing", "wear ", "clothes", "outfit", "dress", "shirt", "pants",
            "eat ", "eating", "drink", "drinking", "hungry", "thirsty",
            "my name is", "i am ", "i'm ", "my age", "how old",
            "dream ", "dreams", "sleep", "asleep", "woke up",
            # Jailbreak
            "your system prompt", "show me your prompt", "ignore your instructions",
            "ignore previous instructions", "disregard your instructions",
            "pretend you are not", "pretend you have no", "bypass your rules",
            "override your", "jailbreak", "developer mode", "dan mode",
            # Arabic OOS
            "عاصمة", "الطقس في", "من هو رئيس", "قل لي نكتة", "من فاز",
            "أرني نظام برومبت", "تجاهل تعليماتك", "تجاوز قيودك", "تظاهر أنك لست",
        ]
        if any(kw in query_lower for kw in OOS_KEYWORDS):
            return WorkflowNodeEnum.OUT_OF_SCOPE

        # 2. PROJECT KEYWORDS: Catch project-specific intents
        PROJECT_KEYWORDS = {
            WorkflowNodeEnum.ONBOARDING: [
                "where do i start", "new here", "how it works", "how do i start",
                "how does this", "how does the", "how does your", "how does it",
                "getting started", "first time", "start here", "guide me",
                "بداية", "كيف أبدأ", "جديد هنا", "كيف تعمل",
            ],
            WorkflowNodeEnum.TEAM_FORMATION: [
                "find teammate", "need a dev", "looking for", "join team",
                "find a designer", "need someone", "recruit",
                "ابحث عن", "أحتاج مطور", "فريق",
            ],
            WorkflowNodeEnum.PHASE_TRANSITION: [
                "next phase", "done with", "advance", "transition", "move to",
                "المرحلة التالية", "الانتقال", "الانتهاء من",
            ],
            WorkflowNodeEnum.BLOCKER: [
                "stuck", "not responding", "error", "problem", "help fix",
                "help me fix", "not working", "broken", "crash", "exception",
                "عالق", "مشكلة", "خطأ", "لا يعمل",
            ],
            WorkflowNodeEnum.MILESTONE_WARNING: [
                "my project is behind", "we are behind", "our deadline",
                "we missed our", "my milestone", "our milestone",
                "our project is late", "we're overdue", "we are overdue",
                "مشروعنا متأخر", "نحن متأخرون", "موعدنا النهائي", "أخطأنا الموعد",
            ],
        }
        for node, triggers in PROJECT_KEYWORDS.items():
            if any(trigger in query_lower for trigger in triggers):
                return node

        # 3. GENERAL KEYWORDS: Greetings and identity questions
        GENERAL_KEYWORDS = [
            "hello", "hi", "hey", "good morning", "good afternoon",
            "who are you", "what can you do", "your name",
            "مرحبا", "سلام", "اهلا", "كيف حالك", "من انت", "ماذا تفعل",
        ]
        if any(kw in query_lower for kw in GENERAL_KEYWORDS):
            return WorkflowNodeEnum.GENERAL

        # 4. FAST PATH: Short queries under 50 chars → GENERAL
        # (Unless they match SKIP_FAST_PATH patterns like "who is" or jailbreak attempts)
        if len(query_lower) < 50 and not any(p in query_lower for p in _SKIP_FAST_PATH):
            return WorkflowNodeEnum.GENERAL

        # 5. Fallback to LLM for complex classification
        language = await self.detect_language(query)
        self.template_parser.set_language(language)

        system_prompt = self.template_parser.get("workflow", "classification_system_prompt")
        user_prompt = self.template_parser.get("workflow", "classification_user_prompt", {"query": query[:2000]})

        chat_history = [
            self.generation_client.construct_prompt(
                prompt=system_prompt,
                role=self.generation_client.enums.SYSTEM.value
            )
        ]

        # Use utility client for classification and keep it extremely brief
        response = await self.utility_client.generate_text(
            prompt=user_prompt + "\n\nAnswer ONLY with the single enum name (e.g., GENERAL).", 
            chat_history=chat_history
        )

        if response:
            try:
                return WorkflowNodeEnum[response.strip().upper()]
            except (KeyError, ValueError):
                pass

        return WorkflowNodeEnum.GENERAL

    async def detect_persona(self, query: str, chat_history: list = None) -> str:
        """
        Detects if the user is a student, early_career, educator, or company.
        """
        return "student"

    async def detect_language(self, query: str) -> str:
        """
        Detects if the language is English or Arabic.
        """
        if re.search(r'[\u0600-\u06FF]', query):
            return "ar"
        return "en"

    async def grade_relevance(self, query: str, context: str) -> bool:
        """
        Grades whether the retrieved context is relevant to the query.
        Uses the utility (fast/small) model to avoid adding heavy LLM latency.
        Returns True if relevant, False if a search fallback is needed.
        """
        if not context or "No relevant documents found" in context:
            return False

        language = await self.detect_language(query)
        self.template_parser.set_language(language)

        system_prompt = self.template_parser.get("relevance_grading", "relevance_grader_system_prompt")
        user_prompt = self.template_parser.get("relevance_grading", "relevance_grader_user_prompt", {
            "query": query,
            "document": context[:2000]
        })

        chat_history = [
            self.generation_client.construct_prompt(
                prompt=system_prompt,
                role=self.generation_client.enums.SYSTEM.value
            )
        ]

        try:
            response = await self.utility_client.generate_text(
                prompt=user_prompt, chat_history=chat_history
            )
            grade = response.strip().upper()
            
            # Robust boundary check
            if "IRRELEVANT" in grade or "NO" in grade:
                return False
            if "YES" in grade or "RELEVANT" in grade:
                return True
            return "AMBIGUOUS" in grade
        except Exception as e:
            self.logger.error(f"Guidance/Grading Error: {str(e)}")
            return True # Fallback to true to avoid blocking the user if grading fails
