from .BaseController import BaseController
from models.db_schemas import Project, DataChunk
from stores.llm.LLMEnums import DocumentTypeEnum
from typing import List
import json
from .WorkflowController import WorkflowController
from .helpers.ToolManager import ToolManager
from models.enums.WorkflowNodeEnum import WorkflowNodeEnum

class NLPController(BaseController):

    def __init__(self, vectordb_client, generation_client, 
                 embedding_client, template_parser, settings=None):
        super().__init__()

        self.vectordb_client = vectordb_client
        self.generation_client = generation_client
        self.embedding_client = embedding_client
        self.template_parser = template_parser
        self.settings = settings

        # Initialize Workflow and Tool Controllers
        self.workflow_controller = WorkflowController(
            generation_client=self.generation_client,
            template_parser=self.template_parser
        )

        if self.settings:
            postgres_conn = f"postgresql://{settings.POSTGRES_USERNAME}:{settings.POSTGRES_PASSWORD}@{settings.POSTGRES_HOST}:{settings.POSTGRES_PORT}/{settings.POSTGRES_MAIN_DATABASE}"
            
            self.tool_manager = ToolManager(
                db_engine_url=postgres_conn,
                generation_client=self.generation_client,
                vectordb_client=self.vectordb_client,
                embedding_client=self.embedding_client,
                template_parser=self.template_parser
            )

    def create_collection_name(self, project_id: str):
        return f"collection_{self.vectordb_client.default_vector_size}_{project_id}".strip()
    
    async def reset_vector_db_collection(self, project: Project):
        collection_name = self.create_collection_name(project_id=project.project_id)
        return await self.vectordb_client.delete_collection(collection_name=collection_name)
    
    async def get_vector_db_collection_info(self, project: Project):
        collection_name = self.create_collection_name(project_id=project.project_id)
        collection_info = await self.vectordb_client.get_collection_info(collection_name=collection_name)

        return json.loads(
            json.dumps(collection_info, default=lambda x: x.__dict__)
        )
    
    async def index_into_vector_db(self, project: Project, chunks: List[DataChunk],
                                   chunks_ids: List[int], 
                                   do_reset: bool = False):
        
        # step1: get collection name
        collection_name = self.create_collection_name(project_id=project.project_id)

        # step2: manage items
        texts = [ c.chunk_text for c in chunks ]
        metadata = [ c.chunk_metadata for c in  chunks]
        vectors = self.embedding_client.embed_text(text=texts, 
                                                  document_type=DocumentTypeEnum.DOCUMENT.value)

        # step3: create collection if not exists
        _ = await self.vectordb_client.create_collection(
            collection_name=collection_name,
            embedding_size=self.embedding_client.embedding_size,
            do_reset=do_reset,
        )

        # step4: insert into vector db
        _ = await self.vectordb_client.insert_many(
            collection_name=collection_name,
            texts=texts,
            metadata=metadata,
            vectors=vectors,
            record_ids=chunks_ids,
        )

        return True

    async def search_vector_db_collection(self, project: Project, text: str, limit: int = 10):

        # step1: get collection name
        collection_name = self.create_collection_name(project_id=project.project_id)

        # step2: get text embedding vector
        vectors = self.embedding_client.embed_text(text=text, 
                                                 document_type=DocumentTypeEnum.QUERY.value)

        if not vectors or len(vectors) == 0:
            return False
        
        if isinstance(vectors, list) and len(vectors) > 0:
            query_vector = vectors[0]

        if not query_vector:
            return False    

        # step3: do semantic search
        results = await self.vectordb_client.search_by_vector(
            collection_name=collection_name,
            vector=query_vector,
            limit=limit
        )

        if not results:
            return False

        return results
    
    async def answer_rag_question(self, project: Project, query: str, limit: int = 10):
        
        answer, full_prompt, chat_history = None, None, None

        # Step 1: Detect Metadata (Node, Language, Persona)
        language = await self.workflow_controller.detect_language(query)
        self.template_parser.set_language(language)
        
        node = await self.workflow_controller.detect_node(query)
        persona = await self.workflow_controller.detect_persona(query)

        # Step 2: Adaptive Retrieval based on Node
        retrieved_context = []
        
        # Always search knowledge base (Vector DB) for grounding
        kb_results = await self.tool_manager.search_knowledge_base(
            project_id=project.project_id, query=query, limit=limit
        )
        retrieved_context.append(f"--- KNOWLEDGE BASE ---\n{kb_results}")

        # Check for specific nodes that need extra tools
        if node in [WorkflowNodeEnum.TEAM_FORMATION, WorkflowNodeEnum.PHASE_TRANSITION, WorkflowNodeEnum.MILESTONE_WARNING]:
            # These nodes require project metrics from the SQL database
            sql_results = await self.tool_manager.execute_sql_query(query)
            retrieved_context.append(f"--- PROJECT DATABASE ---\n{sql_results}")
        
        elif node == WorkflowNodeEnum.GENERAL:
            # General facts might benefit from Wikipedia
            wiki_results = await self.tool_manager.search_wiki(query)
            retrieved_context.append(f"--- WIKIPEDIA ---\n{wiki_results}")

        # Step 3: Construct LLM prompt
        # Use node-specific persona guides from templates
        system_prompt = self.template_parser.get("rag", "system_prompt", {
            "persona": persona,
            "node": node.value
        })

        context_string = "\n\n".join(retrieved_context)
        
        footer_prompt = self.template_parser.get("rag", "footer_prompt", {
            "query": query,
            "context": context_string
        })

        # Step 4: Construct Generation Client Prompts
        chat_history = [
            self.generation_client.construct_prompt(
                prompt=system_prompt,
                role=self.generation_client.enums.SYSTEM.value,
            )
        ]

        full_prompt = footer_prompt

        # Step 5: Retrieve the Final Grounded Answer
        answer = self.generation_client.generate_text(
            prompt=full_prompt,
            chat_history=chat_history
        )

        return answer, full_prompt, chat_history