"""
ToolManager — Multi-source retrieval tools for the Connexios RAG agent.

INTEGRATION NOTE:
  The RAG does NOT connect to the main Connexio backend database directly.
  All live project/user/task data is fetched via REST calls through
  BackendApiClient. This follows the agreed microservices architecture.

  Tools that previously used hard-coded SQL against non-existent tables
  (technology, user_technology, project_technology) have been replaced with
  REST-based equivalents using the main backend's public API.
"""
import asyncio
import json
import logging
import warnings
from typing import Optional

import httpx
# pyrefly: ignore [missing-import]
from langchain_community.tools import WikipediaQueryRun
# pyrefly: ignore [missing-import]
from langchain_community.utilities import (
    SerpAPIWrapper,
    SQLDatabase,
    WikipediaAPIWrapper,
)


# Register pgvector's custom 'vector' type with SQLAlchemy so LangChain
# doesn't emit SAWarning when reflecting the database schema.
try:
    from sqlalchemy.dialects.postgresql import dialect as pg_dialect
    from sqlalchemy.types import UserDefinedType

    class VECTOR(UserDefinedType):
        def __init__(self, *args, **kwargs):
            pass
        def get_col_spec(self, **kw):
            return "vector"

    pg_dialect.ischema_names = getattr(pg_dialect, "ischema_names", {})
    pg_dialect.ischema_names["vector"] = VECTOR
except Exception:
    pass


class ToolManager:
    def __init__(
        self,
        db_engine_url: str,
        generation_client,
        vectordb_client,
        embedding_client,
        template_parser,
        serpapi_api_key: str = None,
        github_token: str = None,
        stackoverflow_api_key: str = None,
        reranker=None,
        backend_client=None,   # BackendApiClient — REST calls to Node.js backend
        masarx_client=None,    # MasarxApiClient — direct reads from shared PostgreSQL
    ):
        self.db_engine_url = db_engine_url
        self.generation_client = generation_client
        self.vectordb_client = vectordb_client
        self.embedding_client = embedding_client
        self.template_parser = template_parser
        self.reranker = reranker
        self.backend_client = backend_client
        self.masarx_client = masarx_client
        self.stackoverflow_api_key = stackoverflow_api_key
        self.logger = logging.getLogger(__name__)

        # SQL tool (RAG's OWN PostgreSQL only — for Text-to-SQL on RAG tables)
        sync_url = db_engine_url.replace("+asyncpg", "")
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            self.db = SQLDatabase.from_uri(sync_url)

        # Wikipedia
        api_wrapper = WikipediaAPIWrapper(top_k_results=5, doc_content_chars_max=4000)
        self.wiki_tool = WikipediaQueryRun(api_wrapper=api_wrapper)

        # Google Search (SerpApi)
        self.serp_tool = SerpAPIWrapper(serpapi_api_key=serpapi_api_key) if serpapi_api_key else None

        # GitHub
        self.github_token = github_token

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_collection_name(self, project_id) -> str:
        """Single source of truth for vector collection naming."""
        return f"collection_{self.vectordb_client.default_vector_size}_{project_id}".strip()

    # ------------------------------------------------------------------
    # SQL Tool (RAG's own DB only)
    # ------------------------------------------------------------------

    async def execute_sql_query(self, query_text: str) -> str:
        """
        Translate natural language to SQL and execute against the RAG's own
        PostgreSQL database. This accesses only RAG-internal tables
        (projects, chunks, assets) — NOT the main backend's database.

        Safety: generated SQL is validated to ensure it is a SELECT-only query.
        Any DDL/DML keywords (INSERT, UPDATE, DELETE, DROP, ALTER, CREATE,
        TRUNCATE, GRANT, REVOKE, EXEC, EXECUTE) cause immediate rejection.
        """
        DANGEROUS_KEYWORDS = [
            "INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "CREATE",
            "TRUNCATE", "GRANT", "REVOKE", "EXEC", "EXECUTE",
            "COPY", "\\i", ";", "--", "/*", "*/",
        ]

        try:
            schema = await asyncio.to_thread(self.db.get_table_info)
            if len(schema) > 5000:
                schema = schema[:5000] + "\n[...schema truncated...]"

            prompt = (
                f"Given the following SQL schema:\n{schema}\n\n"
                f"Generate a single PostgreSQL SELECT query to answer: {query_text}\n"
                "Return ONLY the SQL code. No explanations, no markdown."
            )

            sql_query = await self.generation_client.generate_text(prompt=prompt)
            if not sql_query:
                return "Could not generate SQL query."

            sql_query = sql_query.strip().replace("```sql", "").replace("```", "").strip()

            # Safety validation: reject any query containing dangerous keywords
            sql_upper = sql_query.upper()
            for keyword in DANGEROUS_KEYWORDS:
                if keyword in sql_upper:
                    self.logger.warning(
                        "SQL query rejected — contains forbidden keyword: %s", keyword
                    )
                    return "Query rejected: only read-only SELECT queries are allowed."

            # Ensure it starts with SELECT
            if not sql_upper.startswith("SELECT"):
                self.logger.warning("SQL query rejected — does not start with SELECT")
                return "Query rejected: only SELECT queries are allowed."

            result = await asyncio.to_thread(self.db.run, sql_query)
            result = str(result)
            if len(result) > 1500:
                result = result[:1500] + "\n[...result truncated...]"
            return result
        except Exception as e:
            self.logger.error(f"SQL Tool Error: {str(e)}")
            return f"Error executing database query: {str(e)}"

    # ------------------------------------------------------------------
    # Wikipedia & Web Search Tools
    # ------------------------------------------------------------------

    async def search_wiki(self, query: str, lang: str = "en") -> str:
        try:
            self.wiki_tool.api_wrapper.lang = lang
            res = await asyncio.wait_for(
                asyncio.to_thread(self.wiki_tool.run, query), timeout=5.0
            )

            if (not res or "No relevant information" in res or "Page not found" in res) and lang != "en":
                self.logger.info(f"Wiki search failed for {lang}, retrying in English...")
                self.wiki_tool.api_wrapper.lang = "en"
                res = await asyncio.to_thread(self.wiki_tool.run, query)

            if len(res) > 2000:
                res = res[:2000] + "\n[...wiki truncated...]"
            return res
        except Exception as e:
            if "Expecting value" in str(e):
                return "No relevant information found on Wikipedia for this specific term."
            self.logger.error(f"Wiki Tool Error: {str(e)}")
            return "Unable to perform Wikipedia search at this time."

    async def search_google(self, query: str) -> str:
        if not self.serp_tool:
            return "Google Search is not configured (Missing SERPAPI_API_KEY)."
        try:
            res = await asyncio.wait_for(
                asyncio.to_thread(self.serp_tool.run, query), timeout=5.0
            )
            if len(res) > 2000:
                res = res[:2000] + "\n[...google truncated...]"
            return res
        except Exception as e:
            self.logger.error(f"Google Search Tool Error: {str(e)}")
            return "Unable to perform Google Search at this time."

    def get_global_collection_name(self):
        return self._get_collection_name(0)

    # ------------------------------------------------------------------
    # Vector Knowledge Base Tool
    # ------------------------------------------------------------------

    async def search_collection(self, collection_name: str, query: str, limit: int = 5):
        """Search a specific vector collection by name."""
        try:
            vectors = await self.embedding_client.embed_text(text=query, document_type="query")
            if not vectors or len(vectors) == 0:
                return None
            query_vector = vectors[0]
            try:
                results = await self.vectordb_client.hybrid_search(
                    collection_name=collection_name, query=query, vector=query_vector, limit=limit,
                )
            except Exception:
                results = await self.vectordb_client.search_by_vector(
                    collection_name=collection_name, vector=query_vector, limit=limit,
                )
            return results
        except Exception as e:
            self.logger.error(f"search_collection error for {collection_name}: {e}")
            return None

    async def search_knowledge_base(self, project_id, query: str, limit: int = 5):
        """Hybrid search over project KB + global KB, merged via RRF.
        If project_id=0, searches only the global KB to avoid double-searching the same collection."""
        try:
            vectors = await self.embedding_client.embed_text(text=query, document_type="query")
            if not vectors or len(vectors) == 0:
                return "Could not embed query for knowledge base search."

            query_vector = vectors[0]
            k = 60
            scores = {}
            doc_map = {}

            def add_results(results, prefix=""):
                if not results:
                    return
                for rank, doc in enumerate(results):
                    doc_id = prefix + doc.text
                    doc_map[doc_id] = doc
                    scores[doc_id] = scores.get(doc_id, 0) + (1.0 / (k + rank + 1))

            # Search project KB
            project_collection = self._get_collection_name(project_id)
            try:
                project_results = await self.vectordb_client.hybrid_search(
                    collection_name=project_collection, query=query, vector=query_vector, limit=limit * 2,
                )
            except Exception:
                project_results = await self.vectordb_client.search_by_vector(
                    collection_name=project_collection, vector=query_vector, limit=limit * 2,
                )
            add_results(project_results, "proj_")

            # Search global KB
            try:
                global_results = await self.vectordb_client.hybrid_search(
                    collection_name=self.get_global_collection_name(), query=query, vector=query_vector, limit=limit * 2,
                )
            except Exception:
                global_results = await self.vectordb_client.search_by_vector(
                    collection_name=self.get_global_collection_name(), vector=query_vector, limit=limit * 2,
                )
            add_results(global_results, "global_")

            if not scores:
                return "No relevant documents found in the knowledge base."

            sorted_doc_ids = sorted(scores.keys(), key=lambda x: scores[x], reverse=True)[:limit]

            if self.reranker and sorted_doc_ids:
                docs_to_rerank = [doc_map[did] for did in sorted_doc_ids]
                reranked = await self.reranker.rerank(query=query, documents=docs_to_rerank, top_k=limit)
                final = reranked
            else:
                final = [doc_map[did] for did in sorted_doc_ids]

            formatted = "\n\n".join(
                [f"[Doc {i+1}]: {res.text[:1500]}" for i, res in enumerate(final)]
            )
            if len(formatted) > 3000:
                formatted = formatted[:3000] + "\n[...kb truncated...]"
            return formatted

        except Exception as e:
            self.logger.error(f"Knowledge Base Tool Error: {str(e)}")
            return f"Error searching knowledge base: {str(e)}"

    async def search_knowledge_base_raw(self, project_id, query: str, limit: int = 5):
        """Same retrieval as search_knowledge_base but returns list of raw doc objects.
        Enables batch relevance grading. Returns [] on failure or empty KB."""
        try:
            vectors = await self.embedding_client.embed_text(text=query, document_type="query")
            if not vectors or len(vectors) == 0:
                return []

            query_vector = vectors[0]
            k = 60
            scores = {}
            doc_map = {}

            def add_results(results, prefix=""):
                if not results:
                    return
                for rank, doc in enumerate(results):
                    doc_id = prefix + doc.text
                    doc_map[doc_id] = doc
                    scores[doc_id] = scores.get(doc_id, 0) + (1.0 / (k + rank + 1))

            project_collection = self._get_collection_name(project_id)
            try:
                project_results = await self.vectordb_client.hybrid_search(
                    collection_name=project_collection, query=query, vector=query_vector, limit=limit * 2,
                )
            except Exception:
                project_results = await self.vectordb_client.search_by_vector(
                    collection_name=project_collection, vector=query_vector, limit=limit * 2,
                )
            add_results(project_results, "proj_")

            try:
                global_results = await self.vectordb_client.hybrid_search(
                    collection_name=self.get_global_collection_name(), query=query, vector=query_vector, limit=limit * 2,
                )
            except Exception:
                global_results = await self.vectordb_client.search_by_vector(
                    collection_name=self.get_global_collection_name(), vector=query_vector, limit=limit * 2,
                )
            add_results(global_results, "global_")

            if not scores:
                return []

            sorted_doc_ids = sorted(scores.keys(), key=lambda x: scores[x], reverse=True)[:limit]

            if self.reranker and sorted_doc_ids:
                docs_to_rerank = [doc_map[did] for did in sorted_doc_ids]
                reranked = await self.reranker.rerank(query=query, documents=docs_to_rerank, top_k=limit)
                return reranked
            else:
                return [doc_map[did] for did in sorted_doc_ids]

        except Exception as e:
            self.logger.error(f"Knowledge Base Raw Tool Error: {str(e)}")
            return []

    # ------------------------------------------------------------------
    # Main Backend REST Tools (replacing the broken SQL-based methods)
    # ------------------------------------------------------------------

    async def get_matching_rationale(self, user_id: int, project_id: int) -> str:
        """
        Explains why a user was matched to a project using the 6-factor algorithm.

        Data is fetched from the main Connexio backend via REST — the RAG's own
        database has no user skill or project technology tables.

        Weights: Skills 35% | Availability 25% | Rating 20% | Experience 12%
                 Goals 5%   | Domain Alignment 3%
        """
        if not self.backend_client:
            return (
                "Matching rationale is unavailable: the backend data client is not "
                "configured in this context."
            )

        try:
            # Fetch user and project in parallel
            user_data, project_data = await asyncio.gather(
                self.backend_client.get_user(user_id),
                self.backend_client.get_project(project_id),
            )

            if not user_data:
                return f"Could not retrieve profile for user {user_id} from the backend."
            if not project_data:
                return f"Could not retrieve details for project {project_id} from the backend."

            # Parse skills — stored as comma-separated string in `technologies`
            raw_techs = user_data.get("technologies") or ""
            user_skills = [t.strip() for t in raw_techs.split(",") if t.strip()]

            # skills JSON array (more granular) — merge both sources
            skill_list = user_data.get("skills") or []
            if isinstance(skill_list, list):
                user_skills = list(set(user_skills + [str(s) for s in skill_list]))

            project_techs = project_data.get("technologyUsed") or []
            if isinstance(project_techs, str):
                project_techs = [t.strip() for t in project_techs.split(",") if t.strip()]

            matched_techs = [t for t in user_skills if t in project_techs]

            prompt = (
                f"Explain to the user (name: {user_data.get('FullName', 'User')}, "
                f"UID: {user_id}) why they were matched to the project "
                f"'{project_data.get('PName', f'Project {project_id}')}' "
                f"(PID: {project_id}).\n\n"
                f"User's skills: {', '.join(user_skills) or 'not specified'}\n"
                f"Project requires: {', '.join(project_techs) or 'not specified'}\n"
                f"Matched skills: {', '.join(matched_techs) or 'none directly matched'}\n"
                f"User rating: {user_data.get('rate', 'N/A')}\n"
                f"Experience level: {user_data.get('experience_level', 'N/A')}\n"
                f"Years of experience: {user_data.get('years_of_experience', 'N/A')}\n\n"
                "Use the 6-factor matching algorithm weights: "
                "35% Skills, 25% Availability, 20% Rating, 12% Phase Experience, "
                "5% Learning Goals, 3% Domain Alignment.\n\n"
                "Write a warm, personalized, and encouraging explanation (3-5 sentences)."
            )

            return await self.generation_client.generate_text(prompt=prompt)

        except Exception as e:
            self.logger.error(f"Matching Rationale Error: {str(e)}")
            return "Unable to calculate matching rationale at this time."

    async def get_team_gaps(self, project_id: int) -> str:
        """
        Identifies which technical skills the project team is missing.

        Compares what the project requires (`technologyUsed`) against what
        the current team members collectively have (`technologies`).
        All data is fetched from the main Connexio backend via REST.
        """
        if not self.backend_client:
            return (
                "Team gap analysis is unavailable: the backend data client is not "
                "configured in this context."
            )

        try:
            project_data, members = await asyncio.gather(
                self.backend_client.get_project(project_id),
                self.backend_client.get_project_members(project_id),
            )

            if not project_data:
                return f"Could not retrieve project {project_id} details."

            required_techs = project_data.get("technologyUsed") or []
            if isinstance(required_techs, str):
                required_techs = [t.strip() for t in required_techs.split(",") if t.strip()]

            if not required_techs:
                return (
                    f"Project '{project_data.get('PName', project_id)}' has no "
                    "technology requirements listed yet."
                )

            if not members:
                return (
                    f"No members found for project {project_id}. "
                    f"Required skills: {', '.join(required_techs)}."
                )

            # Aggregate all skills across the team
            team_skills: set[str] = set()
            for member in members:
                raw = member.get("technologies") or ""
                for t in raw.split(","):
                    t = t.strip()
                    if t:
                        team_skills.add(t)

            missing = [t for t in required_techs if t not in team_skills]
            covered = [t for t in required_techs if t in team_skills]

            project_name = project_data.get("PName", f"Project {project_id}")
            member_count = len(members)

            if not missing:
                return (
                    f"Great news! '{project_name}' ({member_count} members) covers "
                    f"all required skills: {', '.join(covered)}."
                )

            return (
                f"'{project_name}' ({member_count} members) is missing expertise in: "
                f"**{', '.join(missing)}**. "
                f"Skills already covered: {', '.join(covered) or 'none'}. "
                "Recommendation: recruit team members with the missing skills before "
                "the next project phase."
            )

        except Exception as e:
            self.logger.error(f"Team Gap Error: {str(e)}")
            return "Error assessing team gaps."

    async def get_masarx_tasks(self, project_id: int) -> str:
        """
        Fetches AI-generated tasks from MasarX's PostgreSQL task table via the
        shared Neon DB. These are sprint tasks created by MasarX's create_tasks
        subgraph and are distinct from the user-created tasks in MySQL.
        Returns an empty string if no client or no tasks found.
        """
        if not self.masarx_client:
            return ""
        try:
            tasks = await self.masarx_client.get_tasks(project_id)
            if not tasks:
                return ""
            lines = [f"AI-planned tasks for project {project_id}:"]
            for t in tasks[:10]:
                status_icon = "✅" if t["status"] == "DONE" else ("🔄" if t["status"] == "IN_PROGRESS" else "⏳")
                assignee = t.get("assignee_name") or "unassigned"
                lines.append(f"  {status_icon} [{t['status']}] {t['title']} — {assignee}")
            return "\n".join(lines)
        except Exception as e:
            self.logger.error(f"get_masarx_tasks error: {e}")
            return ""

    async def get_project_context_summary(self, project_id: int) -> str:
        """
        Returns a structured text summary of the project's current state
        (details + tasks + member count) for use in RAG prompts.

        This enriches the agent's context with live backend data without
        requiring a direct database connection.
        """
        if not self.backend_client:
            return ""

        try:
            project_raw, members_raw, tasks_raw = await asyncio.gather(
                self.backend_client.get_project(project_id),
                self.backend_client.get_project_members(project_id),
                self.backend_client.get_project_tasks(project_id),
            )

            project_data = project_raw.get("data") if isinstance(project_raw, dict) and "data" in project_raw else project_raw
            members = members_raw.get("data") if isinstance(members_raw, dict) and "data" in members_raw else members_raw
            tasks = tasks_raw.get("data") if isinstance(tasks_raw, dict) and "data" in tasks_raw else tasks_raw

            lines = []

            if isinstance(project_data, dict):
                lines.append(f"Project: {project_data.get('PName', project_data.get('name', 'N/A'))}")
                lines.append(f"Description: {project_data.get('Description', project_data.get('description', 'N/A'))}")
                techs = project_data.get("technologyUsed") or []
                if isinstance(techs, str):
                    techs = [t.strip() for t in techs.split(",") if t.strip()]
                lines.append(f"Technology stack: {', '.join(techs) if techs else 'N/A'}")
                lines.append(f"Timeline: {project_data.get('startDate', '?')} → {project_data.get('endDate', '?')}")

            if isinstance(members, list) and members:
                lines.append(f"Team size: {len(members)} member(s)")
                member_names = [m.get("FullName", "?") for m in members[:5] if isinstance(m, dict)]
                lines.append(f"Members: {', '.join(member_names)}")

            if isinstance(tasks, list) and tasks:
                total = len(tasks)
                done = sum(1 for t in tasks if isinstance(t, dict) and t.get("status") in ("completed", "done"))
                overdue = sum(
                    1 for t in tasks
                    if isinstance(t, dict) and t.get("status") not in ("completed", "done")
                    and t.get("end_date")
                )
                lines.append(f"Tasks: {total} total, {done} completed, {overdue} potentially overdue")

            return "\n".join(lines) if lines else ""

        except Exception as e:
            self.logger.error(f"Project context summary error: {str(e)}")
            return ""

    # ------------------------------------------------------------------
    # GitHub Tool
    # ------------------------------------------------------------------

    async def fetch_github_data(self, repo_name: str, mode: str = "summary") -> str:
        if not self.github_token:
            return "GitHub Tool is not configured (Missing GITHUB_TOKEN in .env)."

        headers = {
            "Authorization": f"token {self.github_token}",
            "Accept": "application/vnd.github.v3+json",
        }
        base_url = f"https://api.github.com/repos/{repo_name}"

        try:
            async with httpx.AsyncClient(follow_redirects=True, timeout=5.0) as client:
                if mode == "commits":
                    resp = await client.get(f"{base_url}/commits?per_page=5", headers=headers)
                    resp.raise_for_status()
                    data = resp.json()
                    items = [
                        f"- {c['commit']['author']['name']}: {c['commit']['message']} "
                        f"({c['commit']['author']['date']})"
                        for c in data
                    ]
                    return f"Latest 5 commits for {repo_name}:\n" + "\n".join(items)

                elif mode == "issues":
                    resp = await client.get(f"{base_url}/issues?state=open&per_page=5", headers=headers)
                    resp.raise_for_status()
                    data = resp.json()
                    items = [
                        f"- #{i['number']} {i['title']} (by {i['user']['login']})"
                        for i in data
                    ]
                    return f"Latest 5 open issues for {repo_name}:\n" + "\n".join(items)

                else:  # summary
                    resp = await client.get(base_url, headers=headers)
                    resp.raise_for_status()
                    d = resp.json()
                    return (
                        f"GitHub Repository: {d['full_name']}\n"
                        f"Description: {d['description']}\n"
                        f"Stars: {d['stargazers_count']}, Forks: {d['forks_count']}\n"
                        f"Main Language: {d['language']}\n"
                        f"Open Issues: {d['open_issues_count']}"
                    )

        except Exception as e:
            self.logger.error(f"GitHub Tool Error: {str(e)}")
            return f"Error fetching GitHub data: {str(e)}"

    # Python Interpreter tool has been removed for security reasons.
    # It allowed arbitrary code execution with full system access.

    # ------------------------------------------------------------------
    # ArXiv Research Tool
    # ------------------------------------------------------------------

    async def search_arxiv(self, query: str, max_results: int = 3) -> str:
        """Search ArXiv for academic papers relevant to the query."""
        try:
            search_query = query.replace(" ", "+")
            url = (
                f"https://export.arxiv.org/api/query?"
                f"search_query=all:{search_query}"
                f"&max_results={max_results}"
                f"&sortBy=relevance"
            )
            async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
                resp = await client.get(url)
                resp.raise_for_status()

            import xml.etree.ElementTree as ET
            root = ET.fromstring(resp.text)
            ns = {"atom": "http://www.w3.org/2005/Atom"}

            entries = root.findall("atom:entry", ns)
            if not entries:
                return "No relevant academic papers found on ArXiv."

            papers = []
            for entry in entries[:max_results]:
                title = entry.find("atom:title", ns)
                summary = entry.find("atom:summary", ns)
                published = entry.find("atom:published", ns)
                authors = entry.findall("atom:author", ns)

                title_text = title.text.strip() if title is not None else "Unknown"
                summary_text = summary.text.strip() if summary is not None else ""
                pub_date = published.text[:10] if published is not None else ""
                author_names = [
                    a.find("atom:name", ns).text
                    for a in authors[:3]
                    if a.find("atom:name", ns) is not None
                ]

                paper_str = f"- {title_text}"
                if author_names:
                    paper_str += f" ({', '.join(author_names)}, {pub_date})"
                if summary_text:
                    paper_str += f"\n  {summary_text[:300]}"
                papers.append(paper_str)

            result = f"ArXiv papers for '{query}':\n" + "\n\n".join(papers)
            if len(result) > 2000:
                result = result[:2000] + "\n[...arxiv truncated...]"
            return result

        except Exception as e:
            self.logger.error(f"ArXiv Tool Error: {e}")
            return "Unable to search ArXiv at this time."

    # ------------------------------------------------------------------
    # StackOverflow Developer Q&A Tool
    # ------------------------------------------------------------------

    async def search_stackoverflow(self, query: str, max_results: int = 3) -> str:
        """Search StackOverflow for developer Q&A relevant to the query."""
        if not self.stackoverflow_api_key:
            return "StackOverflow search is not configured (Missing STACKOVERFLOW_API_KEY)."

        try:
            search_query = query.replace(" ", "+")
            url = (
                f"https://api.stackexchange.com/2.3/search/advanced?"
                f"order=desc&sort=relevance&q={search_query}"
                f"&site=stackoverflow&pagesize={max_results}"
                f"&key={self.stackoverflow_api_key}"
                f"&filter=withbody"
            )
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(url)
                resp.raise_for_status()
                data = resp.json()

            items = data.get("items", [])
            if not items:
                return "No relevant StackOverflow answers found."

            results = []
            for item in items[:max_results]:
                title = item.get("title", "Unknown")
                score = item.get("score", 0)
                answer_count = item.get("answer_count", 0)
                link = item.get("link", "")
                # Strip HTML tags from body
                import re
                body = re.sub(r"<[^>]+>", "", item.get("body", "")).strip()
                body = body[:400]

                result_str = (
                    f"- [{score} pts, {answer_count} answers] {title}\n"
                    f"  {body}\n"
                    f"  {link}"
                )
                results.append(result_str)

            output = f"StackOverflow results for '{query}':\n" + "\n\n".join(results)
            if len(output) > 2000:
                output = output[:2000] + "\n[...stackoverflow truncated...]"
            return output

        except Exception as e:
            self.logger.error(f"StackOverflow Tool Error: {e}")
            return "Unable to search StackOverflow at this time."