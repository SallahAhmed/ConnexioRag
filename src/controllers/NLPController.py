from .BaseController import BaseController
from models.db_schemas import Project, DataChunk
from stores.llm.LLMEnums import DocumentTypeEnum
from typing import List, Optional
import json
from .WorkflowController import WorkflowController
from .helpers.ToolManager import ToolManager
from models.enums.WorkflowNodeEnum import WorkflowNodeEnum
from models.SessionModel import SessionModel
import asyncio
from datetime import datetime

class NLPController(BaseController):

    def __init__(self, vectordb_client, generation_client, 
                 embedding_client, template_parser, settings=None, db_client=None):
        super().__init__()

        self.vectordb_client = vectordb_client
        self.generation_client = generation_client
        self.embedding_client = embedding_client
        self.template_parser = template_parser
        self.settings = settings
        self.db_client = db_client

        # Initialize Controllers
        self.workflow_controller = WorkflowController(
            generation_client=self.generation_client,
            template_parser=self.template_parser
        )

        if self.db_client:
            self.session_model = SessionModel(db_client=self.db_client)

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
        vectors = await self.embedding_client.embed_text(text=texts, 
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
        vectors = await self.embedding_client.embed_text(text=text, 
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
    
    async def answer_agent_chat(self, user_id: int, project_id: Optional[int], query: str, 
                                persona: str = "student", session_id: Optional[int] = None, limit: int = 5):
        """
        Comprehensive Agentic Chat Loop:
        1. Detect Node & Language
        2. Manage Session/Memory
        3. Route to Multi-Source Tools
        4. Generate Grounded Response
        """
        # Step 1: Detect Intent & Language
        now = lambda: datetime.now().strftime("%H:%M:%S")
        print(f"\n[AGENT] [{now()}] Query: {query[:50]}...")
        language = await self.workflow_controller.detect_language(query)
        self.template_parser.set_language(language)

        print(f"[AGENT] [{now()}] Detecting user intent (Node)...")
        node = await self.workflow_controller.detect_node(query)
        print(f"[AGENT] [{now()}] Node: {node}")
        
        # Step 2: Session Management & Persona Mapping
        if language == "ar":
            # Map common English persona keys to Arabic for better prompt grounding
            persona_map = {
                "student": "طالب",
                "early_career": "مبتدئ مهني",
                "educator": "معلم",
                "company": "شركة"
            }
            persona = persona_map.get(persona.lower(), persona)

        if self.db_client:
            chat_session = await self.session_model.get_or_create_session(
                user_id=user_id, project_id=project_id, persona=persona, language=language
            )
            session_id = chat_session.session_id
            history = await self.session_model.get_recent_history(session_id)
        else:
            history = []

        # Step 3: Multi-Source Retrieval (Sequential for Stability)
        retrieved_context = []
        sources = []

        print(f"[AGENT] [{now()}] Searching Knowledge Base...")
        kb_results = await self.tool_manager.search_knowledge_base(project_id=project_id, query=query, limit=limit)
        retrieved_context.append(f"--- KNOWLEDGE BASE ---\n{kb_results}")
        sources.append("Documentation")

        # Tool 2: Adaptive SQL/Wiki Routing based on query keywords or node
        lower_query = query.lower()
        if "why was i matched" in lower_query or "recommendation" in lower_query:
            match_rationale = await self.tool_manager.get_matching_rationale(user_id, project_id)
            retrieved_context.append(f"--- MATCHING RATIONALE ---\n{match_rationale}")
            sources.append("Matching Algorithm")
        
        if "role" in lower_query or "what should i do" in lower_query:
            role_gaps = await self.tool_manager.get_team_gaps(project_id)
            retrieved_context.append(f"--- ROLE ANALYSIS ---\n{role_gaps}")
            sources.append("Project Structure")

        if node in [WorkflowNodeEnum.MILESTONE_WARNING, WorkflowNodeEnum.BLOCKER]:
            risks = await self.tool_manager.get_project_risks(project_id)
            retrieved_context.append(f"--- PROJECT RISKS ---\n{risks}")
            sources.append("Project Metrics")

        # Fallback to Wiki for Jargon
        if node == WorkflowNodeEnum.GENERAL and len(retrieved_context) < 2:
            wiki = await self.tool_manager.search_wiki(query, lang=language)
            if wiki:
                retrieved_context.append(f"--- WIKIPEDIA ---\n{wiki}")
                sources.append("General Research")

        # Step 4: Construct Generation Context with Strict Budgeting
        system_prompt = self.template_parser.get("rag", "system_prompt", {
            "persona": persona,
            "node": node.value
        })
        
        # Calculate total available budget
        total_budget = getattr(self.settings, "TOTAL_CONTEXT_CHAR_BUDGET", 15000)
        
        # Arabic Optimization: Arabic text uses significantly more tokens per character.
        # We lower the budget to 6,000 to ensure it stays within local model memory limits.
        if language == "ar":
            total_budget = 6000
        
        # Build context string
        context_string = "\n\n".join(retrieved_context)
        # Allocate 50% of budget to retrieved context
        max_context_chars = int(total_budget * 0.5)
        context_string = context_string[:max_context_chars]

        footer_prompt = self.template_parser.get("rag", "footer_prompt", {
            "query": query,
            "context": context_string
        })

        # Step 5: Manage History with Strict Budgeting (Sliding Window)
        # Allocate 30% of budget to history (rest is for prompts and generation)
        max_history_chars = int(total_budget * 0.3)
        truncated_history = self._get_truncated_history(history, max_history_chars)

        # Build final chat history for the AI provider
        chat_history = [self.generation_client.construct_prompt(prompt=system_prompt, role="system")]
        for msg in truncated_history:
            chat_history.append(self.generation_client.construct_prompt(prompt=msg['content'], role=msg['role']))

        # Step 6: Generate & Persist
        answer = await self.generation_client.generate_text(prompt=footer_prompt, chat_history=chat_history)
        
        if self.db_client:
            await self.session_model.append_message(session_id, "user", query, node.value)
            await self.session_model.append_message(session_id, "assistant", answer, node.value)

        return {
            "answer": answer,
            "node": node.value,
            "language": language,
            "sources": list(set(sources)),
            "session_id": session_id
        }

    def _get_truncated_history(self, history: list, total_char_limit: int) -> list:
        """
        Works backward from the most recent messages. 
        Ensures the total character count across history messages doesn't exceed the limit.
        """
        truncated = []
        current_chars = 0
        
        # Reverse to get newest first, then reverse back at the end
        for msg in reversed(history):
            content = msg['content'][:2000] # Truncate individual massive messages
            if current_chars + len(content) > total_char_limit:
                break
            
            truncated.append({"role": msg['role'], "content": content})
            current_chars += len(content)
            
        return list(reversed(truncated))

    async def get_user_portfolio(self, user_id: int):
        return await self.tool_manager.get_user_portfolio(user_id)

    async def get_coach_path(self, user_id: int, project_id: Optional[int]):
        return await self.tool_manager.get_streak_quote(user_id) # Example placeholder for now

    async def get_supervisor_risks(self, project_id: Optional[int]):
        return await self.tool_manager.get_project_risks(project_id)

    async def get_doc_gen(self, project_id: int, doc_type: str):
        return await self.tool_manager.generate_project_docs(project_id, doc_type)

    async def get_task_architect_plan(self, query: str, user_id: int, project_id: int):
        # Combines knowledge base search with task resolution logic
        kb_context = await self.tool_manager.search_knowledge_base(project_id, query)
        prompt = f"As a Task Architect, provide a step-by-step resolution plan for: {query}\n\nContext:\n{kb_context}"
        return self.generation_client.generate_text(prompt=prompt)