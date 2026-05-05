import asyncio
import sys
import os

# Add src to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))

# Set dummy env vars before imports to satisfy Pydantic/BaseSettings
os.environ["APP_NAME"] = "Test"
os.environ["APP_VERSION"] = "0.1"
os.environ["FILE_ALLOWED_TYPES"] = '["text/plain"]'
os.environ["FILE_MAX_SIZE"] = "10"
os.environ["FILE_DEFAULT_CHUNK_SIZE"] = "512"
os.environ["POSTGRES_USERNAME"] = "dummy"
os.environ["POSTGRES_PASSWORD"] = "dummy"
os.environ["POSTGRES_HOST"] = "localhost"
os.environ["POSTGRES_PORT"] = "5432"
os.environ["POSTGRES_MAIN_DATABASE"] = "dummy"
os.environ["GENERATION_BACKEND"] = "OPENAI"
os.environ["EMBEDDING_BACKEND"] = "OPENAI"
os.environ["VECTOR_DB_BACKEND"] = "PGVECTOR"
os.environ["VECTOR_DB_PATH"] = "dummy"
os.environ["VECTOR_DB_DISTANCE_METHOD"] = "cosine"
os.environ["DEFAULT_LANG"] = "en"
os.environ["PRIMARY_LANG"] = "en"
os.environ["CELERY_BROKER_URL"] = "dummy"
os.environ["CELERY_RESULT_BACKEND"] = "dummy"
os.environ["CELERY_FLOWER_PASSWORD"] = "dummy"
os.environ["CELERY_FLOWER_BROKER_API"] = "dummy"

from controllers.WorkflowController import WorkflowController
from models.enums.WorkflowNodeEnum import WorkflowNodeEnum

class MockLLM:
    def __init__(self, responses):
        self.responses = responses
        self.enums = type('obj', (object,), {'SYSTEM': type('obj', (object,), {'value': 'system'})})
    
    async def generate_text(self, prompt, chat_history=None):
        for key, val in self.responses.items():
            if key in prompt:
                return val
        return "GENERAL"

    def construct_prompt(self, prompt, role):
        return {"role": role, "content": prompt}

class MockTemplateParser:
    def set_language(self, lang): pass
    def get(self, group, key, vars=None):
        return f"TEMPLATE: {group}.{key}"

async def test_scope():
    # Setup mocks
    responses = {
        "Who is the president of France?": "OUT_OF_SCOPE",
        "capital of": "OUT_OF_SCOPE",
        "How do I find a teammate?": "TEAM_FORMATION",
        "Hello": "GENERAL",
        "tell me a joke": "OUT_OF_SCOPE"
    }
    
    mock_llm = MockLLM(responses)
    mock_parser = MockTemplateParser()
    
    controller = WorkflowController(mock_llm, mock_parser)
    
    queries = [
        "Who is the president of France?",
        "How do I find a teammate?",
        "Hi there",
        "What is the capital of Japan?",
        "Tell me a joke about robots"
    ]
    
    print("--- Scope Verification ---")
    for q in queries:
        node = await controller.detect_node(q)
        print(f"Query: '{q}' -> Node: {node}")

if __name__ == "__main__":
    asyncio.run(test_scope())
