import os
import requests
import json
import random

# Configuration
# MAIN_BACKEND_URL or a direct RAG_API_URL should point to your deployed RAG service.
RAG_API_URL = os.environ.get("RAG_API_URL", "https://connexio.icu")
# The X-API-Key required for Connexio internal RAG communication
CONNEXIO_INTERNAL_API_KEY = os.environ.get("CONNEXIO_INTERNAL_API_KEY")
# The API key for the Jules agent service
JULES_API_KEY = os.environ.get("JULES_API_KEY")
# Jules API endpoint (assuming a standard structure, you might need to adjust this to match the actual Jules API URL)
JULES_API_ENDPOINT = os.environ.get("JULES_API_ENDPOINT", "https://api.jules.ai/v1/agents/run")

# A pool of test questions to simulate different user personas and test tool capabilities
TEST_QUERIES = [
    {
        "persona": "student",
        "query": "What is the latest news about Artificial Intelligence?",
        "expected_tool": "Google Search"
    },
    {
        "persona": "early_career",
        "query": "I am getting a TypeError in python when using await on a MagicMock object. How do I fix this?",
        "expected_tool": "StackOverflow"
    },
    {
        "persona": "student",
        "query": "Can you summarize the commits for the repository openai/gym?",
        "expected_tool": "GitHub"
    },
    {
        "persona": "early_career",
        "query": "What is the main topic of the paper 'Attention is All You Need'?",
        "expected_tool": "ArXiv"
    },
    {
        "persona": "student",
        "query": "Can you tell me about the history of the Eiffel Tower?",
        "expected_tool": "Wikipedia"
    },
    {
        "persona": "early_career",
        "query": "I am feeling blocked on my current project milestone, can you help me figure out what to do next?",
        "expected_intent": "blocker" # General conversation/intent routing test
    }
]

def query_rag_system(query, persona):
    """Hits the deployed RAG system endpoint."""
    headers = {
        "x-api-key": CONNEXIO_INTERNAL_API_KEY,
        "Content-Type": "application/json"
    }
    # Using a hypothetical project_id for testing (e.g., 0 or 1)
    project_id = 0
    url = f"{RAG_API_URL}/api/v1/nlp/agent/chat/{project_id}"

    payload = {
        "user_id": 999, # Dummy user
        "query": query,
        "persona": persona,
        "limit": 5,
        "model_tier": "auto"
    }

    try:
        response = requests.post(url, headers=headers, json=payload, timeout=60)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"Error querying RAG system: {e}")
        return {"answer": f"ERROR: {str(e)}", "sources": []}

def trigger_jules_agent(test_results):
    """Calls the Jules API to evaluate the results and take action if needed."""

    prompt = f"""
    You are Jules, an autonomous expert software engineer.
    I have run a test suite against our deployed Connexio RAG system.

    Here are the test queries and the responses the system generated:

    {json.dumps(test_results, indent=2)}

    Your task:
    1. Evaluate each answer on a scale of 1 to 10 based on accuracy, lack of hallucination, tone matching the persona, and whether the expected tools/intents were used.
    2. If the average score or any individual score is strictly below 9/10:
       - You must autonomously investigate the Connexio RAG codebase.
       - Identify the bug or suboptimal prompt causing the poor performance.
       - Implement the fix, run tests, and submit a PR to resolve the issue.
    3. If all scores are 9 or 10, simply confirm the system is healthy.

    Do your best to improve the system if it falls short.
    """

    headers = {
        "Authorization": f"Bearer {JULES_API_KEY}",
        "Content-Type": "application/json"
    }

    payload = {
        "task": prompt,
        "repo": "your_org/connexio-rag", # Update with actual repo if needed
        "branch": "main"
    }

    print("Triggering Jules Agent for evaluation...")
    try:
        response = requests.post(JULES_API_ENDPOINT, headers=headers, json=payload, timeout=30)
        response.raise_for_status()
        print(f"Jules Agent triggered successfully. Response: {response.status_code}")
    except Exception as e:
        print(f"Error triggering Jules Agent: {e}")

def run_evaluation():
    if not CONNEXIO_INTERNAL_API_KEY:
        print("Warning: CONNEXIO_INTERNAL_API_KEY is not set. The RAG API might reject requests.")
    if not JULES_API_KEY:
        print("Warning: JULES_API_KEY is not set. Cannot trigger the Jules agent.")

    # Randomly pick 3 questions to evaluate per run to save time and tokens
    selected_queries = random.sample(TEST_QUERIES, 3)

    results_to_evaluate = []

    for q in selected_queries:
        print(f"Testing Query: '{q['query']}' (Persona: {q['persona']})")
        rag_response = query_rag_system(q['query'], q['persona'])

        results_to_evaluate.append({
            "test_case": q,
            "system_response": rag_response.get("answer", "No answer provided"),
            "system_sources": rag_response.get("sources", []),
            "detected_node": rag_response.get("node", "unknown")
        })
        print(f"Got response. Sources used: {rag_response.get('sources', [])}")

    trigger_jules_agent(results_to_evaluate)

if __name__ == "__main__":
    run_evaluation()
