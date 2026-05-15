"""Quick test of specific fixes after deployment."""
import httpx, asyncio, os, json

API_KEY = os.environ.get("RAG_API_KEY", "")
BASE = "https://sallahahmed-connexiorag.hf.space"
HEADERS = {"Content-Type": "application/json", "X-API-Key": API_KEY}

async def chat(pid, query):
    async with httpx.AsyncClient(timeout=60) as c:
        resp = await c.post(f"{BASE}/api/v1/nlp/agent/chat/{pid}",
            json={"query": query, "user_id": 1, "persona": "student"},
            headers=HEADERS)
        return resp.json()

async def main():
    tests = [
        ("how does this platform work?", "onboarding"),
        ("how to make pizza?", "out_of_scope"),
        ("recipe for pasta", "out_of_scope"),
        ("weather in London", "out_of_scope"),
        ("I need a developer", "team_formation"),
        ("my project is behind", "milestone_warning"),
        ("I'm stuck on login", "blocker"),
        ("what is agile?", "general"),
        ("مرحبا", "general"),
        ("كيف أبدأ؟", "onboarding"),
        ("الطقس في القاهرة", "out_of_scope"),
    ]
    
    passed = 0
    for query, expected in tests:
        try:
            data = await chat(0, query)
            node = data.get("node", "?")
            ok = node == expected
            status = "PASS" if ok else "FAIL"
            if ok:
                passed += 1
            answer = (data.get("answer") or "")[:80]
            print(f"  [{status}] Node={node} (expected {expected}) | Query: {query[:40]}")
            print(f"          Answer: {answer}")
        except Exception as e:
            print(f"  [FAIL] {query[:40]} — Error: {e}")
    
    print(f"\n  Result: {passed}/{len(tests)} passed")

asyncio.run(main())
