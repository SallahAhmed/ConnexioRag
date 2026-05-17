from .BaseController import BaseController
from models.db_schemas import Project, DataChunk
from stores.llm.LLMEnums import DocumentTypeEnum
from typing import List, Optional
import json
import sys
import re
from .WorkflowController import WorkflowController
from .helpers.ToolManager import ToolManager
from models.enums.WorkflowNodeEnum import WorkflowNodeEnum
from models.SessionModel import SessionModel
import asyncio
from datetime import datetime
import uuid
from .helpers.TraceManager import tracer
import logging
import os
import tiktoken


class NLPController(BaseController):

    def __init__(
        self,
        vectordb_client,
        generation_client,
        embedding_client,
        template_parser,
        utility_client=None,
        settings=None,
        db_client=None,
        reranker=None,
        backend_client=None,   # BackendApiClient — injected from app state
        masarx_client=None,    # MasarxApiClient — reads MasarX PostgreSQL tables
    ):
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
        self.backend_client = backend_client  # May be None in Celery workers
        self.masarx_client = masarx_client

        # --- WorkflowController ---
        self.workflow_controller = WorkflowController(
            generation_client=self.generation_client,
            template_parser=self.template_parser,
            utility_client=self.utility_client,
        )

        # --- SessionModel ---
        if self.db_client:
            self.session_model = SessionModel(db_client=self.db_client)

        # --- ToolManager ---
        if self.settings:
            postgres_conn = (
                f"postgresql://{settings.POSTGRES_USERNAME}:{settings.POSTGRES_PASSWORD}"
                f"@{settings.POSTGRES_HOST}:{settings.POSTGRES_PORT}"
                f"/{settings.POSTGRES_MAIN_DATABASE}"
            )
            self.tool_manager = ToolManager(
                db_engine_url=postgres_conn,
                generation_client=self.generation_client,
                vectordb_client=self.vectordb_client,
                embedding_client=self.embedding_client,
                template_parser=self.template_parser,
                serpapi_api_key=settings.SERPAPI_API_KEY,
                github_token=settings.GITHUB_TOKEN,
                stackoverflow_api_key=settings.STACKOVERFLOW_API_KEY,
                reranker=self.reranker,
                backend_client=self.backend_client,
                masarx_client=self.masarx_client,
            )

    # ------------------------------------------------------------------
    # Collection helpers
    # ------------------------------------------------------------------

    def create_collection_name(self, project_id: int):
        """Single source of truth for vector collection naming. Keep in sync with ToolManager."""
        return f"collection_{self.vectordb_client.default_vector_size}_{project_id}".strip()

    async def reset_vector_db_collection(self, project: Project):
        collection_name = self.create_collection_name(project_id=project.project_id)
        return await self.vectordb_client.delete_collection(collection_name=collection_name)

    async def get_vector_db_collection_info(self, project: Project):
        collection_name = self.create_collection_name(project_id=project.project_id)
        collection_info = await self.vectordb_client.get_collection_info(
            collection_name=collection_name
        )
        return json.loads(json.dumps(collection_info, default=lambda x: x.__dict__))

    # ------------------------------------------------------------------
    # Indexing
    # ------------------------------------------------------------------

    async def index_into_vector_db(
        self,
        project: Project,
        chunks: List[DataChunk],
        chunks_ids: List[int],
        do_reset: bool = False,
    ):
        collection_name = self.create_collection_name(project_id=project.project_id)
        texts = [c.chunk_text for c in chunks]
        metadata = [c.chunk_metadata for c in chunks]
        vectors = await self.embedding_client.embed_text(
            text=texts, document_type=DocumentTypeEnum.DOCUMENT.value
        )

        _ = await self.vectordb_client.create_collection(
            collection_name=collection_name,
            embedding_size=self.embedding_client.embedding_size,
            do_reset=do_reset,
        )
        _ = await self.vectordb_client.insert_many(
            collection_name=collection_name,
            texts=texts,
            metadata=metadata,
            vectors=vectors,
            record_ids=chunks_ids,
        )
        return True

    # ------------------------------------------------------------------
    # Search
    # ------------------------------------------------------------------

    async def search_vector_db_collection(
        self, project: Project, text: str, limit: int = 10
    ):
        collection_name = self.create_collection_name(project_id=project.project_id)
        vectors = await self.embedding_client.embed_text(
            text=text, document_type=DocumentTypeEnum.QUERY.value
        )

        if not vectors or len(vectors) == 0:
            return False

        query_vector = vectors[0] if isinstance(vectors, list) else vectors
        if not query_vector:
            return False

        results = await self.vectordb_client.search_by_vector(
            collection_name=collection_name, vector=query_vector, limit=limit
        )
        return results if results else False

    # ------------------------------------------------------------------
    # Chat context preparation
    # ------------------------------------------------------------------

    async def _prepare_chat_context(
        self,
        user_id: int,
        project_id: Optional[int],
        query: str,
        persona: str = "student",
        session_id: Optional[int] = None,
        limit: int = 5,
        model_tier: str = "auto",
        language: Optional[str] = None,
        extra_context: Optional[str] = None,
    ):
        """
        Prepares chat history, retrieves context from all sources, and
        builds the final prompt components ready for generation.
        """
        trace_id = str(uuid.uuid4())
        now = lambda: datetime.now().strftime("%H:%M:%S")
        print(f"\n[AGENT] [{now()}] Query: {query[:50]}...", file=sys.stderr)

        # --- Step 1: Intent & Language ---
        explicit_language = language is not None
        step_id = tracer.start_trace(trace_id, "Intent & Language Detection")

        # extra_context (file upload) → skip detection, always GENERAL, explicit language or en
        is_file_query = bool(extra_context)
        if is_file_query:
            language = language or "en"
            query_language = language
            node = WorkflowNodeEnum.GENERAL
            self.template_parser.set_language(language)
            self.logger.info("File query — skipping intent/language detection, using GENERAL/%s", language)
        else:
            language = language or await self.workflow_controller.detect_language(query)
            query_language = language
            self.template_parser.set_language(language)
            node = await self.workflow_controller.detect_node(query)

        tracer.end_trace(
            trace_id, step_id,
            {"node": node.value, "language": language},
            usage=self.utility_client.last_usage,
        )
        self.logger.info("Query: %s... Node: %s", query[:50], node)

        # --- Step 2: Session ---
        step_id = tracer.start_trace(trace_id, "Session Management")
        if language == "ar":
            persona_map = {
                "student": "طالب",
                "early_career": "مبتدئ مهني",
                "educator": "معلم",
                "company": "شركة",
            }
            persona = persona_map.get(persona.lower(), persona)

        if self.db_client:
            chat_session = await self.session_model.get_or_create_session(
                user_id=user_id,
                project_id=project_id,
                persona=persona,
                language=language,
            )
            session_id = chat_session.session_id

            # Update session language to match current query
            if chat_session.language != language:
                await self.session_model.update_session_metadata(
                    session_id, language=language
                )

            if any(
                cmd in query.lower()
                for cmd in ["clear history", "forget everything", "نظف السجل", "نسيان السجل"]
            ):
                await self.session_model.append_message(
                    session_id, "system", "History cleared by user."
                )
                history = []
            else:
                history = await self.session_model.get_recent_history(session_id)
        else:
            history = []

        # Without project context, cap history at 20 messages (10 turns)
        # to give the LLM rich conversational memory without context overflow.
        if not project_id:
            history = history[-20:] if len(history) > 20 else history

        # File queries (upload-and-query): cap history to last 4 messages (2 turns)
        if is_file_query:
            history = history[-4:] if len(history) > 4 else history

        # Initialize lists here so they are available for memory timeline injection
        retrieved_context = []
        sources = []

        # --- Memory Intent Detection ---
        # Detect when the user is asking about past conversations
        # and inject a chronological timeline to help the LLM summarize accurately.
        memory_keywords = [
            "what did we talk about", "what was the last thing", "what we discussed",
            "yesterday", "last conversation", "previous conversation", "our last chat",
            "ماذا تحدثنا", "عن ماذا تكلمنا", "آخر شيء", "آخر محادثة", "الأمس",
            "المحادثة السابقة", "تحدثنا بالأمس",
        ]
        is_memory_query = any(kw in query.lower() for kw in memory_keywords)

        if is_memory_query and history:
            memory_summary = []
            for i, msg in enumerate(history):
                if language == "ar":
                    role_label = "المستخدم" if msg["role"] == "user" else "المساعد الذكي"
                else:
                    role_label = "User" if msg["role"] == "user" else "Assistant"
                memory_summary.append(f"[{i+1}] {role_label}: {msg['content']}")

            summary_text = "\n".join(memory_summary)
            if language == "ar":
                retrieved_context.append(
                    f"\n[سجل المحادثات السابقة لتجيب المستخدم بدقة عما تحدثتم عنه]:\n{summary_text}"
                )
            else:
                retrieved_context.append(
                    f"\n[Previous Conversation History to help you answer about past talks]:\n{summary_text}"
                )
            sources.append("Conversation Memory")
            node = WorkflowNodeEnum.GENERAL

        tracer.end_trace(trace_id, step_id, {"session_id": session_id})

        # --- Pasted URL Automatic Processing & Extraction ---
        # Detect if the query contains a URL anywhere inside it, download and extract its text
        # content dynamically, and feed it into prompt context.
        url_match = re.search(r'(https?://[^\s]+)', query)
        if url_match:
            extracted_url = url_match.group(1).strip()
            self.logger.info(f"[URL Parser] Detected URL in query: {extracted_url}")
            try:
                import httpx
                async with httpx.AsyncClient(follow_redirects=True, timeout=15.0) as client:
                    resp = await client.get(extracted_url)
                if resp.status_code == 200:
                    content_type = resp.headers.get("content-type", "").lower()
                    content_bytes = resp.content
                    parsed_text = None

                    # 1. Word / docx format (via magic bytes or MIME-type)
                    if "officedocument.wordprocessingml" in content_type or content_bytes.startswith(b"PK\x03\x04"):
                        import docx2txt
                        import io
                        parsed_text = docx2txt.process(io.BytesIO(content_bytes))
                    # 2. PDF format (via magic bytes or MIME-type)
                    elif "application/pdf" in content_type or content_bytes.startswith(b"%PDF"):
                        import fitz  # PyMuPDF
                        doc = fitz.open(stream=content_bytes, filetype="pdf")
                        parsed_text = "\n".join(page.get_text() for page in doc)
                    # 3. Plain text / fallback
                    else:
                        try:
                            parsed_text = content_bytes.decode("utf-8")
                        except Exception:
                            parsed_text = content_bytes.decode("latin-1")

                    if parsed_text and parsed_text.strip():
                        extracted = parsed_text.strip()
                        # Limit to 8000 characters to keep it clean and fits context
                        if len(extracted) > 8000:
                            extracted = extracted[:8000] + "\n\n[...content truncated for length...]"

                        retrieved_context.append(f"\n[Content of Pasted Document URL ({extracted_url})]:\n{extracted}")
                        sources.append("Pasted Link")
                        # Override node to GENERAL so the model processes this as a general retrieval query
                        node = WorkflowNodeEnum.GENERAL
                        # Skip database retrieval since we already got the document content directly
                        is_memory_query = True
            except Exception as e:
                self.logger.error(f"[URL Parser] Failed to download or parse query URL: {e}")

        # --- Extra context injection (used by upload-and-query for file content) ---
        if extra_context:
            retrieved_context.append(extra_context)
            sources.append("Document")
            is_memory_query = True  # skip KB retrieval + CRAG — file content IS the source

        # --- Token budgeting ---
        try:
            encoding = tiktoken.get_encoding("cl100k_base")
        except Exception:
            encoding = None

        total_token_budget = getattr(self.settings, "TOTAL_CONTEXT_TOKEN_BUDGET", 4000)

        def count_tokens(text):
            return len(encoding.encode(text)) if encoding else len(text) // 4

        truncated_history = self._get_truncated_history(
            history, total_token_budget // 3, encoding
        )
        utility_history = [
            self.utility_client.construct_prompt(
                prompt=msg["content"], role=msg["role"]
            )
            for msg in truncated_history
        ]

        # --- Step 3: Knowledge Base Retrieval & CRAG ---
        step_id = tracer.start_trace(trace_id, "Knowledge Base Retrieval & CRAG")

        is_temporal_query = any(kw in query.lower() for kw in [
            "this year", "latest", "recent", "trend", "current", "news", "currently",
            "هذا العام", "أحدث", "آخر الأخبار", "اتجاهات", "جديد",
        ])
        if is_temporal_query:
            self.logger.info(f"[RAG TEMPORAL] Detected temporal query: '{query[:50]}' -> Google forced")

        if node == WorkflowNodeEnum.OUT_OF_SCOPE:
            tracer.end_trace(trace_id, step_id, "Skipped (Out of Scope)")

        elif is_temporal_query:
            tracer.end_trace(trace_id, step_id, "Temporal — Google forced")
            crag_results = await self._run_crag_tools(
                query, language, utility_history, trace_id, max_tools=1, force_tool="GOOGLE"
            )
            for source_name, result_text in crag_results:
                retrieved_context.append(f"\n[{source_name}]:\n{result_text}")
                sources.append(source_name)

        elif is_memory_query:
            tracer.end_trace(trace_id, step_id, "Memory query — KB skipped")

        else:
            raw_docs = await self.tool_manager.search_knowledge_base_raw(
                project_id=project_id if project_id else 0, query=query, limit=limit
            )

            if not raw_docs:
                tracer.end_trace(trace_id, step_id, "Empty KB — firing 2 CRAG tools")
                crag_results = await self._run_crag_tools(
                    query, language, utility_history, trace_id, max_tools=2
                )
                for source_name, result_text in crag_results:
                    retrieved_context.append(f"\n[{source_name}]:\n{result_text}")
                    sources.append(source_name)
            else:
                # Batch-grade all docs in one LLM call
                grades = await self.workflow_controller.grade_relevance_batch(query, raw_docs)

                relevant_docs = [d for d, g in zip(raw_docs, grades) if g == "RELEVANT"]
                ambiguous_docs = [d for d, g in zip(raw_docs, grades) if g == "AMBIGUOUS"]
                n_total = len(raw_docs)
                n_rel = len(relevant_docs)
                n_amb = len(ambiguous_docs)
                n_irr = n_total - n_rel - n_amb
                self.logger.info(
                    f"[RAG GRADING] Total: {n_total} | Relevant: {n_rel} | "
                    f"Ambiguous: {n_amb} | Irrelevant: {n_irr}"
                )

                # Build KB context from RELEVANT + AMBIGUOUS (separate list for clean discard)
                kb_context = []
                filtered_docs = relevant_docs + ambiguous_docs
                if filtered_docs:
                    parts = [f"[Doc {i+1}]: {d.text[:1500]}" for i, d in enumerate(filtered_docs)]
                    kb_text = "\n\n".join(parts)
                    if len(kb_text) > 3000:
                        kb_text = kb_text[:3000] + "\n[...kb truncated...]"
                    kb_context.append(kb_text)

                if n_rel == n_total:
                    # All relevant — KB sufficient, no CRAG needed
                    tracer.end_trace(trace_id, step_id, f"All {n_total} docs relevant — KB only")
                    retrieved_context.extend(kb_context)
                    sources.append("Vector DB")

                elif n_rel == 0 and n_amb == 0:
                    # All irrelevant — discard KB, fire 2 CRAG tools
                    tracer.end_trace(trace_id, step_id, f"All {n_total} docs irrelevant — CRAG only")
                    crag_results = await self._run_crag_tools(
                        query, language, utility_history, trace_id, max_tools=2
                    )
                    for source_name, result_text in crag_results:
                        retrieved_context.append(f"\n[{source_name}]:\n{result_text}")
                        sources.append(source_name)

                else:
                    # Mixed or all-ambiguous — filtered KB + 1 CRAG tool to supplement
                    tracer.end_trace(trace_id, step_id, f"Mixed grades — KB + 1 CRAG tool")
                    retrieved_context.extend(kb_context)
                    sources.append("Vector DB")
                    crag_results = await self._run_crag_tools(
                        query, language, utility_history, trace_id, max_tools=1
                    )
                    for source_name, result_text in crag_results:
                        retrieved_context.append(f"\n[{source_name}]:\n{result_text}")
                        sources.append(source_name)

        # --- Live backend context injection (project summary from main backend) ---
        if project_id and self.backend_client and node not in (WorkflowNodeEnum.OUT_OF_SCOPE,) and not is_file_query:
            try:
                live_summary = await self.tool_manager.get_project_context_summary(
                    project_id=project_id
                )
                if live_summary:
                    retrieved_context.append(f"\n[Live Project Data]:\n{live_summary}")
            except Exception as e:
                self.logger.warning(f"Could not fetch live project context: {e}")

        # --- MasarX AI-planned tasks injection ---
        if project_id and node in (
            WorkflowNodeEnum.BLOCKER,
            WorkflowNodeEnum.MILESTONE_WARNING,
            WorkflowNodeEnum.GENERAL,
            WorkflowNodeEnum.PHASE_TRANSITION,
        ) and not is_file_query:
            try:
                tasks_context = await self.tool_manager.get_masarx_tasks(project_id)
                if tasks_context:
                    retrieved_context.append(f"\n[AI-Planned Tasks (MasarX)]:\n{tasks_context}")
                    sources.append("Tasks")
            except Exception as e:
                self.logger.warning(f"Could not fetch MasarX tasks: {e}")

        # --- Step 4: Final Prompt Construction ---
        self.template_parser.set_language(query_language)

        # Decide which model to use based on intent + model_tier
        PROJECT_NODES = {
            WorkflowNodeEnum.ONBOARDING, WorkflowNodeEnum.TEAM_FORMATION,
            WorkflowNodeEnum.PHASE_TRANSITION, WorkflowNodeEnum.BLOCKER,
            WorkflowNodeEnum.MILESTONE_WARNING,
        }
        use_generation = (
            model_tier == "generation"
            or (model_tier == "auto" and node in PROJECT_NODES)
        )

        if extra_context:
            system_prompt = (
                "You are Connexio AI, a document analysis assistant. "
                "Answer the user's question based ONLY on the document content provided below. "
                "Be concise and accurate. Do not use markdown headers or emojis. "
                "If the document doesn't contain enough information, say so."
                f" Reply in {language.upper()}."
            )
            prompt_client = self.generation_client
        elif use_generation:
            if node == WorkflowNodeEnum.ONBOARDING and not project_id and language == "en":
                system_prompt = (
                    "You are Connexio AI — a project collaboration advisor for new users. "
                    f"Audience: {persona} learner | Context: onboarding\n\n"
                    "Welcome the user warmly. Give them 2-3 specific first actions they can take right now, "
                    "such as exploring the platform's features, starting a project, finding teammates, "
                    "or asking about a specific domain they're interested in.\n"
                    "Be conversational, encouraging, and end with one natural follow-up question.\n"
                    "IMPORTANT: Do NOT ask the user to provide more context or specify a project. "
                    "Assume they are truly new and guide them like a helpful mentor."
                )
            elif node == WorkflowNodeEnum.ONBOARDING and not project_id and language == "ar":
                system_prompt = (
                    "أنت Connexio AI — مستشار تعاون في المشاريع للمستخدمين الجدد. "
                    f"الجمهور: {persona} | السياق: ترحيب\n\n"
                    "رحب بالمستخدم بحرارة. أعطه 2-3 خطوات أولى محددة يمكنه اتخاذها الآن، "
                    "مثل استكشاف مميزات المنصة، بدء مشروع، البحث عن أعضاء فريق، "
                    "أو السؤال عن مجال معين يهتم به.\n"
                    "كن محادثاً ومشجعاً، واختتم بسؤال متابعة طبيعي.\n"
                    "مهم: لا تطلب من المستخدم توفير سياق أو تحديد مشروع. "
                    "افترض أنه جديد بالفعل ووجهه كمرشد مفيد."
                )
            else:
                system_prompt = self.template_parser.get(
                    "rag", "system_prompt", {"persona": persona, "node": node.value}
                )
            prompt_client = self.generation_client
        else:
            persona_guide = {
                "student": "Teach concepts simply with examples. Encourage exploration.",
                "early_career": "Give practical career advice and real-world tradeoffs.",
                "educator": "Use structured explanations with pedagogical depth.",
                "company": "Focus on ROI, strategy, efficiency, and business outcomes.",
            }
            guide = persona_guide.get(persona.lower(), persona_guide["student"])
            system_prompt = (
                f"أنت Connexio AI، مساعد تعاون ذكي في المشاريع. "
                f"{guide} "
                f"كن طبيعياً ومحادثاً. أجب دائماً بنفس لغة المستخدم إلا إذا طلب منك المستخدم صراحةً الترجمة أو الإجابة بلغة أخرى. لا تستخدم رؤوس markdown."
                if language == "ar"
                else f"You are Connexio AI, a project collaboration assistant. "
                     f"{guide} "
                     f"Be natural and conversational. Reply in the same language as the user, "
                     f"unless the user explicitly requests you to translate or reply in another language. "
                     f"Do not use markdown headers."
            )
            prompt_client = self.utility_client

        context_string = "\n\n".join(retrieved_context)

        base_tokens = count_tokens(system_prompt) + count_tokens(context_string)
        history_budget = total_token_budget - base_tokens - 200
        final_history = self._get_truncated_history(history, history_budget, encoding)

        if context_string.strip():
            footer_prompt = self.template_parser.get(
                "rag", "footer_prompt", {"query": query, "context": context_string}
            )
        else:
            footer_prompt = query

        # When language was explicitly set by the caller, reinforce it
        # to prevent chat history from pulling the model into a different language.
        if explicit_language:
            if language == "ar":
                footer_prompt += "\n\nمهم جداً: يجب عليك الرد باللغة العربية فقط. لا تستخدم لغة أخرى تحت أي ظرف."
            else:
                footer_prompt += "\n\nIMPORTANT: You MUST reply in English only. Do not use any other language under any circumstances."

        chat_history = [
            prompt_client.construct_prompt(prompt=system_prompt, role="system")
        ]
        for msg in final_history:
            chat_history.append(
                prompt_client.construct_prompt(
                    prompt=msg["content"], role=msg["role"]
                )
            )

        # Pipeline summary log
        model_name = getattr(prompt_client, 'generation_model_id', 'unknown')
        self.logger.info(
            f"[RAG PIPELINE] Node: {node.value} | Model: {model_name} | "
            f"Sources: {list(set(sources))} | Lang: {language}"
        )

        return chat_history, footer_prompt, session_id, node, language, list(set(sources)), trace_id, prompt_client, final_history

    # ------------------------------------------------------------------
    # CRAG Tool Runner
    # ------------------------------------------------------------------

    async def _run_crag_tools(
        self,
        query: str,
        language: str,
        utility_history: list,
        trace_id: str,
        max_tools: int = 2,
        force_tool: str = None,
    ) -> list:
        """
        Select and fire up to max_tools external tools for CRAG fallback.
        Returns list of (source_name, result_text) tuples — error responses excluded.
        force_tool bypasses LLM selection (used for temporal queries → GOOGLE).
        """
        ERROR_STRINGS = (
            "not configured", "Unable to perform", "Unable to search",
            "Error fetching", "Error searching", "is not configured",
        )
        tool_results = []

        if force_tool:
            tools = [force_tool]
        else:
            # Only show tools that are actually configured — avoids LLM picking missing keys
            available = ["WIKIPEDIA", "ARXIV"]
            if self.tool_manager.serp_tool:
                available.append("GOOGLE")
            if self.tool_manager.github_token:
                available.append("GITHUB")
            if self.tool_manager.stackoverflow_api_key:
                available.append("STACKOVERFLOW")

            tool_descriptions = {
                "WIKIPEDIA": "General knowledge, history, science, definitions.",
                "ARXIV": "Academic papers, research, ML/AI topics, scientific studies.",
                "GOOGLE": "News, recent events, technical stats, product info.",
                "GITHUB": "Searching repositories, finding open-source files.",
                "STACKOVERFLOW": "Developer questions, coding errors, API usage, debugging.",
            }
            tool_lines = "\n".join(
                [f'- "{t}": {tool_descriptions[t]}' for t in available]
            ) + '\n- "NONE": Conversational or no tool needed.'

            decision_prompt = (
                f'Analyze the user query: "{query}" and select up to {max_tools} tools ranked by priority.\n'
                f"{tool_lines}\n"
                f'Return ONLY JSON: {{"tools": ["TOOL1", "TOOL2"]}} or {{"tools": ["TOOL1"]}}'
            )
            raw = await self.utility_client.generate_text(prompt=decision_prompt)
            raw = (raw or "").strip()
            try:
                # Use regex to extract JSON object
                json_match = re.search(r'\{.*\}', raw, re.DOTALL)
                if json_match:
                    json_str = json_match.group(0)
                else:
                    json_str = raw.replace("```json", "").replace("```", "")
                parsed = json.loads(json_str)
                tools = [t.strip().upper() for t in parsed.get("tools", []) if t.strip().upper() != "NONE"]
            except Exception:
                # Fallback: scan raw text for any known tool name
                tools = []
                for t in ["STACKOVERFLOW", "ARXIV", "GITHUB", "WIKIPEDIA", "GOOGLE"]:
                    if t in raw.upper():
                        tools.append(t)
                        break
            tools = tools[:max_tools]

        self.logger.info(f"[RAG TOOL CHOICE] Query: '{query[:50]}' -> Tools: {tools}")

        for choice in tools:
            try:
                if choice == "GITHUB":
                    step_id = tracer.start_trace(trace_id, "GitHub Tool Search")
                    refine = (
                        f"Extract the GitHub repo name (owner/repo) and mode "
                        f"('summary','commits','issues') from: {query}. "
                        'Return ONLY JSON: {"repo": "...", "mode": "..."}'
                    )
                    gh_raw = await self.utility_client.generate_text(
                        prompt=refine, chat_history=utility_history
                    )
                    try:
                        gh_raw_clean = gh_raw.strip()
                        json_match = re.search(r'\{.*\}', gh_raw_clean, re.DOTALL)
                        if json_match:
                            gh_raw_clean = json_match.group(0)
                        else:
                            gh_raw_clean = gh_raw_clean.replace("```json", "").replace("```", "")
                        gh_info = json.loads(gh_raw_clean)
                        repo = gh_info.get("repo", "")
                        result = (
                            await self.tool_manager.fetch_github_data(
                                repo_name=repo, mode=gh_info.get("mode", "summary")
                            )
                            if repo and "/" in repo
                            else "No specific GitHub repository was identified."
                        )
                    except Exception:
                        result = "Could not parse GitHub repository from query."
                    tracer.end_trace(trace_id, step_id, result[:50], usage=self.utility_client.last_usage)
                    if not any(e in result for e in ERROR_STRINGS):
                        tool_results.append(("GitHub", result))

                elif choice == "ARXIV":
                    step_id = tracer.start_trace(trace_id, "ArXiv Research Search")
                    refine = f"Create a concise academic search query (2-4 keywords) for: {query}. Return ONLY the query."
                    refined = (
                        await self.utility_client.generate_text(prompt=refine, chat_history=utility_history) or query
                    ).strip().strip('"').strip("'")
                    result = await self.tool_manager.search_arxiv(query=refined)
                    tracer.end_trace(trace_id, step_id, f"Length: {len(result)}", usage=self.utility_client.last_usage)
                    if not any(e in result for e in ERROR_STRINGS):
                        tool_results.append(("ArXiv", result))

                elif choice == "STACKOVERFLOW":
                    step_id = tracer.start_trace(trace_id, "StackOverflow Developer Q&A")
                    refine = f"Create a concise developer search query (2-5 keywords) for: {query}. Return ONLY the query."
                    refined = (
                        await self.utility_client.generate_text(prompt=refine, chat_history=utility_history) or query
                    ).strip().strip('"').strip("'")
                    result = await self.tool_manager.search_stackoverflow(query=refined)
                    tracer.end_trace(trace_id, step_id, f"Length: {len(result)}", usage=self.utility_client.last_usage)
                    if not any(e in result for e in ERROR_STRINGS):
                        tool_results.append(("StackOverflow", result))

                elif choice == "GOOGLE":
                    step_id = tracer.start_trace(trace_id, "Google Search")
                    refine = f"Create a 3-word Google search query for: {query}. Return ONLY the query."
                    refined = (
                        await self.utility_client.generate_text(prompt=refine, chat_history=utility_history) or query
                    ).strip().strip('"').strip("'")
                    result = await self.tool_manager.search_google(query=refined)
                    tracer.end_trace(trace_id, step_id, f"Length: {len(result)}", usage=self.utility_client.last_usage)
                    if not any(e in result for e in ERROR_STRINGS):
                        tool_results.append(("Google Search", result))

                elif choice == "WIKIPEDIA":
                    step_id = tracer.start_trace(trace_id, "Wikipedia Search")
                    refine = f"Search Wikipedia for: {query}. Return ONLY the main subject name."
                    refined = (
                        await self.utility_client.generate_text(prompt=refine, chat_history=utility_history) or query
                    ).strip().strip('"').strip("'")
                    result = await self.tool_manager.search_wiki(query=refined, lang=language)
                    tracer.end_trace(trace_id, step_id, f"Length: {len(result)}", usage=self.utility_client.last_usage)
                    if result and not any(e in result for e in ERROR_STRINGS):
                        tool_results.append(("Wikipedia", result))

            except Exception as e:
                self.logger.warning(f"CRAG tool {choice} failed: {e}")

        if tool_results:
            tool_names = [t[0] for t in tool_results]
            self.logger.info(f"[RAG TOOLS] Fired: {tool_names}")
        else:
            self.logger.info(f"[RAG TOOLS] None fired (all returned errors or NONE selected)")

        return tool_results

    # ------------------------------------------------------------------
    # Public chat methods
    # ------------------------------------------------------------------

    async def answer_agent_chat(
        self,
        user_id: int,
        project_id: Optional[int],
        query: str,
        persona: str = "student",
        session_id: Optional[int] = None,
        limit: int = 5,
        model_tier: str = "auto",
        language: Optional[str] = None,
        extra_context: Optional[str] = None,
    ):
        self.logger.info(f"answer_agent_chat called with model_tier={model_tier}, language={language}")
        # Fast path — history clear
        clear_commands = [
            "clear history", "forget everything", "new topic",
            "نظف السجل", "نسيان السجل", "موضوع جديد",
        ]
        if any(cmd in query.lower() for cmd in clear_commands):
            if self.db_client:
                chat_session = await self.session_model.get_or_create_session(
                    user_id=user_id, project_id=project_id, persona=persona, language="en"
                )
                await self.session_model.append_message(
                    chat_session.session_id, "system", "History cleared by user."
                )
                sid = chat_session.session_id
            else:
                sid = 0
            lang = "ar" if any("\u0600" <= c <= "\u06FF" for c in query) else "en"
            msg = (
                "تم مسح سجل المحادثة بنجاح!" if lang == "ar"
                else "Chat history cleared successfully!"
            )
            return {
                "answer": msg, "node": "general",
                "language": lang, "sources": [], "session_id": sid,
            }

        chat_history, footer_prompt, session_id, node, language, sources, trace_id, prompt_client, final_history = (
            await self._prepare_chat_context(
                user_id, project_id, query, persona, session_id, limit, model_tier, language=language, extra_context=extra_context
            )
        )
        # Derive use_generation from the selected client so answer_agent_chat can
        # reference it without re-computing (avoids the out-of-scope local-var bug).
        use_generation = prompt_client is not self.utility_client

        # Short-circuit: out-of-scope queries never reach the generation LLM.
        if node == WorkflowNodeEnum.OUT_OF_SCOPE:
            answer = (
                "أنا متخصص في التعاون في المشاريع والمهارات المهنية. "
                "هل يمكنني مساعدتك في شيء متعلق بمشروعك؟"
                if language == "ar"
                else "I specialize in project collaboration and professional skills. "
                     "Can I help you with something related to your project?"
            )
            if self.db_client:
                await self.session_model.append_message(session_id, "user", query, node.value)
                await self.session_model.append_message(session_id, "assistant", answer, node.value)
            return {
                "answer": answer,
                "node": node.value,
                "language": language,
                "sources": [],
                "session_id": session_id,
            }

        step_id = tracer.start_trace(trace_id, "LLM Generation", {"streaming": False})
        print(f"[RAG SOURCE] {' / '.join(sources) if sources else 'NONE'}", file=sys.stderr)
        answer = await prompt_client.generate_text(
            prompt=footer_prompt, chat_history=chat_history
        )

        usage = prompt_client.last_usage or {}
        self.logger.info(
            f"[TOKEN USAGE] Node: {node.value} | "
            f"In: {usage.get('prompt_tokens', 0)} | "
            f"Out: {usage.get('completion_tokens', 0)} | "
            f"Total: {usage.get('total_tokens', 0)}"
        )
        tracer.end_trace(trace_id, step_id, (answer or "")[:100], usage=usage)

        # Auto-escalate: if utility model gave a bad answer, retry with generation
        if prompt_client == self.utility_client and not use_generation:
            # Detect language mismatch: English query → Arabic answer (or vice versa)
            query_has_arabic = bool(re.search(r'[\u0600-\u06FF]', query))
            answer_has_arabic = bool(re.search(r'[\u0600-\u06FF]', answer or ""))
            lang_mismatch = (query_has_arabic and not answer_has_arabic) or (not query_has_arabic and answer_has_arabic)

            is_bad = (
                not answer or not answer.strip()
                or len(answer.strip()) < 20
                or query.lower().strip().startswith(answer.lower().strip()[:15])
                or "only help" in answer.lower()
                or "can't help" in answer.lower()
                or "specialize in" in answer.lower()
                or lang_mismatch
            )
            if is_bad:
                if lang_mismatch:
                    self.logger.info(f"Utility answer language mismatch (query={'ar' if query_has_arabic else 'en'}, answer={'ar' if answer_has_arabic else 'en'}). Escalating.")
                else:
                    self.logger.info(f"Utility answer subpar. Escalating to generation model.")
                gen_system = self.template_parser.get(
                    "rag", "system_prompt", {"persona": persona, "node": node.value}
                )
                gen_chat = [self.generation_client.construct_prompt(prompt=gen_system, role="system")]
                for msg in final_history:
                    gen_chat.append(
                        self.generation_client.construct_prompt(prompt=msg["content"], role=msg["role"])
                    )
                gen_answer = await self.generation_client.generate_text(
                    prompt=footer_prompt, chat_history=gen_chat
                )
                if gen_answer and gen_answer.strip():
                    answer = gen_answer
                    self.logger.info("Escalation succeeded — using generation answer.")
                else:
                    self.logger.warning("Escalation failed — keeping utility answer.")

        # Post-generation language correction: if the model responded in a different
        # language than detected, correct the response language metadata.
        if answer:
            answer_has_arabic = bool(re.search(r'[\u0600-\u06FF]', answer))
            if answer_has_arabic and language != "ar":
                self.logger.info(f"Language correction: '{language}' -> 'ar' (answer contains Arabic)")
                language = "ar"
            elif not answer_has_arabic and language == "ar" and not re.search(r'[\u0600-\u06FF]', query):
                self.logger.info(f"Language correction: 'ar' -> 'en' (query+answer are English)")
                language = "en"

        # Fallback if still empty after primary + potential escalation
        if not answer or not answer.strip():
            fallback_msg = (
                "عذراً، لم أتمكن من إنشاء رد. يرجى إعادة صياغة السؤال."
                if language == "ar"
                else "Sorry, I couldn't generate a response. Please try rephrasing your question."
            )
            answer = fallback_msg

        if self.db_client:
            await self.session_model.append_message(session_id, "user", query, node.value)
            await self.session_model.append_message(session_id, "assistant", answer, node.value)

        try:
            os.makedirs("traces", exist_ok=True)
            with open(f"traces/trace_{trace_id}.json", "w", encoding="utf-8") as f:
                f.write(tracer.export_trace(trace_id))
        except Exception as e:
            self.logger.error(f"Failed to save trace: {e}")

        if sources:
            self.logger.info(f"[RAG SOURCES] {sources}")

        return {
            "answer": answer,
            "node": node.value,
            "language": language,
            "session_id": session_id,
        }


    async def answer_agent_chat_stream(
        self,
        user_id: int,
        project_id: Optional[int],
        query: str,
        persona: str = "student",
        session_id: Optional[int] = None,
        limit: int = 5,
        model_tier: str = "auto",
        language: Optional[str] = None,
        extra_context: Optional[str] = None,
    ):
        # Fast path — history clear
        clear_commands = [
            "clear history", "forget everything", "new topic",
            "نظف السجل", "نسيان السجل", "موضوع جديد",
        ]
        if any(cmd in query.lower() for cmd in clear_commands):
            if self.db_client:
                chat_session = await self.session_model.get_or_create_session(
                    user_id=user_id, project_id=project_id, persona=persona
                )
                await self.session_model.append_message(
                    chat_session.session_id, "system", "History cleared by user."
                )
                sid = chat_session.session_id
            else:
                sid = 0
            lang = "ar" if any("\u0600" <= c <= "\u06FF" for c in query) else "en"
            msg = (
                "تم مسح سجل المحادثة بنجاح!" if lang == "ar"
                else "Chat history cleared successfully!"
            )
            import json as _json
            yield f"data: {_json.dumps({'answer': msg, 'session_id': sid, 'node': 'general', 'language': lang})}\n\n"
            yield "data: [DONE]\n\n"
            return

        chat_history, footer_prompt, session_id, node, language, sources, trace_id, prompt_client, final_history = (
            await self._prepare_chat_context(
                user_id, project_id, query, persona, session_id, limit, model_tier, language=language, extra_context=extra_context
            )
        )

        # Short-circuit: out-of-scope queries never reach the generation LLM.
        if node == WorkflowNodeEnum.OUT_OF_SCOPE:
            answer = (
                "أنا متخصص في التعاون في المشاريع والمهارات المهنية. "
                "هل يمكنني مساعدتك في شيء متعلق بمشروعك؟"
                if language == "ar"
                else "I specialize in project collaboration and professional skills. "
                     "Can I help you with something related to your project?"
            )
            if self.db_client:
                await self.session_model.append_message(session_id, "user", query, node.value)
                await self.session_model.append_message(session_id, "assistant", answer, node.value)
            import json as _json
            yield f"data: {_json.dumps({'node': node.value, 'language': language, 'sources': sources, 'session_id': session_id, 'event': 'meta'})}\n\n"
            yield f"data: {_json.dumps({'text': answer})}\n\n"
            yield "data: [DONE]\n\n"
            return

        # Upgrade to generation model for streaming when there's no project context.
        # Streaming users see every token rendered — utility model (8B) quality is too
        # poor for general conversation. No escalation needed since we start with 70B.
        if prompt_client == self.utility_client and project_id is None and node == WorkflowNodeEnum.GENERAL:
            prompt_client = self.generation_client
            gen_system = self.template_parser.get(
                "rag", "system_prompt", {"persona": persona, "node": node.value}
            )
            chat_history = [
                prompt_client.construct_prompt(prompt=gen_system, role="system")
            ]
            for msg in final_history:
                chat_history.append(
                    prompt_client.construct_prompt(prompt=msg["content"], role=msg["role"])
                )

        metadata_sent = False
        full_answer = ""
        step_id = tracer.start_trace(trace_id, "LLM Generation", {"streaming": True})

        import json as _json
        print(f"[RAG SOURCE] {' / '.join(sources) if sources else 'NONE'}", file=sys.stderr)
        async for chunk in prompt_client.generate_text_stream(
            prompt=footer_prompt, chat_history=chat_history
        ):
            if not metadata_sent:
                metadata = {
                    "node": node.value,
                    "language": language,
                    "session_id": session_id,
                    "trace_id": trace_id,
                    "event": "meta",
                }
                yield f"data: {_json.dumps(metadata)}\n\n"
                metadata_sent = True
            if chunk:
                full_answer += chunk
                yield f"data: {_json.dumps({'text': chunk})}\n\n"

        tracer.end_trace(trace_id, step_id, full_answer)

        # Pipeline summary log
        model_name = getattr(prompt_client, 'generation_model_id', 'unknown')
        self.logger.info(
            f"[RAG PIPELINE] Node: {node.value} | Model: {model_name} | "
            f"Sources: {list(set(sources))} | Lang: {language}"
        )

        try:
            os.makedirs("traces", exist_ok=True)
            with open(f"traces/trace_{trace_id}.json", "w", encoding="utf-8") as f:
                f.write(tracer.export_trace(trace_id))
        except Exception as e:
            self.logger.error(f"Failed to save trace: {e}")

        if self.db_client:
            await self.session_model.append_message(session_id, "user", query, node.value)
            await self.session_model.append_message(session_id, "assistant", full_answer, node.value)

        yield "data: [DONE]\n\n"

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _get_truncated_history(
        self, history: list, total_token_limit: int, encoding=None
    ) -> list:
        """Work backward from the most recent messages within the token budget."""
        truncated = []
        current_tokens = 0
        for msg in reversed(history):
            content = msg.get("content", "")
            msg_tokens = (
                len(encoding.encode(content)) if encoding else len(content) // 4
            )
            if current_tokens + msg_tokens > total_token_limit:
                break
            truncated.insert(0, msg)
            current_tokens += msg_tokens
        return truncated