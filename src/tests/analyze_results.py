"""Analyze saved test results."""
import json, sys

path = sys.argv[1] if len(sys.argv) > 1 else None
if not path:
    import glob
    files = sorted(glob.glob("rag_test_results_*.json"))
    if not files:
        print("No result files found")
        sys.exit(1)
    path = files[-1]

with open(path, "r", encoding="utf-8") as f:
    data = json.load(f)

print(f"Results from: {data['timestamp']}")
print(f"Target: {data['target']}")

for cat, results in data["results"].items():
    print(f"\n=== {cat.upper()} ({len(results)} tests) ===")
    for r in results:
        status = "PASS" if r["passed"] else "FAIL"
        resp = r.get("response") or {}
        answer = (resp.get("answer") or "")[:150]
        node = resp.get("node", "?")
        lang = resp.get("language", "?")
        sources = resp.get("sources", [])
        failures = r.get("failures", [])
        print(f"  [{status}] {r['name']}")
        print(f"    Query: {r['query'][:60]}")
        print(f"    Node: {node} | Lang: {lang} | Sources: {sources}")
        print(f"    Answer: {answer}")
        if failures:
            print(f"    ISSUES: {failures}")
        print()
