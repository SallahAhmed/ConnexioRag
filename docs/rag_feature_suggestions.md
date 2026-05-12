# Connexio RAG Model Features & Suggestions

Based on the `README.md` and the vision outlined in `Idea.txt`, here is a comprehensive breakdown of the core features currently planned for v2, followed by advanced feature suggestions that fully leverage Connexio's unique cross-disciplinary, startup-style ecosystem.

## Core V2 Features (From README)

These are the foundational mechanics driving the RAG agent's intelligence in v2:

1.  **Workflow Routing Nodes**: The RAG agent routes conversations dynamically into 5 distinct nodes: `ONBOARDING`, `TEAM_FORMATION`, `PHASE_TRANSITION`, `BLOCKER`, and `MILESTONE_WARNING`. Each node triggers specific retrieval strategies and system prompts.
2.  **Intelligent Matching Algorithm**: A weighted 6-factor scoring engine (including skill complementarity, availability, phase experience, and a 20% weight on rating history) to recommend the best teammates.
3.  **Persona Handling**: The agent adjusts its tone, depth, and focus depending on whether the user is a Student or an Early-career professional.
4.  **Bilingual Support**: Auto-detects and responds in English or Arabic seamlessly.
5.  **Phase Transition Gatekeeper**: The model actively validates the deliverable checklist before allowing a team to advance to the next lifecycle phase.
6.  **Team Gap Check**: Proactively warns teams if they are missing crucial technical or non-technical roles.
7.  **Adaptive Session Tracking**: Persists the user's persona, language, and current project phase across conversation turns for a fluid experience.
8.  **Freemium Logic Integration**: Naturally mentions premium limits and features without breaking character.

---

## Advanced Feature Suggestions (Based on Idea.txt)

To fully realize the platform's vision of creating "professional evidence of real experience," here are suggested expansions:

### 1. Project Portfolio & Resume Auto-Generator (The "Career Builder")
Since Connexio's goal is to produce "professional evidence of real experience," the RAG model can act as a personal resume writer. 
*   **How it works**: At the end of a project (Retrospective phase), a user asks, *"Summarize my contributions for my portfolio."*
*   **Data Sources**: Text-to-SQL fetches the exact tasks they completed. Vector DB pulls their specific deliverables or GitHub commit summaries.
*   **Output**: A professionally formatted portfolio entry highlighting their cross-disciplinary collaboration and specific technical/non-technical achievements.

### 2. Automated Sprint Retrospective Facilitator
Since Connexio enforces a structured "startup-style lifecycle," the RAG model can actively facilitate the "Retrospective" phase.
*   **How it works**: Instead of just warning about missed deadlines, the model analyzes the completed phase. *"I see the MVP frontend was delayed by 3 days due to 5 blocked tasks. What went well, and what could we improve?"*
*   **Data Sources**: Text-to-SQL checks task velocities and completion rates. Vector DB reviews team chat/blocker logs.

### 3. Cross-Disciplinary "Jargon Buster" (The "Translator")
Connexio teams mix developers, designers, and marketers. Communication gaps are inevitable.
*   **How it works**: A marketer asks the bot, *"What does the backend team mean by 'migrating the CI/CD pipeline'?"* The RAG agent simplifies the concept using the exact context of their specific project.
*   **Data Sources**: Wikipedia Tool for general definitions, blended with Project Vector DB to contextualize how it affects the specific project.

### 4. Supervisor & Educator Insights Assistant
Since the platform includes "Institution and supervisor integration," educators need a way to monitor dozens of teams without micromanaging.
*   **How it works**: A supervisor asks, *"Which student teams are currently at high risk of failing this sprint?"*
*   **Data Sources**: Text-to-SQL aggregates data on missed tasks vs. total tasks across all teams. The model outputs a concise risk report highlighting the specific teams needing intervention.

### 5. Gamification & Skill Growth Coach
Connexio features a gamification system rewarding skill growth. The RAG agent could act as a proactive career mentor.
*   **How it works**: *"You've been doing great with React tasks. To level up your profile and increase your match score for senior teams, I recommend picking up a 'Database Design' task. Team Alpha has an unassigned one right now."*
*   **Data Sources**: SQL checks the user's current gamification points and skill gaps. SQL also searches for open tasks in the platform that match the missing skills.

### 6. Intelligent Task Architect & Resolution Planner (The "Solver")
This feature addresses the need for help with complicated, multi-step tasks that require both external research and internal project context.
*   **How it works**: A user presents a complex problem (e.g., *"I'm stuck on how to implement the OAuth login flow for our mobile app"*). The agent doesn't just give a snippet; it:
    1.  **Searches External Knowledge**: Uses the Wikipedia/Web tools to find the latest best practices.
    2.  **Analyzes Project Context**: Checks existing code/docs in the Vector DB to see what's already built.
    3.  **Organizes the Solution**: Generates a structured, step-by-step execution plan (checklist) that the user can follow.
*   **Data Sources**: Wikipedia Tool + Vector DB Search + SQL (to check current task status and dependencies).

---

## Open Questions / Missing Information

To help refine these ideas, I have a few questions about the platform's architecture:

1.  **Chat Integration**: Will the RAG model have access to read the real-time team chat data (to assess sentiment, blockers, or activity levels)? 
2.  **GitHub Access**: How deep is the GitHub integration? Will the RAG model have a "GitHub Tool" to read Pull Requests, Commit messages, or issue comments directly?
3.  **Gamification Authority**: For the gamification system, should the RAG model only *read* user points to give advice, or will it have the ability to explicitly act as a judge and *award* points for good collaboration?
4.  **Action Execution**: Currently, the RAG model retrieves data and answers questions. Should the RAG model be able to *execute* actions on behalf of the user (e.g., actually assigning a task, or creating a milestone via an API)?
