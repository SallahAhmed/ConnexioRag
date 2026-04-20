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
import uuid
from .helpers.TraceManager import tracer

class NLPController(BaseController):

    def __init__(self, vectordb_client, generation_client, 
                 embedding_client, template_parser, settings=None, db_client=None, reranker=None):
        super().__init__()

        self.vectordb_client = vectordb_client
        self.generation_client = generation_client
        self.embedding_client = embedding_client
        self.template_parser = template_parser
        self.settings = settings
        self.db_client = db_client
        self.reranker = reranker

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
                template_parser=self.template_parser,
                reranker=self.reranker
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
    
    async def _prepare_chat_context(self, user_id: int, project_id: Optional[int], query: str, 
                                persona: str = "student", session_id: Optional[int] = None, limit: int = 5):
        """
        Prepares the chat context, history, and tools before generating text.
        """
        trace_id = str(uuid.uuid4())
        now = lambda: datetime.now().strftime("%H:%M:%S")
        print(f"\n[AGENT] [{now()}] Query: {query[:50]}...")
        
        # Step 1: Detect Intent & Language
        step_id = tracer.start_trace(trace_id, "Intent & Language Detection")
        language = await self.workflow_controller.detect_language(query)
        self.template_parser.set_language(language)
        node = await self.workflow_controller.detect_node(query)
        tracer.end_trace(trace_id, step_id, {"node": node.value, "language": language})

        print(f"[AGENT] [{now()}] Node: {node}")
        
        # Step 2: Session Management
        step_id = tracer.start_trace(trace_id, "Session Management")
        if language == "ar":
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
        tracer.end_trace(trace_id, step_id, {"session_id": session_id})

        # Step 3: Multi-Source Retrieval (With Query Decomposition & CRAG)
        retrieved_context = []
        sources = []

        step_id = tracer.start_trace(trace_id, "Query Decomposition")
        print(f"[AGENT] [{now()}] Decomposing Query (Internal Logic)...")
        self.template_parser.set_language("en")
        
        decompose_sys = self.template_parser.get("relevance_grading", "decompose_query_system_prompt")
        decompose_usr = self.template_parser.get("relevance_grading", "decompose_query_user_prompt", {"query": query})
        decompose_history = [self.generation_client.construct_prompt(prompt=decompose_sys, role="system")]
        
        decomposed_queries_text = await self.generation_client.generate_text(
            prompt=decompose_usr, chat_history=decompose_history, max_output_tokens=100
        )
        
        queries_to_search = [query]
        if decomposed_queries_text:
            try:
                import ast
                cleaned_text = decomposed_queries_text.strip().replace('```python', '').replace('```', '').strip()
                parsed = ast.literal_eval(cleaned_text)
                if isinstance(parsed, list) and len(parsed) > 0:
                    queries_to_search = parsed[:3]
                    print(f"[AGENT] [{now()}] Queries decomposed into: {queries_to_search}")
            except Exception:
                pass
        tracer.end_trace(trace_id, step_id, queries_to_search)

        step_id = tracer.start_trace(trace_id, "Knowledge Base Retrieval")
        print(f"[AGENT] [{now()}] Searching Knowledge Base...")
        kb_results = ""
        for q in queries_to_search:
            res = await self.tool_manager.search_knowledge_base(project_id=project_id, query=q, limit=limit)
            kb_results += f"\n[Results for: {q}]\n{res}\n"
        tracer.end_trace(trace_id, step_id, f"Length: {len(kb_results)}")

        step_id = tracer.start_trace(trace_id, "Relevance Grading")
        print(f"[AGENT] [{now()}] Grading Document Relevance...")
        grade_sys = self.template_parser.get("relevance_grading", "relevance_grader_system_prompt")
        grade_usr = self.template_parser.get("relevance_grading", "relevance_grader_user_prompt", {
            "query": query, "document": kb_results[:2000]
        })
        grade_history = [self.generation_client.construct_prompt(prompt=grade_sys, role="system")]
        grade_result = await self.generation_client.generate_text(
            prompt=grade_usr, chat_history=grade_history, max_output_tokens=10
        )
        grade_result_str = (grade_result or "").upper()
        print(f"[AGENT] [{now()}] Document Grade: {grade_result_str}")
        tracer.end_trace(trace_id, step_id, grade_result_str)

        if "IRRELEVANT" in grade_result_str:
            step_id = tracer.start_trace(trace_id, "Wikipedia Fallback")
            print(f"[AGENT] [{now()}] Triggering Fallback Search...")
            wiki_fb = await self.tool_manager.search_wiki(query, lang=language)
            if wiki_fb:
                retrieved_context.append(f"--- WIKIPEDIA FALLBACK ---\n{wiki_fb}")
                sources.append("External Fallback")
            tracer.end_trace(trace_id, step_id, "Completed")
        else:
            retrieved_context.append(f"--- KNOWLEDGE BASE ---\n{kb_results}")
            sources.append("Documentation")
            
        self.template_parser.set_language(language)

        lower_query = query.lower()
        if "why was i matched" in lower_query or "recommendation" in lower_query:
            step_id = tracer.start_trace(trace_id, "Matching Rationale Tool")
            match_rationale = await self.tool_manager.get_matching_rationale(user_id, project_id)
            retrieved_context.append(f"--- MATCHING RATIONALE ---\n{match_rationale}")
            sources.append("Matching Algorithm")
            tracer.end_trace(trace_id, step_id, "Completed")
        
        if "role" in lower_query or "what should i do" in lower_query:
            step_id = tracer.start_trace(trace_id, "Team Gaps Tool")
            role_gaps = await self.tool_manager.get_team_gaps(project_id)
            retrieved_context.append(f"--- ROLE ANALYSIS ---\n{role_gaps}")
            sources.append("Project Structure")
            tracer.end_trace(trace_id, step_id, "Completed")

        if node in [WorkflowNodeEnum.MILESTONE_WARNING, WorkflowNodeEnum.BLOCKER]:
            step_id = tracer.start_trace(trace_id, "Project Risk Assessment")
            risks = await self.tool_manager.get_project_risks(project_id)
            retrieved_context.append(f"--- PROJECT RISKS ---\n{risks}")
            sources.append("Project Metrics")
            tracer.end_trace(trace_id, step_id, "Completed")

        if node == WorkflowNodeEnum.GENERAL and len(retrieved_context) < 2:
            step_id = tracer.start_trace(trace_id, "Wikipedia Jargon Search")
            wiki = await self.tool_manager.search_wiki(query, lang=language)
            if wiki:
                retrieved_context.append(f"--- WIKIPEDIA ---\n{wiki}")
                sources.append("General Research")
            tracer.end_trace(trace_id, step_id, "Completed")

        system_prompt = self.template_parser.get("rag", "system_prompt", {
            "persona": persona,
            "node": node.value
        })
        
        total_budget = getattr(self.settings, "TOTAL_CONTEXT_CHAR_BUDGET", 15000)
        if language == "ar":
            total_budget = 6000
        
        context_string = "\n\n".join(retrieved_context)
        max_context_chars = int(total_budget * 0.5)
        context_string = context_string[:max_context_chars]

        footer_prompt = self.template_parser.get("rag", "footer_prompt", {
            "query": query,
            "context": context_string
        })

        max_history_chars = int(total_budget * 0.3)
        truncated_history = self._get_truncated_history(history, max_history_chars)

        chat_history = [self.generation_client.construct_prompt(prompt=system_prompt, role="system")]
        for msg in truncated_history:
            chat_history.append(self.generation_client.construct_prompt(prompt=msg['content'], role=msg['role']))

        return chat_history, footer_prompt, session_id, node, language, list(set(sources)), trace_id

    async def answer_agent_chat(self, user_id: int, project_id: Optional[int], query: str, 
                                persona: str = "student", session_id: Optional[int] = None, limit: int = 5):
        
        chat_history, footer_prompt, session_id, node, language, sources, trace_id = await self._prepare_chat_context(
            user_id, project_id, query, persona, session_id, limit
        )
        
        step_id = tracer.start_trace(trace_id, "LLM Generation", {"streaming": False})

        # Step 6: Generate & Persist
        answer = await self.generation_client.generate_text(prompt=footer_prompt, chat_history=chat_history)
        tracer.end_trace(trace_id, step_id, answer)

        if self.db_client:
            await self.session_model.append_message(session_id, "user", query, node.value)
            await self.session_model.append_message(session_id, "assistant", answer, node.value)

        return {
            "answer": answer,
            "node": node.value,
            "language": language,
            "sources": sources,
            "session_id": session_id,
            "trace": tracer.export_trace(trace_id)
        }

    async def answer_agent_chat_stream(self, user_id: int, project_id: Optional[int], query: str, 
                                persona: str = "student", session_id: Optional[int] = None, limit: int = 5):
        
        chat_history, footer_prompt, session_id, node, language, sources, trace_id = await self._prepare_chat_context(
            user_id, project_id, query, persona, session_id, limit
        )

        metadata_sent = False
        full_answer = ""
        
        step_id = tracer.start_trace(trace_id, "LLM Generation", {"streaming": True})
        # We need to stream the textual chunks. But we must also pass connection metadata.
        # So we yield SSE formatted lines.
        async for chunk in self.generation_client.generate_text_stream(prompt=footer_prompt, chat_history=chat_history):
            if not metadata_sent:
                # First chunk sends meta info
                metadata = {
                    "node": node.value,
                    "language": language,
                    "sources": sources,
                    "session_id": session_id,
                    "trace_id": trace_id,
                    "event": "meta"
                }
                yield f"data: {json.dumps(metadata)}\n\n"
                metadata_sent = True
            
            if chunk:
                full_answer += chunk
                yield f"data: {json.dumps({'text': chunk})}\n\n"
        
        tracer.end_trace(trace_id, step_id, full_answer)
        
        # Finally send the full trace summary in a final event
        yield f"data: {json.dumps({'event': 'trace', 'data': tracer.export_trace(trace_id)})}\n\n"

        # When done streaming, persist to DB.
        if self.db_client:
            await self.session_model.append_message(session_id, "user", query, node.value)
            await self.session_model.append_message(session_id, "assistant", full_answer, node.value)
            
        yield "data: [DONE]\n\n"

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