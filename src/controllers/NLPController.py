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
import logging

class NLPController(BaseController):

    def __init__(self, vectordb_client, generation_client, 
                 embedding_client, template_parser, utility_client=None, settings=None, db_client=None, reranker=None):
        super().__init__()
        self.logger = logging.getLogger(__name__)

        self.vectordb_client = vectordb_client
        self.generation_client = generation_client
        self.utility_client = utility_client if utility_client else generation_client
        self.embedding_client = embedding_client
        self.template_parser = template_parser
        self.settings = settings
        self.db_client = db_client
        self.reranker = reranker

        # Initialize Controllers
        self.workflow_controller = WorkflowController(
            generation_client=self.generation_client,
            template_parser=self.template_parser,
            utility_client=self.utility_client
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
                serpapi_api_key=settings.SERPAPI_API_KEY,
                github_token=settings.GITHUB_TOKEN,
                reranker=self.reranker
            )

    def create_collection_name(self, project_id: str):
        """Single source of truth for vector collection naming. Keep in sync with ToolManager."""
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

        # Step 3: Multi-Source Retrieval (Simplified for Speed)
        retrieved_context = []
        sources = []

        # --- Query Decomposition Disabled for Speed ---
        # step_id = tracer.start_trace(trace_id, "Query Decomposition")
        # print(f"[AGENT] [{now()}] Decomposing Query (Internal Logic)...")
        # ... (logic omitted)
        # tracer.end_trace(trace_id, step_id, queries_to_search)
        
        queries_to_search = [query]

        step_id = tracer.start_trace(trace_id, "Knowledge Base Retrieval")
        print(f"[AGENT] [{now()}] Searching Knowledge Base (Parallel)...")
        
        # Search all decomposed queries (and the original one) in parallel
        search_tasks = [
            self.tool_manager.search_knowledge_base(project_id=project_id, query=q, limit=limit)
            for q in queries_to_search
        ]
        results = await asyncio.gather(*search_tasks)
        
        # --- Corrective RAG (CRAG) Logic ---
        # If KB is empty or irrelevant, we fallback to Web Search
        kb_results = ""
        for q, res in zip(queries_to_search, results):
            kb_results += f"\n[Results for: {q}]\n{res}\n"

        is_kb_relevant = await self.workflow_controller.grade_relevance(query, kb_results)
        
        if not is_kb_relevant:
            tracer.end_trace(trace_id, step_id, "Irrelevant/Empty (Fallback Triggered)")
            
            # Step 1: Decision Logic (The "Brilliant" part)
            decision_prompt = f"""Analyze the user query: "{query}" and select the single best tool.
            - "WIKIPEDIA": General knowledge, history, science, definitions.
            - "GOOGLE": News, recent events, technical stats, product info.
            - "GITHUB": Code, repositories, issues.
            - "PYTHON": Math, logic, data processing.
            
            IMPORTANT: Return ONLY one word from the list above. No explanation."""
            
            choice = await self.utility_client.generate_text(prompt=decision_prompt)
            choice = choice.strip().upper()
            
            # Step 2: Tool Specific Processing
            print(f"[AGENT] [{now()}] Knowledge Gap Detected. Using {choice} for fallback...")
            
            if "GITHUB" in choice:
                step_id_github = tracer.start_trace(trace_id, "GitHub Tool Search")
                refine_prompt = f"Extract the GitHub repository name (e.g., 'owner/repo') and the desired mode ('summary', 'commits', or 'issues') from this query: {query}. Return as JSON: {{\"repo\": \"...\", \"mode\": \"...\"}}. Return ONLY the JSON."
                gh_info_raw = await self.utility_client.generate_text(prompt=refine_prompt)
                try:
                    gh_info = json.loads(gh_info_raw.strip().replace("```json", "").replace("```", ""))
                    repo_name = gh_info.get("repo")
                    if repo_name and "/" in repo_name:
                        github_results = await self.tool_manager.fetch_github_data(repo_name=repo_name, mode=gh_info.get("mode", "summary"))
                    else:
                        github_results = "No specific GitHub repository was identified in the query."
                except:
                    github_results = "Error parsing GitHub request."
                
                retrieved_context.append(f"\n[GitHub Repository Data]:\n{github_results}")
                sources.append("GitHub")
                tracer.end_trace(trace_id, step_id_github, f"GitHub Result: {github_results[:50]}...")

            elif "PYTHON" in choice:
                step_id_python = tracer.start_trace(trace_id, "Python Interpreter Execution")
                python_prompt = f"Write a short, efficient Python script to solve or analyze this request: {query}. Return ONLY the Python code block."
                python_code = await self.utility_client.generate_text(prompt=python_prompt)
                python_results = await self.tool_manager.execute_python(code=python_code)
                
                retrieved_context.append(f"\n[Python Execution Result]:\n{python_results}")
                sources.append("Python Interpreter")
                tracer.end_trace(trace_id, step_id_python, f"Python Output Length: {len(python_results)}")

            elif "GOOGLE" in choice:
                step_id_web = tracer.start_trace(trace_id, "Google Search Fallback")
                refine_prompt = f"Create a 3-word Google search query for: {query}. Return ONLY the query."
                refined_query = await self.utility_client.generate_text(prompt=refine_prompt)
                refined_query = refined_query.strip().strip('"').strip("'")
                web_results = await self.tool_manager.search_google(query=refined_query)
                retrieved_context.append(f"\n[Live Web Search (Google)]:\n{web_results}")
                sources.append("Google Search")
                tracer.end_trace(trace_id, step_id_web, f"Google Length: {len(web_results)}")
            
            else: # WIKIPEDIA
                step_id_wiki = tracer.start_trace(trace_id, "Wikipedia Fallback Search")
                refine_prompt = f"Search Wikipedia for: {query}. Return ONLY the main subject name."
                refined_query = await self.utility_client.generate_text(prompt=refine_prompt)
                refined_query = refined_query.strip().strip('"').strip("'")
                wiki_results = await self.tool_manager.search_wiki(query=refined_query, lang=language)
                if wiki_results and "Unable to perform" not in wiki_results:
                    retrieved_context.append(f"\n[Global Knowledge (Wikipedia)]:\n{wiki_results}")
                    sources.append("Wikipedia")
                else:
                    retrieved_context.append("\n[Global Knowledge]: No external information found.")
                tracer.end_trace(trace_id, step_id_wiki, f"Wiki Length: {len(wiki_results)}")
        else:
            # KB results are valid
            retrieved_context.append(kb_results)
            sources.append("Documentation")
            tracer.end_trace(trace_id, step_id, f"Total Length: {len(kb_results)}")
        
        # Strictly local document retrieval
        self.template_parser.set_language(language)

        system_prompt = self.template_parser.get("rag", "system_prompt", {
            "persona": persona,
            "node": node.value
        })
        
        total_budget = getattr(self.settings, "TOTAL_CONTEXT_CHAR_BUDGET", 15000)
        if language == "ar":
            # Arabic is token-expensive (~1 char ≈ 1+ token), so we apply a tighter cap
            # to stay within local model limits, but never below 8000 for usable context.
            total_budget = min(total_budget, 8000)
        
        context_string = "\n\n".join(retrieved_context)
        max_context_chars = int(total_budget * 0.5)
        context_string = context_string[:max_context_chars]

        print(f"DEBUG: Retrieved Context Length: {len(context_string)} chars")
        if len(context_string) == 0:
            print("WARNING: NO CONTEXT RETRIEVED FROM DATABASE!")

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
        
        if not answer or len(answer.strip()) == 0:
            self.logger.warning(f"AI returned an empty response for trace {trace_id}")
            answer = "I apologize, but the AI model took too long to generate a response or returned an empty answer. Please try a simpler question or use the streaming endpoint for immediate feedback."

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
        return await self.generation_client.generate_text(prompt=prompt)