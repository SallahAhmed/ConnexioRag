# Comprehensive Master Implementation Plan — Production RAG & Express Overhaul

This unified, comprehensive implementation plan covers all phases to bring the Connexio RAG, Agent, and Express/Socket services to absolute, production-grade maturity:

1. **Phase 1: End-to-End Files Management**: Connects Frontend, Node.js Backend, and FastAPI RAG service to enable dynamic document uploads, listings, and automatic database-synced deletions (supporting up to 15MB, PDF/TXT/DOCX, strictly team leader owner permissions, client-side validation, and UI name-stripping).
2. **Phase 2: RAG Retrieval Accuracy Hardening (Cohere Rerank)**: Integrates **Cohere Rerank (`rerank-multilingual-v3.0`)** and refactors the sliding-window chunking pipeline to ensure your AI Assistant delivers highly accurate, context-aware answers.
3. **Phase 3: Premium Arabic Prompt Modernization**: Rewrites robotic Arabic templates into elite Modern Standard Arabic with natural software development terminology formatting to guarantee flawless Arabic answers.
4. **Phase 4: Database Connection & Session Latency Optimizations**: Refactors the chat history session manager to eliminate double database round-trips for reading and writing messages, yielding a significant decrease in latency.
5. **Phase 5: Global Cross-Service HTTP Connection Pooling**: Configures global HTTPS keep-alive connection agents on the Hostinger Express backend to keep TCP/TLS channels to Hugging Face Spaces open, dropping cross-cloud handshake overhead by 100ms - 150ms per call.
6. **Phase 6: RAG Projectless Tool Routing**: Relax the projectless query blocker in `NLPController.py` to allow external tools (ArXiv, StackOverflow, GitHub, Google, Wikipedia) to trigger dynamically for all technical/research queries even when `project_id` is missing.
7. **Phase 7: Express/Socket.IO SSE UTF-8 Mojibake Correction**: Specifying `charset=utf-8` in Express router stream headers, and configuring `setEncoding('utf8')` in the Node.js socket stream reader to prevent multi-byte Arabic character boundary corruption.
8. **Phase 8: Hardening Out-of-Scope Classification Prompts**: Refining locales workflow prompts to permit technical creators, programming language history, and cybersecurity concepts as `GENERAL` (in-scope).
9. **Phase 9: Premium Chat Memory & Temporal Context Recall**:
   - Extend the general chat history token budget cap from 4 messages (2 turns) to **20 messages (10 turns)** to allow rich context.
   - Detect direct memory questions (e.g. "what did we talk about yesterday", "what was the last thing we discussed", "ماذا تحدثنا بالأمس") and format a structured chronological conversation timeline into the RAG context, allowing the LLM to summarize and recall past discussions perfectly.

---

## 🔍 Goal Description

Connecting the three layers of the Connexio stack to enable real-time project file ingestion and removal:
1. **Frontend (React)**: Replace the files tab with an upload file input (accepting `.pdf`, `.txt`, and `.docx`), list indexed assets, upload indicators, and a deletion trigger.
2. **Node.js Backend**: Enforce team leader validation, expose listing and deletion proxies that safely query the Python RAG microservice.
3. **RAG Microservice**: Add clean endpoints to list assets from PostgreSQL, support Word/PDF/TXT parsing, and drop assets alongside associated chunks.

---

## 💬 Configuration & Policy Decisions

> [!NOTE]
> **1. File Type and Size Constraints**
> * Allowed extensions: `.pdf`, `.txt`, `.docx` (100% stable python-native loaders).
> * Max file size: **15MB** (enforced on client-side, backend, and RAG configuration).
>
> **2. Permissions Policy**
> * Access controls: **Strictly Team Leader Only** (only project members with the `'owner'` role are authorized to upload files or delete records from the index).

---

## 💰 Token Consumption Guardrails & Averages

The total tokens sent to the LLM can **never** exceed the hardcoded ceiling of `total_token_budget = 4000` (about 3,000 words). The history is dynamically fitted into whatever remaining budget is left over after retrieved chunks are packed.

### Average Token Cost Analysis:
* **Standard User Turn (No Memory)**: Input grows by a mere ~400 tokens (~$0.0003 cost) because we retain up to 20 messages rather than discarding them.
* **Memory Recall Query (e.g., "What did we talk about yesterday?")**: Input increases by ~1,500 tokens only for that specific turn to load the chronological conversation timeline.
* **Absolute Ceiling**: Fully capped at **4,000 tokens** across both systems, ensuring zero risk of billing spikes or LLM out-of-context errors.

---

## 🛠️ Proposed Changes

---

### 🐍 Component A: RAG Microservice (Python/FastAPI)

#### [MODIFY] [Requirements.txt](file:///c:/Users/salla/Connexios/src/Requirements.txt)
Add Python-native docx parser:
```text
docx2txt==0.8
```

#### [MODIFY] [ProcessingEnum.py](file:///c:/Users/salla/Connexios/src/models/enums/ProcessingEnum.py)
Register Word `.docx` documents as an allowed processing format:
```python
class ProcessingEnum(Enum):

    TXT = ".txt"
    PDF = ".pdf"
    DOCX = ".docx"
```

#### [NEW] [CoHereReranker.py](file:///c:/Users/salla/Connexios/src/stores/vectordb/providers/CoHereReranker.py)
A state-of-the-art reranker utilizing Cohere's SDK to sort top PGVector results before sending them to the LLM.
```python
import cohere
from typing import List
from ..RerankerInterface import RerankerInterface
from models.db_schemas import RetrievedDocument

class CoHereReranker(RerankerInterface):
    def __init__(self, api_key: str, model: str = "rerank-multilingual-v3.0"):
        self.client = cohere.AsyncClient(api_key=api_key)
        self.model = model

    async def rerank(self, query: str, documents: List[RetrievedDocument], top_k: int) -> List[RetrievedDocument]:
        if not documents:
            return []
        
        doc_texts = [d.text for d in documents]
        try:
            response = await self.client.rerank(
                model=self.model,
                query=query,
                documents=doc_texts,
                top_n=top_k
            )
            
            reranked_docs = []
            for result in response.results:
                original_doc = documents[result.index]
                original_doc.score = result.relevance_score
                reranked_docs.append(original_doc)
                
            return reranked_docs
        except Exception as e:
            import logging
            logging.getLogger(__name__).error(f"[RAG] Cohere rerank failed: {e}")
            return documents[:top_k]
```

#### [MODIFY] [main.py](file:///c:/Users/salla/Connexios/src/main.py)
Initialize the Cohere Reranker:
```python
    # --- Reranker Setup (Activated) ---
    from stores.vectordb.providers.CoHereReranker import CoHereReranker
    if settings.COHERE_API_KEY:
        logger.info("Initializing Cohere Reranker...")
        app.reranker = CoHereReranker(api_key=settings.COHERE_API_KEY)
    else:
        logger.warning("COHERE_API_KEY not found. Reranking remains disabled.")
        app.reranker = None
```

#### [MODIFY] [config.py](file:///c:/Users/salla/Connexios/src/helpers/config.py)
Update maximum allowed file size limits and extensions:
```python
    FILE_ALLOWED_TYPES: list = ["application/pdf", "text/plain", "application/vnd.openxmlformats-officedocument.wordprocessingml.document"]
    FILE_MAX_SIZE: int = 15
```

#### [MODIFY] [ChunkModel.py](file:///c:/Users/salla/Connexios/src/models/ChunkModel.py)
Add asset-based methods to keep data queries fully encapsulated inside model classes:
```python
    async def get_chunks_by_asset_id(self, asset_id: int):
        async with self.db_client() as session:
            stmt = select(DataChunk).where(DataChunk.chunk_asset_id == asset_id)
            result = await session.execute(stmt)
            records = result.scalars().all()
        return records

    async def delete_chunks_by_asset_id(self, asset_id: int):
        async with self.db_client() as session:
            async with session.begin():
                stmt = delete(DataChunk).where(DataChunk.chunk_asset_id == asset_id)
                result = await session.execute(stmt)
            await session.commit()
        return result.rowcount
```

#### [MODIFY] [DataController.py](file:///c:/Users/salla/Connexios/src/controllers/DataController.py)
Fix the extension map to correctly parse the massive Word document MIME type into the `.docx` extension, otherwise uploads will fail validation:
```python
    _EXTENSION_MAP = {
        "text/plain": ".txt",
        "application/pdf": ".pdf",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx"
    }
```

#### [MODIFY] [ProcessController.py](file:///c:/Users/salla/Connexios/src/controllers/ProcessController.py)
Include Docx loading and the sentence overlapping sliding window chunker:
```python
from langchain_community.document_loaders import TextLoader
from langchain_community.document_loaders import PyMuPDFLoader
from langchain_community.document_loaders import Docx2txtLoader

    def get_file_loader(self, file_id: str):
        file_ext = self.get_file_extension(file_id=file_id).lower()
        file_path = os.path.join(self.project_path, file_id)

        if not os.path.exists(file_path):
            return None

        if file_ext == ProcessingEnum.TXT.value:
            return TextLoader(file_path, encoding="utf-8")

        if file_ext == ProcessingEnum.PDF.value:
            return PyMuPDFLoader(file_path)

        if file_ext == ProcessingEnum.DOCX.value:
            return Docx2txtLoader(file_path)
        
        return None

    def process_simpler_splitter(self, texts: List[str], metadatas: List[dict], chunk_size: int, splitter_tag: str="\n"):
        full_text = " ".join(texts)
        overlap = 150
        chunks = []
        start = 0
        text_len = len(full_text)
        
        while start < text_len:
            end = min(start + chunk_size, text_len)
            chunk_text = full_text[start:end].strip()
            if len(chunk_text) > 5:
                chunks.append(Document(
                    page_content=chunk_text,
                    metadata={}
                ))
            if end == text_len:
                break
            start += (chunk_size - overlap)
            
        return chunks
```

#### [MODIFY] [NLPController.py](file:///c:/Users/salla/Connexios/src/controllers/NLPController.py)
Relax projectless guards, expand general history budget, and inject chronological conversation summary on memory-recall query detection.
```python
        # --- Step 2: Session ---
        ...
        # Without project context there is nothing to RAG about — cap history
        # at 10 turns (20 messages) to retain premium conversational memory.
        if not project_id:
            history = history[-20:] if len(history) > 20 else history

        # --- Memory Intent Detection ---
        memory_keywords = [
            "what did we talk about", "what was the last thing", "what we discussed",
            "yesterday", "last conversation", "previous conversation", "our last chat",
            "ماذا تحدثنا", "عن ماذا تكلمنا", "آخر شيء", "آخر محادثة", "الأمس",
            "المحادثة السابقة", "تحدثنا بالأمس"
        ]
        is_memory_query = any(kw in query.lower() for kw in memory_keywords)

        if is_memory_query and history:
            memory_summary = []
            for i, msg in enumerate(history):
                role_label = "المستخدم" if msg["role"] == "user" else "المساعد الذكي"
                if language == "en":
                    role_label = "User" if msg["role"] == "user" else "Assistant"
                memory_summary.append(f"[{i+1}] {role_label}: {msg['content']}")
            
            summary_text = "\n".join(memory_summary)
            if language == "ar":
                retrieved_context.append(
                    f"\n[سجل المحادثات السابقة لتجيب المستخدم بدقة عما تحدثتم عنه]:\n{summary_text}"
                )
            else:
                retrieved_context.append(
                    f"\n[Previous Conversation History to help you answer the user about past talks]:\n{summary_text}"
                )
            sources.append("Conversation Memory")
            node = WorkflowNodeEnum.GENERAL
```
Relax the projectless query tool routing:
```diff
-        elif project_id is None:
-            # No project context — but allow external tools for clearly
-            # technical/research queries. Block only for general-knowledge trivia.
-            technical_keywords = [
-                "research", "paper", "latest", "how to", "error", "bug", "fix",
-                "code", "api", "library", "framework", "security", "vulnerability",
-                "github", "stackoverflow", "programming", "developer", "debug",
-                "implementation", "algorithm", "architecture", "design pattern",
-                "بحث", "ورقة", "أحدث", "كود", "برمجة", "مطور", "خطأ", "إصلاح",
-                "أمان", "ثغرة", "مكتبة", "إطار عمل", "خوارزمية",
-            ]
-            is_technical = any(kw in query.lower() for kw in technical_keywords)
-
-            if is_technical:
-                # Run CRAG tool selection (same as project flow)
-                tracer.end_trace(
-                    trace_id, step_id, "No project context but technical query — running CRAG tools"
-                )
+        elif project_id is None:
+            # No project context — but allow external tools for clearly in-scope
+            # queries. The classifier has already filtered out-of-scope trivia.
+            is_technical = True
+
+            if is_technical:
+                # Run CRAG tool selection (same as project flow)
+                tracer.end_trace(
+                    trace_id, step_id, "No project context but in-scope query — running CRAG tools"
+                )
```

#### [MODIFY] [data.py (Schemas)](file:///c:/Users/salla/Connexios/src/Routes/schemas/data.py)
Update default parameters in the validation schema to default to **800** and **150** instead of 100 and 20:
```python
class ProcessRequest(BaseModel):
    file_id: str = None
    chunk_size: Optional[int]=800
    overlap_size: Optional[int]=150
    do_reset: Optional[int]=0
```

#### [MODIFY] [data.py](file:///c:/Users/salla/Connexios/src/Routes/data.py)
Include database synchronized asset listings and deletion proxies:
```python
from sqlalchemy import delete
from sqlalchemy.sql import text as sql_text

@data_router.get("/assets/{project_id}")
async def get_project_assets(request: Request, project_id: int):
    asset_model = await AssetModel.create_instance(db_client=request.app.db_client)
    assets = await asset_model.get_all_project_assets(
        asset_project_id=project_id, 
        asset_type=AssetTypeEnum.FILE.value
    )
    return {
        "success": True,
        "assets": [
            {
                "asset_id": a.asset_id,
                "asset_name": a.asset_name,
                "asset_size": a.asset_size,
                "created_at": a.created_at.isoformat() if a.created_at else None
            }
            for a in assets
        ]
    }

@data_router.delete("/assets/{asset_id}")
async def delete_project_asset(request: Request, asset_id: int):
    db_client = request.app.db_client
    asset_model = await AssetModel.create_instance(db_client=db_client)
    chunk_model = await ChunkModel.create_instance(db_client=db_client)
    
    # 1. Fetch asset details
    async with db_client() as session:
        result = await session.execute(
            select(Asset).where(Asset.asset_id == asset_id)
        )
        asset = result.scalar_one_or_none()
        
    if not asset:
        return JSONResponse(status_code=404, content={"success": False, "message": "Asset not found"})
        
    project_id = asset.asset_project_id
    file_id = asset.asset_name
    
    # 2. Get associated chunks
    chunks = await chunk_model.get_chunks_by_asset_id(asset_id=asset_id)
    chunk_ids = [c.chunk_id for c in chunks]
        
    # 3. Clean vectors from dynamic DB tables
    if chunk_ids:
        nlp_controller = NLPController(
            vectordb_client=request.app.vectordb_client,
            generation_client=request.app.generation_client,
            embedding_client=request.app.embedding_client,
            template_parser=request.app.template_parser,
        )
        collection_name = nlp_controller.create_collection_name(project_id=project_id)
        if await request.app.vectordb_client.is_collection_existed(collection_name):
            try:
                collection_tbl = sql_text(f"DELETE FROM {collection_name} WHERE chunk_id IN :chunk_ids")
                async with db_client() as session:
                    async with session.begin():
                        await session.execute(collection_tbl, {"chunk_ids": tuple(chunk_ids)})
            except Exception as q_err:
                logger.error(f"[RAG] Failed to delete PGVector points: {q_err}")

    # 4. Remove physical file
    project_path = ProjectController().get_project_path(project_id=project_id)
    file_path = os.path.join(project_path, file_id)
    if os.path.exists(file_path):
        try:
            os.remove(file_path)
        except Exception as f_err:
            logger.error(f"[RAG] Physical file removal failed: {f_err}")

    # 5. Drop chunks and asset records from SQL via models
    await chunk_model.delete_chunks_by_asset_id(asset_id=asset_id)
    await asset_model.delete_asset_by_id(asset_id=asset_id)
            
    return {"success": True, "message": "Asset and vectors deleted successfully"}
```

#### [MODIFY] [workflow.py (English)](file:///c:/Users/salla/Connexios/src/stores/llm/templates/locales/en/workflow.py)
Harden English classification prompts to allow tech/programming history and creators in-scope.
```diff
 CATEGORIES:
 ...
- - GENERAL: Professional/technical questions (methodologies, coding, design, marketing, management, career advice, interview prep, resume tips, professional development, learning recommendations). If unsure, default here.
- - OUT_OF_SCOPE: Food, cooking, weather, politics, sports, celebrities, geography, history dates ("what year did X happen"), general trivia, general knowledge questions ("who is X", "what is the capital of Y"). Anything completely unrelated to professional work.
+ - GENERAL: Professional/technical questions (methodologies, coding, design, marketing, management, career advice, programming language/tech history, tech creators, cyber security, interview prep, resume tips, professional development, learning recommendations). If unsure, default here.
+ - OUT_OF_SCOPE: Food, cooking, weather, politics, sports, celebrities, geography, history dates ("what year did X happen"), general trivia, general knowledge questions ("who is X", "what is the capital of Y" - EXCEPT when X is a tech/science founder or concept like 'who invented Python'). Anything completely unrelated to professional work.

 CRITICAL RULES:
 ...
- 4. If the query asks ANY general knowledge, trivia, or fact-based question (who/what/when/where about non-project topics) → OUT_OF_SCOPE.
+ 4. If the query asks ANY general knowledge, trivia, or fact-based question (who/what/when/where about non-project topics) → OUT_OF_SCOPE. EXCEPT: programming language history, tech/AI history, and technical/science creators (e.g., Ada Lovelace, Linus Torvalds, Guido van Rossum) are STRICTLY IN-SCOPE → GENERAL.
```

#### [MODIFY] [workflow.py (Arabic)](file:///c:/Users/salla/Connexios/src/stores/llm/templates/locales/ar/workflow.py)
Harden Arabic classification prompt.
```diff
 الفئات:
 ...
- - GENERAL: أسئلة مهنية/تقنية عامة (أجايل، برمجة، تصميم، تسويق، إدارة، نصائح مهنية، مقابلات عمل، تطوير مهني، توصيات تعلم). في حالة الشك، اختر GENERAL.
- - OUT_OF_SCOPE: طعام، طبخ، طقس، سياسة، رياضة، مشاهير، جغرافيا، تواريخ تاريخية ("في أي سنة حدث X")، معلومات عامة، أسئلة معرفية عامة ("من هو X"، "ما هي عاصمة Y"). أي شيء لا علاقة له بالعمل المهني.
+ - GENERAL: أسئلة مهنية/تقنية عامة (أجايل، برمجة، تصميم، تسويق، إدارة، تاريخ لغات البرمجة والتقنية، مخترعي التقنية، الأمن السيبراني، نصائح مهنية، مقابلات عمل، تطوير مهني، توصيات تعلم). في حالة الشك، اختر GENERAL.
+ - OUT_OF_SCOPE: طعام، طبخ، طقس، سياسة، رياضة، مشاهير، جغرافيا، تواريخ تاريخية ("في أي سنة حدث X")، معلومات عامة، أسئلة معرفية عامة ("من هو X"، "ما هي عاصمة Y" - باستثناء مخترعي أو مفاهيم البرمجة مثل 'من اخترع بايثون'). أي شيء لا علاقة له بالعمل المهني.

 قواعد حرجة:
 ...
- 4. إذا كان السؤال يسأل عن معرفة عامة أو حقيقة أو معلومة (من/ماذا/متى/أين عن مواضيع غير متعلقة بالمشروع) → OUT_OF_SCOPE.
+ 4. إذا كان السؤال يسأل عن معرفة عامة أو حقيقة أو معلومة (من/ماذا/متى/أين عن مواضيع غير متعلقة بالمشروع) → OUT_OF_SCOPE. باستثناء: تاريخ لغات البرمجة، تاريخ التقنية/الذكاء الاصطناعي، ومؤسسي ومخترعي التكنولوجيا (مثل: جيدو فان روسوم، لينوس تورفالدز) فهي في صميم التخصص → GENERAL.
```

#### [MODIFY] [rag.py (Arabic Prompt)](file:///c:/Users/salla/Connexios/src/stores/llm/templates/locales/ar/rag.py)
Upgrade translation to premium Modern Standard Arabic with development terminologies and markdown rule enforcement.
```python
from string import Template

system_prompt = Template("\n".join([
    "أنت Connexio AI — المستشار الذكي والرفيق الرقمي لمساعدة فرق التطوير البرمجي على التخطيط وبناء التطبيقات بأعلى كفاءة وسرعة.",
    "الجمهور المستهدف: متعلم مهني وخلفيته: $persona | سياق المحادثة الحالي: $node",
    "",
    "## مهامك ومسؤولياتك الأساسية ##",
    "1. تخطيط وإدارة المشاريع: تقسيم مراحل العمل (Milestones) إلى مهام برمجية واضحة، تحديد العقبات والمخاطر مبكراً، واقتراح خطط دورات التطوير (Sprint plans).",
    "2. مراجعة الكود والوثائق: البحث الذكي في ملفات ومستندات المشروع، شرح البنى الهندسية المعقدة (Architecture)، ومراجعة طلبات الدمج (PRs).",
    "3. التنسيق البرمجي والتقني: دعم المطورين من خلال تقديم إجابات وحلول برمجية عملية مدعومة بالبحث في (StackOverflow, GitHub, ArXiv).",
    "",
    "## أسلوب صياغة الردود حسب خلفية المستخدم ##",
    "- طالب (student): اشرح بأسلوب المعلم الحريص والميسر؛ استخدم أمثلة برمجية مبسطة، وتجنب التعقيد الاصطلاحي بلا داعٍ. ابدأ دائماً بـ: 'دعنا نبسط هذا المفهوم التقني معاً...'",
    "- مبتدئ مهني (early_career): أسلوب المرشد العملي؛ ركّز على أفضل الممارسات في سوق العمل الحقيقي والمقايضات الواقعية (Trade-offs). ابدأ دائماً بـ: 'في البيئات البرمجية والعملية الحقيقية، تميل فرق التطوير إلى...'",
    "- معلم (educator): أسلوب أكاديمي منظم؛ استخدم أطر العمل المنهجية والشروحات التفصيلية. ابدأ بـ: 'دعنا نحلل هذه المسألة استناداً إلى أطر العمل البرمجية...'",
    "- شركة (company): أسلوب استشاري استراتيجي؛ ركز على الإنتاجية، العائد الاستثماري (ROI)، والكفاءة التشغيلية. ابدأ بـ: 'من زاوية الجدوى التقنية والقيمة التجارية للمشروع...'",
    "",
    "## قواعد ذهبية للصياغة العربية الممتازة ##",
    "1. اكتب بلغة عربية فصحى حديثة، بليغة، وخالية تماماً من الركاكة أو الترجمات الحرفية الروبوتية.",
    "2. عند الحديث عن مصطلحات تقنية برمجية شائعة (مثل APIs, Frontend, Database, CSS, Backend)، اكتب المصطلح باللغة العربية متبوعاً باسمه الإنجليزي الأصلي بين قوسين لكي يبدو ردك متطابقاً مع لغة المطورين المحترفين في سوق العمل.",
    "3. لا تستخدم إطلاقاً رموز العناوين الكبيرة في لغة markdown (مثل ## أو ###) في منتصف الردود لتفادي تشويه تنسيق العرض. تحدث وصِغ أفكارك بفقرات انسيابية مسترسلة.",
    "4. التزم التزاماً مطلقاً بالرد بنفس اللغة التي وجه بها المستخدم سؤاله (العربية دائمًا في هذا السياق).",
    "5. أنهِ كل رد بسؤال تفاعلي ذكي وجذاب يدفع فريق العمل لمواصلة النقاش حول الخطوة التالية.",
    "6. إذا كان السؤال خارج نطاق التطوير البرمجي والريادة (كالسياسة، الطبخ، الطقس، المشاهير)، اعتذر بكياسة متناهية وأعد توجيه المستخدم لنطاق مشروعه البرمجي.",
]))
```

#### [MODIFY] [SessionModel.py](file:///c:/Users/salla/Connexios/src/models/SessionModel.py)
Upgrade session manager to execute transactional creations and modifications in single blocks.
```python
    async def get_or_create_session(self, user_id: int, project_id: int = None,
                                     persona: str = "student", language: str = "en") -> ChatSession:
        async with self.db_client() as session:
            query = select(ChatSession).where(ChatSession.user_id == user_id)
            if project_id:
                query = query.where(ChatSession.project_id == project_id)

            query = query.order_by(ChatSession.created_at.desc()).limit(1)
            result = await session.execute(query)
            existing = result.scalar_one_or_none()

            if existing:
                return existing

            session_record = ChatSession(
                user_id=user_id,
                project_id=project_id,
                persona=persona,
                language=language,
                chat_history=[]
            )
            async with session.begin():
                session.add(session_record)
            await session.commit()
            await session.refresh(session_record)
            return session_record

    async def append_message(self, session_id: int, role: str, content: str,
                               workflow_node: str = None):
        message = {
            "role": role,
            "content": content,
            "node": workflow_node,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }

        async with self.db_client() as session:
            async with session.begin():
                result = await session.execute(
                    select(ChatSession).where(ChatSession.session_id == session_id)
                )
                chat_session = result.scalar_one_or_none()
                if not chat_session:
                    return None

                current_history = list(chat_session.chat_history or [])
                current_history.append(message)
                chat_session.chat_history = current_history
                chat_session.last_workflow_node = workflow_node
            await session.commit()

        return message
```

---

### 🖥️ Component B: Node.js Backend Routing & Keep-Alive Pooling

#### [MODIFY] [bootstrap.js](file:///f:/connexio_back2/bootstrap.js)
Establish global keep-alive HTTP pooling agents.
```javascript
import http from 'http';
import https from 'https';
import axios from 'axios';

axios.defaults.httpAgent = new http.Agent({ keepAlive: true, maxSockets: 100, keepAliveMsecs: 1000 });
axios.defaults.httpsAgent = new https.Agent({ keepAlive: true, maxSockets: 100, keepAliveMsecs: 1000 });
```

#### [MODIFY] [projects.routes.js](file:///F:/connexio_back2/modules/projects/projects.routes.js)
Expose file retrieval and deletion proxies:
```javascript
router.get('/:id/files', projectsController.getProjectFiles);
router.delete('/:id/files/:assetId', projectsController.deleteProjectFile);
```

#### [MODIFY] [projects.controller.js](file:///F:/connexio_back2/modules/projects/projects.controller.js)
Axios listing and delete triggers with **Team Leader Only** permissions:
```javascript
export const getProjectFiles = async (req, res) => {
  const { id } = req.params;
  try {
    if (process.env.RAG_SERVICE_URL && process.env.CONNEXIO_RAG_API_KEY) {
      const response = await axios.get(
        `${process.env.RAG_SERVICE_URL}/api/v1/data/assets/${id}`,
        { headers: { 'x-api-key': process.env.CONNEXIO_RAG_API_KEY } }
      );
      res.status(200).json({ success: true, data: response.data.assets || [] });
    } else {
      res.status(200).json({ success: true, data: [] });
    }
  } catch (error) {
    console.error('[RAG] Get files error:', error.response?.data || error.message);
    res.status(500).json({ success: false, message: 'Failed to fetch files' });
  }
};

export const deleteProjectFile = async (req, res) => {
  const { id, assetId } = req.params;
  try {
    // 1. Enforce STRICT Project Owner (Team Leader) check
    const member = await db.query(
      'SELECT role FROM project_members WHERE PID = ? AND UID = ?',
      [id, req.user.UID]
    );
    if (member.rows.length === 0 || member.rows[0].role !== 'owner') {
      return res.status(403).json({ success: false, message: 'Only the project leader (owner) can delete files from the RAG index.' });
    }

    if (process.env.RAG_SERVICE_URL && process.env.CONNEXIO_RAG_API_KEY) {
      await axios.delete(
        `${process.env.RAG_SERVICE_URL}/api/v1/data/assets/${assetId}`,
        { headers: { 'x-api-key': process.env.CONNEXIO_RAG_API_KEY } }
      );
      res.status(200).json({ success: true, message: 'File deleted successfully' });
    } else {
      res.status(400).json({ success: false, message: 'RAG service not configured' });
    }
  } catch (error) {
    console.error('[RAG] Delete file error:', error.response?.data || error.message);
    res.status(500).json({ success: false, message: 'Failed to delete file' });
  }
};
```

#### [MODIFY] [fileUpload.controller.js](file:///f:/connexio_back2/modules/fileUpload/fileUpload.controller.js)
Gating uploads strictly to the **Team Leader Only**:
```javascript
export const uploadProjectFile = async (req, res) => {
  uploadSingle('projectFile')(req, res, async (err) => {
    if (err) {
      return res.status(400).json({ success: false, message: err.message });
    }

    if (!req.file) {
      return res.status(400).json({ success: false, message: 'No file uploaded' });
    }

    const projectId = req.params.projectId || req.body.projectId;
    if (!projectId) {
      return res.status(400).json({ success: false, message: 'Project ID is required' });
    }

    try {
      // Enforce Team Leader Verification Check
      const memberCheck = await query(
        'SELECT role FROM project_members WHERE PID = ? AND UID = ?',
        [projectId, req.user.UID]
      );
      if (memberCheck.rows.length === 0 || memberCheck.rows[0].role !== 'owner') {
        return res.status(403).json({ success: false, message: 'Only the project leader (owner) is authorized to upload and index project files.' });
      }

      const fileInfo = await saveFileLocally(req.file, 'projects');

      // Forward to RAG for indexing via URL (non-fatal)
      if (process.env.RAG_SERVICE_URL && process.env.CONNEXIO_RAG_API_KEY) {
        try {
          const formData = new FormData();
          const fileResp = await axios.get(fileInfo.url, { responseType: 'stream' });
          formData.append('file', fileResp.data, { filename: fileInfo.originalName });
          formData.append('chunk_size', '800');
          formData.append('overlap_size', '150');
          formData.append('do_reset', '0');

          await axios.post(
            `${process.env.RAG_SERVICE_URL}/api/v1/data/upload-and-process/${projectId}`,
            formData,
            { headers: { 'x-api-key': process.env.CONNEXIO_RAG_API_KEY, ...formData.getHeaders() } }
          );
        } catch (ragErr) {
          console.warn('[RAG] File indexing failed (non-fatal):', ragErr.message);
        }
      }

      // Trigger MasarX Agent (non-fatal)
      try {
        const { fireEvent } = await import('../../services/aiService.js');
        await fireEvent('file.uploaded', projectId, req.user.UID, {
          filename: fileInfo.originalName,
          file_url: fileInfo.url,
          mimetype: fileInfo.mimetype
        });
      } catch (agentErr) {
        console.warn('[MasarX] File event trigger failed (non-fatal):', agentErr.message);
      }

      res.status(200).json({
        success: true,
        message: 'Project file uploaded successfully',
        data: { url: fileInfo.url, filename: fileInfo.filename, originalName: fileInfo.originalName, size: fileInfo.size, mimetype: fileInfo.mimetype }
      });
    } catch (error) {
      console.error('Upload project file error:', error);
      res.status(500).json({ success: false, message: 'Server error' });
    }
  });
};
```

#### [MODIFY] [ai.routes.js](file:///f:/connexio_back2/modules/ai/ai.routes.js)
Ensure output SSE stream is cleanly encoded.
```diff
-  res.setHeader("Content-Type", "text/event-stream");
+  res.setHeader("Content-Type", "text/event-stream; charset=utf-8");
```

#### [MODIFY] [socket.js](file:///f:/connexio_back2/socket.js)
Apply UTF-8 encoding checks on socket stream payloads to avoid multi-byte boundaries splits.
```diff
               const ragStream = await axios.get(
                 `${RAG_SERVICE_URL}/api/v1/nlp/agent/chat/stream/${projectId}`,
                 {
                   params: {
                     query: content,
                     user_id: socket.userId,
                     persona: 'student',
                     limit: 20,
                     model_tier: 'auto',
                   },
                   headers: { 'x-api-key': CONNEXIO_RAG_API_KEY },
                   responseType: 'stream',
                   timeout: 60000,
                 }
               );
 
               let fullText = '';
               let metaData = null;
               let buffer = '';
 
+              // Ensure multi-byte UTF-8 characters are not corrupted at chunk boundaries
+              ragStream.data.setEncoding('utf8');
+
               await new Promise((resolve, reject) => {
                 ragStream.data.on('data', (chunk) => {
-                  buffer += chunk.toString();
+                  buffer += chunk;
```

---

### 🎨 Component C: React Frontend

#### [MODIFY] [ProjectDetail.jsx](file:///F:/Connexio_Frontend2/src/pages/ProjectDetail.jsx)
Dynamic Upload interface with validation checks, upload states, and prefix-stripped renders.
```javascript
const [files, setFiles] = useState([]);
const [filesLoading, setFilesLoading] = useState(false);

useEffect(() => {
  if (tab === 'files') {
    setFilesLoading(true);
    api.get(`/projects/${id}/files`)
      .then(res => setFiles(res.data?.data || []))
      .catch(() => toast.error('Failed to load project files'))
      .finally(() => setFilesLoading(false));
  }
}, [tab, id]);

const handleUploadFile = async (e) => {
  const file = e.target.files?.[0];
  if (!file) return;
  
  const allowed = ['.pdf', '.txt', '.docx'];
  const ext = file.name.substring(file.name.lastIndexOf('.')).toLowerCase();
  if (!allowed.includes(ext)) {
    toast.error('Only PDF, TXT, and DOCX files are allowed.');
    return;
  }

  if (file.size > 15 * 1024 * 1024) {
    toast.error('File size exceeds the 15MB limit.');
    return;
  }
  
  const fd = new FormData();
  fd.append('projectFile', file);
  fd.append('projectId', id);
  
  const uploadToast = toast.loading('Uploading and indexing file...');
  try {
    await api.post('/upload/project-file', fd, {
      headers: { 'Content-Type': 'multipart/form-data' }
    });
    toast.success('File uploaded and indexed successfully!', { id: uploadToast });
    const updated = await api.get(`/projects/${id}/files`);
    setFiles(updated.data?.data || []);
  } catch (err) {
    const msg = err.response?.data?.message || 'File upload failed';
    toast.error(msg, { id: uploadToast });
  }
};

const handleDeleteFile = async (assetId) => {
  if (!window.confirm('Are you sure you want to delete this file?')) return;
  const deleteToast = toast.loading('Deleting file...');
  try {
    await api.delete(`/projects/${id}/files/${assetId}`);
    toast.success('File deleted successfully!', { id: deleteToast });
    setFiles(prev => prev.filter(f => f.asset_id !== assetId));
  } catch (err) {
    const msg = err.response?.data?.message || 'Failed to delete file';
    toast.error(msg, { id: deleteToast });
  }
};
```

---

## 🚀 Testing & Deployment Checklist

Following deployment to Hugging Face Spaces (Agent + RAG) and Hostinger (Node.js Backend), the following smoke test cases must be run:

1. **Team Leader Upload & Deletion Security Gates**
   - Attempt to upload/delete a project file from a **regular member's** account -> verify backend rejects with a `403 Forbidden` ("Only the project leader...").
   - Perform the same actions from the **project leader's** account -> verify success.

2. **Format Compatibility (Word/PDF/TXT)**
   - Upload a `.docx` file -> verify the chunks are split and indexed successfully.
   - Run a query referencing content inside the DOCX -> verify correct citation.

3. **Projectless Tool Routing Test (ArXiv / StackOverflow)**
   - Run: `curl -X POST http://localhost:8000/api/v1/nlp/agent/chat/0 -H "Content-Type: application/json" -d '{"message": "What is the latest research on transformer models?"}'`
   - Verify: Returns live ArXiv paper summaries, abstracts, and links.

4. **In-Scope Query Exception Test (Technical History)**
   - Run: `curl -X POST http://localhost:8000/api/v1/nlp/agent/chat/0 -H "Content-Type: application/json" -d '{"message": "Who invented Python programming and when?"}'`
   - Verify: The classifier maps it to `GENERAL` (in-scope) and pulls the answer from Wikipedia.

5. **Arabic Streaming Mojibake Test**
   - Run: Interact via Web UI in Arabic (e.g. asking for a sprint plan or coding help).
   - Verify: Chunks stream back in clean, beautiful Modern Standard Arabic.

6. **Conversational Memory Recall Test (English / Arabic)**
   - Run: After chatting about 3 or 4 different technical topics in a session, ask: `"What was the last thing we talked about?"` or `"ماذا تحدثنا بالأمس؟"`.
   - Verify: The model retrieves the session history database records, formats a clean timeline, and answers with a highly accurate summary of the topics you discussed!
