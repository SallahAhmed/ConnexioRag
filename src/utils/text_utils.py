"""
Shared text-processing utilities used across controllers and routes.

Centralises Arabic detection, greeting recognition, and other helpers
that were previously duplicated in NLPController, WorkflowController,
and route handlers.
"""
import re
from typing import List, Tuple

# ── Arabic detection ──────────────────────────────────────────────

# Full Arabic Unicode coverage: Basic, Extended-A, Presentation Forms A & B.
_ARABIC_RE = re.compile(r'[\u0600-\u06FF\u08A0-\u08FF\uFB50-\uFDFF\uFE70-\uFEFF]')


def contains_arabic(text: str) -> bool:
    """Return True if *text* contains any Arabic-script character."""
    return bool(_ARABIC_RE.search(text or ""))


def detect_language(text: str) -> str:
    """Return ``'ar'`` if *text* contains Arabic, otherwise ``'en'``."""
    return "ar" if contains_arabic(text) else "en"


# ── Greetings ─────────────────────────────────────────────────────

GREETINGS_EN = frozenset({
    "hello", "hi", "hey", "hi there", "hello there",
    "good morning", "good afternoon", "good evening", "good day", "good night",
    "whats up", "what's up", "sup", "howdy", "greetings", "yo", "morning",
    "how are you", "how are you doing", "how's it going", "how are things",
})

GREETINGS_AR = frozenset({
    "مرحبا", "اهلا", "السلام عليكم", "سلام", "أهلاً", "مرحباً",
    "صباح الخير", "مساء الخير", "صباح النور", "مساء النور",
    "كيف حالك", "كيف الحال", "ازيك", "أزيك",
})

GREETING_RESPONSES = {
    "en": "Hello! How can I help you with your project today?",
    "ar": "مرحباً! كيف يمكنني مساعدتك في مشروعك اليوم؟",
}


def is_greeting(query: str) -> bool:
    """Return True if *query* is a simple greeting (EN or AR)."""
    clean = query.strip().lower().rstrip("?!.,;:")
    greeting_set = GREETINGS_AR if contains_arabic(query) else GREETINGS_EN
    return clean in greeting_set


# ── Clear-history commands ────────────────────────────────────────

CLEAR_COMMANDS = [
    "clear history", "forget everything", "new topic",
    "نظف السجل", "نسيان السجل", "موضوع جديد",
]


def is_clear_history(query: str) -> bool:
    """Return True if *query* requests a history clear."""
    lower = query.lower()
    return any(cmd in lower for cmd in CLEAR_COMMANDS)


# ── Out-of-scope response ────────────────────────────────────────

OOS_RESPONSES = {
    "en": (
        "I specialize in project collaboration and professional skills. "
        "Can I help you with something related to your project?"
    ),
    "ar": (
        "أنا متخصص في التعاون في المشاريع والمهارات المهنية. "
        "هل يمكنني مساعدتك في شيء متعلق بمشروعك؟"
    ),
}


def get_oos_response(language: str) -> str:
    """Return the canned out-of-scope response for *language*."""
    return OOS_RESPONSES.get(language, OOS_RESPONSES["en"])


# ── Technology-list parsing ───────────────────────────────────────

def parse_tech_list(raw) -> List[str]:
    """Normalise a technology value into a flat list of strings.

    Handles:
      - comma-separated string  (``"Python, React, Docker"``)
      - JSON list               (``["Python", "React"]``)
      - ``None`` / empty        (returns ``[]``)
    """
    if not raw:
        return []
    if isinstance(raw, str):
        return [t.strip() for t in raw.split(",") if t.strip()]
    if isinstance(raw, list):
        return [str(t).strip() for t in raw if str(t).strip()]
    return []


# ── RRF merge ─────────────────────────────────────────────────────

def rrf_merge(
    ranked_lists: List[List],
    text_fn=None,
    k: int = 60,
    limit: int = 10,
) -> Tuple[list, dict, dict]:
    """Reciprocal Rank Fusion across multiple ranked lists.

    Parameters
    ----------
    ranked_lists : list of list
        Each inner list is an ordered sequence of document objects.
    text_fn : callable or None
        Extracts a hashable identity from a doc (default: ``doc.text``).
    k : int
        RRF constant (default 60).
    limit : int
        Max results to return.

    Returns
    -------
    sorted_ids : list[str]
        Top-*limit* document IDs sorted by RRF score.
    doc_map : dict[str, object]
        Maps document IDs to objects.
    scores : dict[str, float]
        Maps document IDs to their RRF scores.
    """
    if text_fn is None:
        text_fn = lambda doc: doc.text  # noqa: E731

    scores: dict = {}
    doc_map: dict = {}

    for results in ranked_lists:
        if not results:
            continue
        for rank, doc in enumerate(results):
            doc_id = text_fn(doc)
            doc_map[doc_id] = doc
            scores[doc_id] = scores.get(doc_id, 0) + (1.0 / (k + rank + 1))

    sorted_ids = sorted(scores.keys(), key=lambda x: scores[x], reverse=True)[:limit]
    return sorted_ids, doc_map, scores
