"""Fix the two _prepare_chat_context calls to pass model_tier."""
import re

path = r"C:\Users\salla\Connexios\src\controllers\NLPController.py"
with open(path, "r", encoding="utf-8") as f:
    content = f.read()

# The old and new code blocks
old_call = (
    '            await self._prepare_chat_context(\n'
    '                user_id, project_id, query, persona, session_id, limit\n'
    '            )'
)
new_call = (
    '            await self._prepare_chat_context(\n'
    '                user_id, project_id, query, persona, session_id, limit, model_tier\n'
    '            )'
)

count = content.count(old_call)
print(f"Found {count} occurrences of the old call")
content = content.replace(old_call, new_call)
print(f"Replaced, now {content.count(new_call)} occurrences")

# Also update answer_agent_chat_stream signature
old_sig = (
    '    async def answer_agent_chat_stream(\n'
    '        self,\n'
    '        user_id: int,\n'
    '        project_id: Optional[int],\n'
    '        query: str,\n'
    '        persona: str = "student",\n'
    '        session_id: Optional[int] = None,\n'
    '        limit: int = 5,\n'
    '    ):'
)
new_sig = (
    '    async def answer_agent_chat_stream(\n'
    '        self,\n'
    '        user_id: int,\n'
    '        project_id: Optional[int],\n'
    '        query: str,\n'
    '        persona: str = "student",\n'
    '        session_id: Optional[int] = None,\n'
    '        limit: int = 5,\n'
    '        model_tier: str = "auto",\n'
    '    ):'
)
if old_sig in content:
    content = content.replace(old_sig, new_sig)
    print("Updated stream signature")
else:
    print("Stream signature may already be updated")

with open(path, "w", encoding="utf-8") as f:
    f.write(content)
print("Done")
