1. Research & External Knowledge Tools
   wikipedia / WikipediaQueryRun:
   Purpose: Allows the agent to look up general facts, definitions, and concepts.
   Use Case: Powering the "Jargon Buster" (explaining technical terms to non-technical team members).
   DuckDuckGo-Search:
   Purpose: Provides safe, live web searching without needing an API key for every search.
   Use Case: Finding the latest libraries or documentation for the "Solver" feature.
2. Structured Data Tools (Text-to-SQL)
   LangChain SQLDatabase:
   Purpose: Connects the LLM directly to your PostgreSQL database. It "teaches" the model your schema (projects, tasks, users).
   Use Case: Answering questions like "How many tasks are overdue in my project?" or "Who has the highest skill match for a Designer role?"
   SQLAlchemy:
   Purpose: The underlying engine that handles the actual database connection and query execution.
3. Workflow & Agent Logic
   LangChain Agents:
   Purpose: The "brain" that decides which tool to use. If you ask a project question, it picks the SQL Tool; if you ask a general fact, it picks the Wikipedia Tool.
   LangGraph (Highly Recommended for v2):
   Purpose: Handles complex "loops" and states (like your Workflow Nodes).
   Use Case: Managing the transition between project phases (Ideation -> MVP -> Development) based on valid tool outputs.
4. Integration & Career Tools
   PyGithub:
   Purpose: Connects to the GitHub API.
   Use Case: The "Career Builder" feature. The agent can read a user’s commit history and repository metadata to generate a professional portfolio entry automatically.
   PyMuPDF / Unstructured:
   Purpose: Deep parsing of PDF/Docx files.
   Use Case: Uploading and analyzing complex project requirement documents to the Vector DB.
