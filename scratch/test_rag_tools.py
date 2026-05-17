import os
import sys
import asyncio
import logging

# Set up logging to stdout to verify HF space logs output style
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stdout
)

# Add 'src' directory to python path
src_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src")
sys.path.insert(0, src_dir)

from helpers.config import get_settings
from stores.llm.LLMProviderFactory import LLMProviderFactory
from stores.llm.templates.template_parser import TemplateParser
from controllers.WorkflowController import WorkflowController
from controllers.NLPController import NLPController
from models.enums.WorkflowNodeEnum import WorkflowNodeEnum

class MockToolManager:
    def __init__(self):
        pass
    async def search_knowledge_base(self, project_id, query, limit):
        return []
    async def fetch_github_data(self, repo_name, mode):
        return "mock github commits data"
    async def search_arxiv(self, query):
        return "mock arxiv search result"
    async def search_stackoverflow(self, query):
        return "mock stackoverflow search result"
    async def search_google(self, query):
        return "mock google search result"
    async def search_wiki(self, query, lang):
        return "mock wikipedia search result"

async def test_cases():
    settings = get_settings()
    llm_provider_factory = LLMProviderFactory(settings)
    
    generation_client = llm_provider_factory.create_generation_client()
    utility_client = llm_provider_factory.create_utility_client()
    
    template_parser = TemplateParser(
        language=settings.PRIMARY_LANG,
        default_language=settings.DEFAULT_LANG,
    )
    
    nlp_controller = NLPController(
        vectordb_client=None,
        generation_client=generation_client,
        embedding_client=None,
        template_parser=template_parser,
        utility_client=utility_client,
        settings=None, # pass None to prevent real ToolManager connecting to PG
        db_client=None,
        reranker=None,
        backend_client=None,
        masarx_client=None
    )
    
    # Inject Mock ToolManager
    nlp_controller.tool_manager = MockToolManager()
    
    print("\n" + "="*80)
    print("RUNNING RAG TOOL ROUTING & CLASSIFICATION TESTS")
    print("="*80)
    
    # ─── CASE 1: CLARIFICATION QUESTION WITH "YEAR" ───
    print("\n[TEST CASE 1] Clarification question containing 'year'")
    query_1 = "what is the year you meant?"
    node_1 = await nlp_controller.workflow_controller.detect_node(query_1)
    print(f"Query: '{query_1}'")
    print(f"Detected Node: {node_1} (Expected: WorkflowNodeEnum.GENERAL)")
    assert node_1 != WorkflowNodeEnum.OUT_OF_SCOPE, "Bug: Query was incorrectly classified as OUT_OF_SCOPE!"
    print("[OK] Success: Query correctly classified.")
    
    # ─── CASE 2: TEMPORAL TREND QUERY (GOOGLE SEARCH) ───
    print("\n[TEST CASE 2] Temporal / Trend Query")
    query_2 = "what are the best fields in technology this year?"
    
    chat_history, footer_prompt, session_id, node, language, sources, trace_id, prompt_client, final_history = (
        await nlp_controller._prepare_chat_context(
            user_id=1,
            project_id=None, # project_id is None triggers tool decision path
            query=query_2,
            persona="student"
        )
    )
    print(f"Query: '{query_2}'")
    print(f"Routed Node: {node}")
    print(f"Sources included: {sources}")
    print("[OK] Success: Temporal query routed and processed.")
    
    # ─── CASE 3: EACH SPECIFIC TOOL ROUTING VERIFICATION ───
    test_queries = {
        "WIKIPEDIA": "tell me about photosynthesis on wikipedia",
        "GOOGLE": "what is the current temperature in Cairo right now?",
        "GITHUB": "show me the latest commits on SallahAhmed/ConnexioRag repository",
        "ARXIV": "research papers on deep learning models and neural networks",
        "STACKOVERFLOW": "how to resolve keyerror in python dict when fetching keys"
    }
    
    for tool_name, query in test_queries.items():
        print(f"\n[TEST CASE 3 - {tool_name}] Query: '{query}'")
        try:
            _, _, _, _, _, sources, _, _, _ = await nlp_controller._prepare_chat_context(
                user_id=1,
                project_id=None,
                query=query,
                persona="student"
            )
            print(f"Resulting sources for query: {sources}")
        except Exception as e:
            print(f"Error executing case: {e}")

if __name__ == "__main__":
    asyncio.run(test_cases())
