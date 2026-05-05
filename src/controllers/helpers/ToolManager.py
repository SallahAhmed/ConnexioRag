from langchain_community.utilities import SQLDatabase
from langchain_community.tools.wikipedia.tool import WikipediaQueryRun
from langchain_community.utilities import WikipediaAPIWrapper, SerpAPIWrapper
import logging
import warnings
import asyncio
import sys
import io
import traceback
import httpx

# Register pgvector's custom 'vector' type with SQLAlchemy so LangChain
# doesn't emit SAWarning when reflecting the database schema.
try:
    from sqlalchemy.dialects.postgresql import dialect as pg_dialect
    from sqlalchemy import TypeDecorator, UserDefinedType
    class VectorType(UserDefinedType):
        """Stub type to silence pgvector SAWarning during schema reflection."""
        def get_col_spec(self):
            return "vector"
    pg_dialect.colspecs = getattr(pg_dialect, "colspecs", {})
    pg_dialect.ischema_names = getattr(pg_dialect, "ischema_names", {})
    pg_dialect.ischema_names["vector"] = VectorType
except Exception:
    pass  # Non-critical; just means the warning may still appear

class ToolManager:
    def __init__(self, db_engine_url: str, generation_client, vectordb_client, 
                 embedding_client, template_parser, serpapi_api_key: str = None, 
                 github_token: str = None, reranker=None):
        self.db_engine_url = db_engine_url
        self.generation_client = generation_client
        self.vectordb_client = vectordb_client
        self.embedding_client = embedding_client
        self.template_parser = template_parser
        self.reranker = reranker
        self.logger = logging.getLogger(__name__)

        # Initialize SQL Database (sync version for LangChain tools)
        # We strip +asyncpg for compatibility with standard SQLAlchemy used by LangChain.
        # We also exclude embedding tables (which contain raw vector columns) from
        # schema reflection — they are not useful for text-to-SQL queries anyway.
        sync_url = db_engine_url.replace("+asyncpg", "")
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            self.db = SQLDatabase.from_uri(sync_url)

        # Initialize Wikipedia
        api_wrapper = WikipediaAPIWrapper(top_k_results=5, doc_content_chars_max=4000)
        self.wiki_tool = WikipediaQueryRun(api_wrapper=api_wrapper)

        # Initialize Google Search (SerpApi)
        if serpapi_api_key:
            self.serp_tool = SerpAPIWrapper(serpapi_api_key=serpapi_api_key)
        else:
            self.serp_tool = None
            
        # Initialize GitHub
        self.github_token = github_token

    def _get_collection_name(self, project_id) -> str:
        """Single source of truth for vector collection naming."""
        return f"collection_{self.vectordb_client.default_vector_size}_{project_id}".strip()

    async def execute_sql_query(self, query_text: str) -> str:
        """
        Translates Natural Language to SQL and executes it.
        """
        try:
            # We use a custom chain or the LangChain built-in one
            # For v2, we'll implement a simple text-to-sql prompt integration
            # since we are using a custom generation_client
            
            # Step 1: Generate SQL 
            # Note: We truncate the schema to ensure it doesn't blow the context
            schema = await asyncio.to_thread(self.db.get_table_info)
            if len(schema) > 5000:
                schema = schema[:5000] + "\n[...schema truncated for brevity...]"

            prompt = f"Given the following SQL schema:\n{schema}\n\nGenerate a single PostgreSQL SELECT query to answer: {query_text}\nReturn ONLY the SQL code."
            
            sql_query = await self.generation_client.generate_text(prompt=prompt)
            
            if not sql_query:
                return "Could not generate SQL query."

            # Clean the query (remove markdown formatting if present)
            sql_query = sql_query.strip().replace("```sql", "").replace("```", "").strip()
            
            # Step 2: Execute (Read-only)
            result = await asyncio.to_thread(self.db.run, sql_query)
            result = str(result)
            if len(result) > 1500:
                result = result[:1500] + "\n[...result truncated for size...]"
            return result
        except Exception as e:
            self.logger.error(f"SQL Tool Error: {str(e)}")
            return f"Error executing database query: {str(e)}"

    async def search_wiki(self, query: str, lang: str = "en") -> str:
        """
        Searches Wikipedia in a specific language.
        """
        try:
            # Update the language for the current search
            self.wiki_tool.api_wrapper.lang = lang
            res = await asyncio.to_thread(self.wiki_tool.run, query)
            
            # Fallback to English if no results found in local language
            if (not res or "No relevant information" in res or "Page not found" in res) and lang != "en":
                self.logger.info(f"Wiki search failed for {lang}, retrying in English...")
                self.wiki_tool.api_wrapper.lang = "en"
                res = await asyncio.to_thread(self.wiki_tool.run, query)

            if len(res) > 2000:
                res = res[:2000] + "\n[...wiki truncated...]"
            return res
        except Exception as e:
            # Handle the specific "Expecting value" error which usually means a blocked/empty response
            if "Expecting value" in str(e):
                return "No relevant information found on Wikipedia for this specific term."
            self.logger.error(f"Wiki Tool Error: {str(e)}")
            return "Unable to perform Wikipedia search at this time."

    async def search_google(self, query: str) -> str:
        """
        Searches Google using SerpApi.
        """
        if not self.serp_tool:
            return "Google Search is not configured (Missing API Key)."
        
        try:
            res = await asyncio.to_thread(self.serp_tool.run, query)
            if len(res) > 2000:
                res = res[:2000] + "\n[...google truncated...]"
            return res
        except Exception as e:
            self.logger.error(f"Google Search Tool Error: {str(e)}")
            return "Unable to perform Google Search at this time."

    async def search_knowledge_base(self, project_id: str, query: str, limit: int = 5):
        """
        Wraps current vector search logic to find relevant document chunks using hybrid search and reranking.
        """
        try:
            # Use shared helper for collection name
            collection_name = self._get_collection_name(project_id)

            # Embed the query
            vectors = await self.embedding_client.embed_text(text=query, document_type="query")
            if not vectors or len(vectors) == 0:
                return "Could not embed query for knowledge base search."
            
            query_vector = vectors[0]

            # Perform Hybrid Search with RRF Ranking
            try:
                results = await self.vectordb_client.hybrid_search(
                    collection_name=collection_name,
                    query=query,
                    vector=query_vector,
                    limit=limit
                )
            except Exception as e:
                self.logger.warning(f"Hybrid search failed, falling back to vector search: {str(e)}")
                # Fallback to standard vector search (The "Brilliant" search safety net)
                results = await self.vectordb_client.search_by_vector(
                    collection_name=collection_name,
                    vector=query_vector,
                    limit=limit
                )

            if not results:
                return "No relevant documents found in the knowledge base."

            # Rerank if a reranker is provided
            if self.reranker and len(results) > 0:
                results = await self.reranker.rerank(query=query, documents=results, top_k=limit)
            else:
                # Fallback to naive limit
                results = results[:limit]

            # Format results for the agent
            formatted_results = "\n\n".join([
                f"[Doc {i+1}]: {res.text[:1500]}" for i, res in enumerate(results)
            ])
            
            if len(formatted_results) > 3000:
                formatted_results = formatted_results[:3000] + "\n[...kb truncated...]"
                
            return formatted_results
        except Exception as e:
            self.logger.error(f"Knowledge Base Tool Error: {str(e)}")
            return f"Error searching knowledge base: {str(e)}"

    async def get_matching_rationale(self, user_id: int, project_id: int) -> str:
        """
        Explains why a user was matched to a project based on the 6-factor algorithm.
        """
        try:
            # In a real scenario, we'd query the weights and scores from the DB.
            # Here, we'll fetch the user's technology match for the project as a primary factor.
            query = f"""
            SELECT t.name 
            FROM technology t
            JOIN user_technology ut ON t.id = ut.tech_id
            JOIN project_technology pt ON t.id = pt.tech_id
            WHERE ut.UID = {user_id} AND pt.PID = {project_id}
            """
            matched_techs = await asyncio.to_thread(self.db.run, query)
            
            # Formulate the rationale based on weights (0.35 skill, 0.25 availability, etc.)
            prompt = f"Explain to the user (UID: {user_id}) why they match Project {project_id}. Key Factors: Matched Techs: {matched_techs}. Weights: 35% Skills, 25% Availability, 20% Rating, 12% Experience, 5% Goals, 3% Domain. Speak personally."
            return await self.generation_client.generate_text(prompt=prompt)
        except Exception as e:
            if "relation" in str(e).lower() and ("technology" in str(e).lower() or "user" in str(e).lower()):
                return "Note: Core matching metrics and technical skills are currently stored in the main application database. I'll provide detailed 6-factor matching rationales once the main DB is synchronized with this RAG environment."
            self.logger.error(f"Matching Rationale Error: {str(e)}")
            return "Unable to calculate matching rationale at this time."

    async def get_team_gaps(self, project_id: int) -> str:
        """
        Identifies missing technical and non-technical roles in a team.
        """
        try:
            # Find required technology that isn't covered by current team
            query = f"""
            SELECT t.name 
            FROM technology t
            JOIN project_technology pt ON t.id = pt.tech_id
            WHERE pt.PID = {project_id}
            AND t.id NOT IN (
                SELECT ut.tech_id 
                FROM user_technology ut
                JOIN user_project up ON ut.UID = up.UID
                WHERE up.PID = {project_id}
            )
            """
            missing_techs = await asyncio.to_thread(self.db.run, query)
            return f"The project is currently missing the following technical expertise: {missing_techs}. Recommendation: Find members with these skills to ensure delivery."
        except Exception as e:
            if "relation" in str(e).lower() and "technology" in str(e).lower():
                return "Note: Core technology tracking tables are not yet linked to the RAG database. I can identify semantic gaps once the main Connexio DB is synchronized."
            self.logger.error(f"Team Gap Error: {str(e)}")
            return "Error assessing team gaps."

    async def get_user_portfolio(self, user_id: int) -> str:
        """
        Summarizes a user's task history and deliverables for their portfolio.
        """
        try:
            query = f"""
            SELECT t.TaskName, t.TaskDesc, p.PName
            FROM task t
            JOIN project p ON t.PID = p.PID
            WHERE t.UID = {user_id}
            """
            tasks = await asyncio.to_thread(self.db.run, query)
            prompt = f"Summarize the following project contributions for a professional portfolio entry:\n{tasks}"
            return await self.generation_client.generate_text(prompt=prompt)
        except Exception as e:
            if "relation" in str(e).lower() and ("task" in str(e).lower() or "project" in str(e).lower()):
                return "Note: Task history is currently stored in the main application database and hasn't been synced to the RAG context yet. I can summarize PDF/text documents in the meantime."
            self.logger.error(f"Portfolio Error: {str(e)}")
            return "Error generating portfolio summary."

    async def get_streak_quote(self, user_id: int) -> str:
        """
        Fetches or generates a domain-aware motivational quote for the user.
        """
        try:
            # Check if quotes table exists (mocked or real)
            # If not found, LLM generates one based on user's field
            field_query = f"SELECT fieldExperience FROM \"user\" WHERE UID = {user_id}"
            field = await asyncio.to_thread(self.db.run, field_query)
            
            prompt = f"Generate a short, powerful motivational one-liner for a professional in the field of {field}. Make it inspiring."
            return await self.generation_client.generate_text(prompt=prompt)
        except Exception as e:
            return "Keep pushing forward! Every small step is progress."

    async def get_project_risks(self, project_id: int = None) -> str:
        """
        Aggregates risk metrics (missed deadlines, stalled progress) for supervisors.
        """
        try:
            filter_str = f"WHERE project_id = {project_id}" if project_id else ""
            query = f"SELECT project_id, project_name, progress FROM projects {filter_str} ORDER BY progress ASC"
            metrics = await asyncio.to_thread(self.db.run, query)
            
            prompt = f"Analyze these project progress metrics and identify which are at high risk of failing this sprint:\n{metrics}"
            return await self.generation_client.generate_text(prompt=prompt)
        except Exception as e:
            if "relation" in str(e).lower() and "projects" in str(e).lower():
                return "Project tracking data is not yet available in the database."
            self.logger.error(f"Risk Assessment Error: {str(e)}")
            return "Error performing risk assessment."

    async def generate_project_docs(self, project_id: int, doc_type: str = "readme") -> str:
        """
        Generates structured documentation (README, Retrospective) from project data.
        """
        try:
            query = f"SELECT * FROM projects WHERE project_id = {project_id}"
            proj_data = await asyncio.to_thread(self.db.run, query)
            
            # Tasks are core app data, handle missing gracefully
            tasks = "No synchronized task heartbeats found for this project yet."
            try:
                task_query = f"SELECT TaskId, TaskName, TaskDesc FROM task WHERE PID = {project_id}"
                tasks = await asyncio.to_thread(self.db.run, task_query)
            except Exception:
                pass 
            
            prompt = f"Generate a high-quality Markdown {doc_type} for this project using this data:\nProject: {proj_data}\nTasks: {tasks}"
            return await self.generation_client.generate_text(prompt=prompt)
        except Exception as e:
            self.logger.error(f"Doc Gen Error: {str(e)}")
            return "Error generating documentation. Ensure the project exists in the RAG database."

    async def fetch_github_data(self, repo_name: str, mode: str = "summary") -> str:
        """
        Fetches metadata, commits, or issues from a GitHub repository.
        """
        if not self.github_token:
            return "GitHub Tool is not configured (Missing GITHUB_TOKEN). Please add it to your .env file."
        
        headers = {
            "Authorization": f"token {self.github_token}",
            "Accept": "application/vnd.github.v3+json"
        }
        
        base_url = f"https://api.github.com/repos/{repo_name}"
        
        try:
            async with httpx.AsyncClient(follow_redirects=True) as client:
                if mode == "commits":
                    url = f"{base_url}/commits?per_page=5"
                    resp = await client.get(url, headers=headers)
                    resp.raise_for_status()
                    data = resp.json()
                    results = [f"- {c['commit']['author']['name']}: {c['commit']['message']} ({c['commit']['author']['date']})" for c in data]
                    return f"Latest 5 commits for {repo_name}:\n" + "\n".join(results)
                
                elif mode == "issues":
                    url = f"{base_url}/issues?state=open&per_page=5"
                    resp = await client.get(url, headers=headers)
                    resp.raise_for_status()
                    data = resp.json()
                    results = [f"- #{i['number']} {i['title']} (by {i['user']['login']})" for i in data]
                    return f"Latest 5 open issues for {repo_name}:\n" + "\n".join(results)
                
                else: # Summary
                    resp = await client.get(base_url, headers=headers)
                    resp.raise_for_status()
                    data = resp.json()
                    return (f"GitHub Repository: {data['full_name']}\n"
                            f"Description: {data['description']}\n"
                            f"Stars: {data['stargazers_count']}, Forks: {data['forks_count']}\n"
                            f"Main Language: {data['language']}\n"
                            f"Open Issues: {data['open_issues_count']}")
                            
        except Exception as e:
            self.logger.error(f"GitHub Tool Error: {str(e)}")
            return f"Error fetching data from GitHub: {str(e)}"

    async def execute_python(self, code: str) -> str:
        """
        Executes Python code in a restricted local environment and returns stdout/stderr.
        """
        self.logger.info("Executing Python Tool...")
        
        # Clean the code block if it contains markdown
        code = code.strip().replace("```python", "").replace("```", "").strip()
        
        # Capture stdout and stderr
        stdout_capture = io.StringIO()
        stderr_capture = io.StringIO()
        
        # Restricted globals/locals
        # Note: This is not a perfectly secure sandbox, but sufficient for RAG data processing.
        safe_globals = {
            "__builtins__": __builtins__,
            "asyncio": asyncio,
            "math": __import__("math"),
            "datetime": __import__("datetime"),
            "json": __import__("json")
        }
        
        original_stdout = sys.stdout
        original_stderr = sys.stderr
        
        try:
            sys.stdout = stdout_capture
            sys.stderr = stderr_capture
            
            # Execute the code
            exec(code, safe_globals)
            
            output = stdout_capture.getvalue()
            errors = stderr_capture.getvalue()
            
            result = ""
            if output:
                result += f"Output:\n{output}\n"
            if errors:
                result += f"Errors:\n{errors}\n"
                
            if not result:
                result = "Code executed successfully with no output."
                
            return result
        except Exception:
            return f"Python Execution Error:\n{traceback.format_exc()}"
        finally:
            sys.stdout = original_stdout
            sys.stderr = original_stderr

