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
