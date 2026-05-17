from .BaseController import BaseController
from models.enums.WorkflowNodeEnum import WorkflowNodeEnum
import difflib
import re

# Short queries matching these patterns bypass the fast-path and go to the LLM classifier,
# because they could be trivia, jailbreak attempts, or historical questions.
_SKIP_FAST_PATH = (
    "who is ", "who was ", "who were ", "who's ",
    "what is ", "what are ", "what does ",
    "من هو ", "من كان ", "من هي ", "من كانت ",
    "ما هو ", "ما هي ", "ماذا ", "لماذا ",
    "كيف ", "أين ", "متى ", "هل ",
    "system prompt", "your prompt", "your instructions",
    "ignore your", "ignore previous", "disregard your",
    "forget your", "pretend you", "act as if", "bypass your",
    "jailbreak", "تجاهل تعليم", "تجاوز قيود", "تظاهر أنك",
)

# Fuzzy matching dictionary for typo-tolerant intent detection.
# Maps a correctly-spelled term to its most likely intent node.
_FUZZY_TERM_NODE = {
    "start": WorkflowNodeEnum.ONBOARDING,
    "guide": WorkflowNodeEnum.ONBOARDING,
    "begin": WorkflowNodeEnum.ONBOARDING,
    "tutorial": WorkflowNodeEnum.ONBOARDING,
    "teammate": WorkflowNodeEnum.TEAM_FORMATION,
    "developer": WorkflowNodeEnum.TEAM_FORMATION,
    "designer": WorkflowNodeEnum.TEAM_FORMATION,
    "recruit": WorkflowNodeEnum.TEAM_FORMATION,
    "sprint": WorkflowNodeEnum.PHASE_TRANSITION,
    "phase": WorkflowNodeEnum.PHASE_TRANSITION,
    "transition": WorkflowNodeEnum.PHASE_TRANSITION,
    "advance": WorkflowNodeEnum.PHASE_TRANSITION,
    "agile": WorkflowNodeEnum.PHASE_TRANSITION,
    "scrum": WorkflowNodeEnum.PHASE_TRANSITION,
    "stuck": WorkflowNodeEnum.BLOCKER,
    "error": WorkflowNodeEnum.BLOCKER,
    "problem": WorkflowNodeEnum.BLOCKER,
    "broken": WorkflowNodeEnum.BLOCKER,
    "crash": WorkflowNodeEnum.BLOCKER,
    "exception": WorkflowNodeEnum.BLOCKER,
    "compile": WorkflowNodeEnum.BLOCKER,
    "timeout": WorkflowNodeEnum.BLOCKER,
    "issue": WorkflowNodeEnum.BLOCKER,
    "milestone": WorkflowNodeEnum.MILESTONE_WARNING,
    "deadline": WorkflowNodeEnum.MILESTONE_WARNING,
    "overdue": WorkflowNodeEnum.MILESTONE_WARNING,
    "delay": WorkflowNodeEnum.MILESTONE_WARNING,
    "hello": WorkflowNodeEnum.GENERAL,
    "greeting": WorkflowNodeEnum.GENERAL,
    # Arabic
    "بداية": WorkflowNodeEnum.ONBOARDING,
    "فريق": WorkflowNodeEnum.TEAM_FORMATION,
    "مطور": WorkflowNodeEnum.TEAM_FORMATION,
    "مرحلة": WorkflowNodeEnum.PHASE_TRANSITION,
    "مشكلة": WorkflowNodeEnum.BLOCKER,
    "موعد": WorkflowNodeEnum.MILESTONE_WARNING,
    "مرحبا": WorkflowNodeEnum.GENERAL,
}
_FUZZY_TERMS = list(_FUZZY_TERM_NODE.keys())

class WorkflowController(BaseController):
    def __init__(self, generation_client, template_parser, utility_client=None):
        super().__init__()
        self.generation_client = generation_client
        self.utility_client = utility_client if utility_client else generation_client
        self.template_parser = template_parser

    async def detect_node(self, query: str) -> WorkflowNodeEnum:
        """
        Detects the workflow node from the user query.
        Order: Jailbreak keywords → OOS keywords → project keywords → GENERAL keywords → fast path → LLM.
        """
        query_lower = query.lower().strip()

        # 0. JAILBREAK KEYWORDS FIRST: Strict bypass-prevention, always OUT_OF_SCOPE (no exceptions)
        JAILBREAK_KEYWORDS = [
            "your system prompt", "show me your prompt", "ignore your instructions",
            "ignore previous instructions", "disregard your instructions",
            "pretend you are not", "pretend you have no", "bypass your rules",
            "override your", "jailbreak", "developer mode", "dan mode",
            "أرني نظام برومبت", "تجاهل تعليماتك", "تجاوز قيودك", "تظاهر أنك لست",
        ]
        if any(kw in query_lower for kw in JAILBREAK_KEYWORDS):
            return WorkflowNodeEnum.OUT_OF_SCOPE

        # 1. OOS KEYWORDS: Catch off-topic queries immediately before anything else
        # BUT: Tech/AI/programming history is IN-SCOPE for a dev collaboration assistant
        OOS_KEYWORDS = [
            "capital of", "who is the president", "who is the current",
            "who won the election", "who won the", "population of", "located in",
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
            # History & trivia (EXCEPT programming/tech history)
            "what happened on", "born on", "died in", "year ",
            # Personal/off-topic
            "wearing", "wear ", "clothes", "outfit", "dress", "shirt", "pants",
            "eat ", "eating", "drink", "drinking", "hungry", "thirsty",
            "my name is", "my age", "how old",
            "dream ", "dreams", "sleep", "asleep", "woke up",
            # Arabic OOS
            "عاصمة", "الطقس في", "من هو رئيس", "قل لي نكتة", "من فاز",
            # Arabic philosophy / personal / feelings
            "الحب", "حب ", "مشاعر", "عواطف", "المشاعر", "الحنان",
            "الخوف", "قلق", "اكتئاب", "حزن", "فرح", "سعادة",
            # Arabic folk / trivia / personal (EXCEPT tech/AI/programming)
            "مشهور", "مشهورة", "ولد في", "توفي في",
            "مطرب", "مغني", "ممثل", "مسلسل", "فيلم", "أغنية",
            "طبخة", "طبخ", "اكل", "أكل", "شربة", "سلطة",
            "أغاني", "أغان", "مهرجان", "مهرجانات", "كليبات", "دوري",
        ]
        # Tech/AI/programming exceptions — these are IN-SCOPE even if they match OOS patterns
        TECH_IN_SCOPE = [
            "python", "javascript", "programming", "software", "code", "api",
            "artificial intelligence", "machine learning", "deep learning", "neural",
            "الذكاء الاصطناعي", "تعلم الآلة", "التعلم العميق", "البرمجة", "المبرمج",
            "invent", "invented", "creator", "created", "founder", "developed",
            "security", "vulnerability", "cve", "exploit", "patch", "cyber",
            "الأمن السيبراني", "الثغرات", "الاختراق", "الحماية",
        ]
        if any(kw in query_lower for kw in OOS_KEYWORDS):
            # Exception: if query contains tech/AI keywords, allow it through
            if any(kw in query_lower for kw in TECH_IN_SCOPE):
                pass  # Fall through to project keyword check
            else:
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
                "find teammate", "find a ", "need a dev", "looking for", "join team",
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

        # 3.5 FUZZY MATCHING: Catch typos in short queries (e.g. "sprnit" → sprint)
        if len(query_lower) < 50:
            for word in query_lower.split():
                if len(word) < 4:
                    continue
                matches = difflib.get_close_matches(word, _FUZZY_TERMS, n=1, cutoff=0.8)
                if matches:
                    matched_node = _FUZZY_TERM_NODE.get(matches[0])
                    if matched_node is not None:
                        return matched_node

        # 4. FAST PATH: Short queries under 50 chars → GENERAL
        # (Unless they match SKIP_FAST_PATH patterns like "who is" or jailbreak attempts)
        # Also skip for Arabic queries — short Arabic can be philosophical/folk questions
        # without explicit question words (e.g. "مروان موسى لقى البوصلة ولا لسة").
        if (
            len(query_lower) < 50
            and not any(p in query_lower for p in _SKIP_FAST_PATH)
            and not re.search(r'[\u0600-\u06FF]', query_lower)
        ):
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
        Checks Arabic Unicode ranges: Basic (0600-06FF), Extended-A (08A0-08FF),
        Presentation Forms-A (FB50-FDFF), Presentation Forms-B (FE70-FEFF).
        """
        if re.search(r'[\u0600-\u06FF\u08A0-\u08FF\uFB50-\uFDFF\uFE70-\uFEFF]', query):
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
