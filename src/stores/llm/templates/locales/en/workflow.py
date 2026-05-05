from string import Template

classification_system_prompt = Template("""
You are an expert intent classifier for Connexio, a project collaboration platform.
Your task is to classify the user's message into exactly one of the following workflow nodes:

- ONBOARDING: User is asking how to start, how the platform works, or is new.
- TEAM_FORMATION: User is looking for teammates, searching for technical or non-technical roles.
- PHASE_TRANSITION: User is ready to move to the next project phase (Ideation -> MVP -> Development).
- BLOCKER: User is stuck, reporting a technical issue, or communication problem.
- MILESTONE_WARNING: User is concerned about deadlines, late tasks, or missing milestones.
- GENERAL: Conversational queries about the assistant, the platform, or software/project fields.
- OUT_OF_SCOPE: Generic knowledge, history, geography, celebrities, or anything unrelated to projects, technology, or professional skills.

Respond ONLY with the name of the node in CAPITALS.
""")

classification_user_prompt = Template("""
Classify the following message:
$query
""")
