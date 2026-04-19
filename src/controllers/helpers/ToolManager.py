from langchain_community.utilities import SQLDatabase
from langchain_community.tools.wikipedia.tool import WikipediaQueryRun
from langchain_community.utilities import WikipediaAPIWrapper
from langchain.chains import create_sql_query_chain
from langchain_community.tools.sql_database.tool import QuerySQLDataBaseTool
import logging

class ToolManager:
    def __init__(self, db_engine_url: str, generation_client, vectordb_client, 
                 embedding_client, template_parser):
        self.db_engine_url = db_engine_url
        self.generation_client = generation_client
        self.vectordb_client = vectordb_client
        self.embedding_client = embedding_client
        self.template_parser = template_parser
        self.logger = logging.getLogger(__name__)

        # Initialize SQL Database (sync version for LangChain tools)
        # Note: We strip +asyncpg for compatibility with standard SQLAlchemy engine used by LangChain tools
        sync_url = db_engine_url.replace("+asyncpg", "")
        self.db = SQLDatabase.from_uri(sync_url)

        # Initialize Wikipedia
        api_wrapper = WikipediaAPIWrapper(top_k_results=3, doc_content_chars_max=1000)
        self.wiki_tool = WikipediaQueryRun(api_wrapper=api_wrapper)

    async def execute_sql_query(self, query_text: str) -> str:
        """
        Translates Natural Language to SQL and executes it.
        """
        try:
            # We use a custom chain or the LangChain built-in one
            # For v2, we'll implement a simple text-to-sql prompt integration
            # since we are using a custom generation_client
            
            # Step 1: Generate SQL 
            # Note: In a production scenario, we'd use create_sql_query_chain
            # but here we'll use our generation_client with a schema-aware prompt.
            
            schema = self.db.get_table_info()
            prompt = f"Given the following SQL schema:\n{schema}\n\nGenerate a single PostgreSQL SELECT query to answer: {query_text}\nReturn ONLY the SQL code."
            
            sql_query = self.generation_client.generate_text(prompt=prompt)
            
            if not sql_query:
                return "Could not generate SQL query."

            # Clean the query (remove markdown formatting if present)
            sql_query = sql_query.strip().replace("```sql", "").replace("```", "").strip()
            
            # Step 2: Execute (Read-only)
            result = self.db.run(sql_query)
            return result
        except Exception as e:
            self.logger.error(f"SQL Tool Error: {str(e)}")
            return f"Error executing database query: {str(e)}"

    async def search_wiki(self, query: str) -> str:
        """
        Searches Wikipedia.
        """
        return self.wiki_tool.run(query)

    async def search_knowledge_base(self, project_id: str, query: str, limit: int = 5):
        """
        Wraps current vector search logic to find relevant document chunks.
        """
        try:
            # Replicate collection name logic
            collection_name = f"collection_{self.vectordb_client.default_vector_size}_{project_id}".strip()

            # Embed the query
            vectors = self.embedding_client.embed_text(text=query, document_type="query")
            if not vectors or len(vectors) == 0:
                return "Could not embed query for knowledge base search."
            
            query_vector = vectors[0]

            # Search vector DB
            results = await self.vectordb_client.search_by_vector(
                collection_name=collection_name,
                vector=query_vector,
                limit=limit
            )

            if not results:
                return "No relevant documents found in the knowledge base."

            # Format results for the agent
            formatted_results = "\n\n".join([
                f"[Doc {i+1}]: {res.text}" for i, res in enumerate(results)
            ])
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
            matched_techs = self.db.run(query)
            
            # Formulate the rationale based on weights (0.35 skill, 0.25 availability, etc.)
            prompt = f"Explain to the user (UID: {user_id}) why they match Project {project_id}. Key Factors: Matched Techs: {matched_techs}. Weights: 35% Skills, 25% Availability, 20% Rating, 12% Experience, 5% Goals, 3% Domain. Speak personally."
            return self.generation_client.generate_text(prompt=prompt)
        except Exception as e:
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
            missing_techs = self.db.run(query)
            return f"The project is currently missing the following technical expertise: {missing_techs}. Recommendation: Find members with these skills to ensure delivery."
        except Exception as e:
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
            tasks = self.db.run(query)
            prompt = f"Summarize the following project contributions for a professional portfolio entry:\n{tasks}"
            return self.generation_client.generate_text(prompt=prompt)
        except Exception as e:
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
            field = self.db.run(field_query)
            
            prompt = f"Generate a short, powerful motivational one-liner for a professional in the field of {field}. Make it inspiring."
            return self.generation_client.generate_text(prompt=prompt)
        except Exception as e:
            return "Keep pushing forward! Every small step is progress."

    async def get_project_risks(self, project_id: int = None) -> str:
        """
        Aggregates risk metrics (missed deadlines, stalled progress) for supervisors.
        """
        try:
            filter_str = f"WHERE PID = {project_id}" if project_id else ""
            query = f"SELECT PID, PName, progress FROM project {filter_str} ORDER BY progress ASC"
            metrics = self.db.run(query)
            
            prompt = f"Analyze these project progress metrics and identify which are at high risk of failing this sprint:\n{metrics}"
            return self.generation_client.generate_text(prompt=prompt)
        except Exception as e:
            self.logger.error(f"Risk Assessment Error: {str(e)}")
            return "Error performing risk assessment."

    async def generate_project_docs(self, project_id: int, doc_type: str = "readme") -> str:
        """
        Generates structured documentation (README, Retrospective) from project data.
        """
        try:
            query = f"SELECT * FROM project WHERE PID = {project_id}"
            proj_data = self.db.run(query)
            task_query = f"SELECT TaskName, TaskDesc FROM task WHERE PID = {project_id}"
            tasks = self.db.run(task_query)
            
            prompt = f"Generate a high-quality Markdown {doc_type} for this project using this data:\nProject: {proj_data}\nTasks: {tasks}"
            return self.generation_client.generate_text(prompt=prompt)
        except Exception as e:
            return "Error generating documentation."
