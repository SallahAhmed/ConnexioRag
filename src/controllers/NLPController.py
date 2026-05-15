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
                reranker=self.reranker,
                backend_client=self.backend_client,  # passed through to ToolManager
            )

    # ------------------------------------------------------------------
    # Collection helpers
    # ------------------------------------------------------------------

    def create_collection_name(self, project_id: str):
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
    ):
        """
        Prepares chat history, retrieves context from all sources, and
        builds the final prompt components ready for generation.
        """
        trace_id = str(uuid.uuid4())
        now = lambda: datetime.now().strftime("%H:%M:%S")
        print(f"\n[AGENT] [{now()}] Query: {query[:50]}...")

        # --- Step 1: Intent & Language ---
        step_id = tracer.start_trace(trace_id, "Intent & Language Detection")
        language = await self.workflow_controller.detect_language(query)
        self.template_parser.set_language(language)
        node = await self.workflow_controller.detect_node(query)
        tracer.end_trace(
            trace_id, step_id,
            {"node": node.value, "language": language},
            usage=self.utility_client.last_usage,
        )
        print(f"[AGENT] [{now()}] Node: {node}")

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

        # Without project context there is nothing to RAG about — cap history
        # at 2 turns (4 messages) to prevent accumulation across unrelated queries.
        if not project_id:
            history = history[-4:] if len(history) > 4 else history

        tracer.end_trace(trace_id, step_id, {"session_id": session_id})

        # --- Token budgeting ---
        try:
            encoding = tiktoken.get_encoding("cl100k_base")
        except Exception:
            encoding = None

        total_token_budget = getattr(self.settings, "TOTAL_CONTEXT_TOKEN_BUDGET", 4000)
        if len(query) < 200:
            total_token_budget = min(total_token_budget, 2500)

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

        # --- Step 3: Knowledge Base Retrieval ---
        retrieved_context = []
        sources = []
        queries_to_search = [query]

        step_id = tracer.start_trace(trace_id, "Knowledge Base Retrieval")
        if node == WorkflowNodeEnum.OUT_OF_SCOPE:
            print(f"[AGENT] [{now()}] Query is OUT OF SCOPE. Skipping retrieval.")
            results = [[]]
        elif not project_id:
            print(f"[AGENT] [{now()}] Searching global KB.")
            search_tasks = [
                self.tool_manager.search_knowledge_base(
                    project_id=0, query=q, limit=limit
                )
                for q in queries_to_search
            ]
            results = await asyncio.gather(*search_tasks)
        else:
            search_tasks = [
                self.tool_manager.search_knowledge_base(
                    project_id=project_id, query=q, limit=limit
                )
                for q in queries_to_search
            ]
            results = await asyncio.gather(*search_tasks)

        # --- Corrective RAG (CRAG) ---
        kb_results = ""
        has_kb_content = False
        for q, res in zip(queries_to_search, results):
            if res:
                kb_results += f"\n[Results for: {q}]\n{res}\n"
                has_kb_content = True

        # Bypass relevance grader for projectless mode — global KB is curated content
        if not has_kb_content:
            is_kb_relevant = False
            kb_usage = {}
        elif not project_id:
            is_kb_relevant = True
            kb_usage = {}
        else:
            is_kb_relevant = await self.workflow_controller.grade_relevance(
                query, kb_results
            )
            kb_usage = self.utility_client.last_usage

        PLATFORM_NODES = {
            WorkflowNodeEnum.ONBOARDING,
            WorkflowNodeEnum.TEAM_FORMATION,
            WorkflowNodeEnum.PHASE_TRANSITION,
        }

        if node == WorkflowNodeEnum.OUT_OF_SCOPE:
            tracer.end_trace(trace_id, step_id, "Skipped (Out of Scope)")

        elif is_kb_relevant:
            retrieved_context.append(kb_results)
            if kb_results.strip():
                sources.append("Documentation")
            tracer.end_trace(
                trace_id, step_id, f"Total Length: {len(kb_results)}", usage=kb_usage
            )

        elif project_id is None:
            # No project context — skip external tools entirely to avoid Wikipedia/Google
            # answering general-knowledge trivia. Let the generation model handle the
            # query using the system prompt guardrails alone.
            tracer.end_trace(trace_id, step_id, "No project context, skipping external tools")

        else:
            # KB was irrelevant/empty and we have a project context → CRAG fallback
            tracer.end_trace(
                trace_id, step_id, "Irrelevant/Empty (Fallback Triggered)", usage=kb_usage
            )

            if node in PLATFORM_NODES and not has_kb_content:
                print(f"[AGENT] [{now()}] Platform node with empty KB. Using canned response.")
                if language == "ar":
                    retrieved_context.append(
                        "\n[Platform Guide]: لا تتوفر لديّ وثائق منصة محددة حول هذا "
                        "الموضوع بعد. يُرجى الرجوع إلى أدلة منصة Connexio."
                    )
                else:
                    retrieved_context.append(
                        "\n[Platform Guide]: I don't have specific Connexio platform "
                        "documentation on this topic yet. Please check the Connexio "
                        "platform guides or contact your project supervisor."
                    )
                sources.append("Platform Guide")
            else:
                # Decision: pick the best external tool
                decision_prompt = (
                    f'Analyze the user query: "{query}" and select the single best tool.\n'
                    '- "WIKIPEDIA": General knowledge, history, science, definitions.\n'
                    '- "GOOGLE": News, recent events, technical stats, product info.\n'
                    '- "GITHUB": Searching repositories, finding open-source files.\n'
                    '- "PYTHON": Executing code snippets, math, logic, data processing.\n'
                    '- "NONE": Conversational or no tool needed.\n'
                    "Return ONLY one word."
                )
                choice = await self.utility_client.generate_text(prompt=decision_prompt)
                choice = choice.strip().upper() if choice else "NONE"

                if "GITHUB" in choice:
                    step_id_gh = tracer.start_trace(trace_id, "GitHub Tool Search")
                    refine = (
                        f"Extract the GitHub repo name (owner/repo) and mode "
                        f"('summary','commits','issues') from: {query}. "
                        "Return ONLY JSON: {\"repo\": \"...\", \"mode\": \"...\"}"
                    )
                    gh_raw = await self.utility_client.generate_text(
                        prompt=refine, chat_history=utility_history
                    )
                    try:
                        gh_info = json.loads(
                            gh_raw.strip().replace("```json", "").replace("```", "")
                        )
                        repo = gh_info.get("repo", "")
                        if repo and "/" in repo:
                            gh_result = await self.tool_manager.fetch_github_data(
                                repo_name=repo, mode=gh_info.get("mode", "summary")
                            )
                        else:
                            gh_result = "No specific GitHub repository was identified."
                    except Exception:
                        gh_result = "Error parsing GitHub request."
                    retrieved_context.append(f"\n[GitHub Repository Data]:\n{gh_result}")
                    sources.append("GitHub")
                    tracer.end_trace(trace_id, step_id_gh, gh_result[:50], usage=self.utility_client.last_usage)

                elif "PYTHON" in choice:
                    step_id_py = tracer.start_trace(trace_id, "Python Interpreter Execution")
                    py_prompt = (
                        f"Write a short Python script to solve: {query}. "
                        "Return ONLY the code block."
                    )
                    py_code = await self.utility_client.generate_text(prompt=py_prompt)
                    py_result = await self.tool_manager.execute_python(code=py_code)
                    retrieved_context.append(f"\n[Python Execution Result]:\n{py_result}")
                    sources.append("Python Interpreter")
                    tracer.end_trace(trace_id, step_id_py, f"Length: {len(py_result)}", usage=self.utility_client.last_usage)

                elif "GOOGLE" in choice:
                    step_id_web = tracer.start_trace(trace_id, "Google Search Fallback")
                    refine = f"Create a 3-word Google search query for: {query}. Return ONLY the query."
                    refined = await self.utility_client.generate_text(
                        prompt=refine, chat_history=utility_history
                    )
                    refined = (refined or query).strip().strip('"').strip("'")
                    web_result = await self.tool_manager.search_google(query=refined)
                    retrieved_context.append(f"\n[Live Web Search (Google)]:\n{web_result}")
                    sources.append("Google Search")
                    tracer.end_trace(trace_id, step_id_web, f"Length: {len(web_result)}", usage=self.utility_client.last_usage)

                elif "WIKIPEDIA" in choice:
                    step_id_wiki = tracer.start_trace(trace_id, "Wikipedia Fallback Search")
                    refine = f"Search Wikipedia for: {query}. Return ONLY the main subject name."
                    refined = await self.utility_client.generate_text(
                        prompt=refine, chat_history=utility_history
                    )
                    refined = (refined or query).strip().strip('"').strip("'")
                    wiki_result = await self.tool_manager.search_wiki(
                        query=refined, lang=language
                    )
                    if wiki_result and "Unable to perform" not in wiki_result:
                        retrieved_context.append(
                            f"\n[Global Knowledge (Wikipedia)]:\n{wiki_result}"
                        )
                        sources.append("Wikipedia")
                    else:
                        retrieved_context.append(
                            "\n[Global Knowledge]: No external information found."
                        )
                    tracer.end_trace(trace_id, step_id_wiki, f"Length: {len(wiki_result)}", usage=self.utility_client.last_usage)

                else:
                    retrieved_context.append(
                        "\n[Global Knowledge]: No relevant information found in project domain."
                    )

        # --- Live backend context injection (project summary from main backend) ---
        if project_id and self.backend_client and node not in (WorkflowNodeEnum.OUT_OF_SCOPE,):
            try:
                live_summary = await self.tool_manager.get_project_context_summary(
                    project_id=project_id
                )
                if live_summary:
                    retrieved_context.append(f"\n[Live Project Data]:\n{live_summary}")
                    sources.append("Live Backend Data")
            except Exception as e:
                self.logger.warning(f"Could not fetch live project context: {e}")

        # --- Step 4: Final Prompt Construction ---
        self.template_parser.set_language(language)

        # Decide which model to use based on model_tier and project context
        use_generation = (
            model_tier == "generation"
            or (model_tier == "auto" and project_id is not None)
        )

        if use_generation:
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
            domain_rule = (
                "إذا كان السؤال عن الطعام، الطقس، السياسة، الرياضة، المشاهير، "
                "الجغرافيا، التاريخ، أو معلومات عامة غير متعلقة بالمشاريع، "
                "فارفض الإجابة بلطف واذكر أنك متخصص في التعاون في المشاريع فقط."
                if language == "ar"
                else "If the question is about food, weather, politics, sports, celebrities, "
                     "geography, history, general trivia, or subjective opinions ('best', "
                     "'most brilliant', 'top') — politely refuse and state you only "
                     "help with project collaboration topics."
            )
            system_prompt = (
                f"أنت Connexio AI، مساعد تعاون في المشاريع. الشخصية: {persona}. "
                f"{guide} {domain_rule} كن موجزاً ومفيداً. لا تستخدم رؤوس markdown."
                if language == "ar"
                else f"You are Connexio AI, a project collaboration assistant. "
                     f"Persona: {persona}. {guide} {domain_rule} "
                     f"Be concise and helpful. Do not use markdown headers."
            )
            prompt_client = self.utility_client

        context_string = "\n\n".join(retrieved_context)

        base_tokens = count_tokens(system_prompt) + count_tokens(context_string)
        history_budget = total_token_budget - base_tokens - 200
        final_history = self._get_truncated_history(history, history_budget, encoding)

        footer_prompt = self.template_parser.get(
            "rag", "footer_prompt", {"query": query, "context": context_string}
        )

        chat_history = [
            prompt_client.construct_prompt(prompt=system_prompt, role="system")
        ]
        for msg in final_history:
            chat_history.append(
                prompt_client.construct_prompt(
                    prompt=msg["content"], role=msg["role"]
                )
            )

        return chat_history, footer_prompt, session_id, node, language, list(set(sources)), trace_id, prompt_client

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
    ):
        self.logger.info(f"answer_agent_chat called with model_tier={model_tier}")
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

        chat_history, footer_prompt, session_id, node, language, sources, trace_id, prompt_client = (
            await self._prepare_chat_context(
                user_id, project_id, query, persona, session_id, limit, model_tier
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
            return {
                "answer": answer,
                "node": node.value,
                "language": language,
                "sources": [],
                "session_id": session_id,
            }

        step_id = tracer.start_trace(trace_id, "LLM Generation", {"streaming": False})
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

        if not answer or not answer.strip():
            self.logger.warning("Primary model returned empty response. Retrying with utility model.")
            fallback_history = [
                self.utility_client.construct_prompt(prompt=system_prompt, role="system")
            ]
            for msg in final_history:
                fallback_history.append(
                    self.utility_client.construct_prompt(prompt=msg["content"], role=msg["role"])
                )
            answer = await self.utility_client.generate_text(
                prompt=footer_prompt, chat_history=fallback_history
            )

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

        return {
            "answer": answer,
            "node": node.value,
            "language": language,
            "sources": sources,
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

        chat_history, footer_prompt, session_id, node, language, sources, trace_id, prompt_client = (
            await self._prepare_chat_context(
                user_id, project_id, query, persona, session_id, limit, model_tier
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
            yield f"data: {_json.dumps({'node': node.value, 'language': language, 'sources': [], 'session_id': session_id, 'event': 'meta'})}\n\n"
            yield f"data: {_json.dumps({'text': answer})}\n\n"
            yield "data: [DONE]\n\n"
            return

        metadata_sent = False
        full_answer = ""
        step_id = tracer.start_trace(trace_id, "LLM Generation", {"streaming": True})

        import json as _json
        async for chunk in prompt_client.generate_text_stream(
            prompt=footer_prompt, chat_history=chat_history
        ):
            if not metadata_sent:
                metadata = {
                    "node": node.value,
                    "language": language,
                    "sources": sources,
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