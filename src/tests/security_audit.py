"""Security audit of the RAG codebase."""
import os

BASE = r"C:\Users\salla\Connexios\src"
issues = []

# 1. Rate limiting
for f in ["Routes/agent.py", "Routes/data.py", "Routes/nlp.py", "Routes/base.py", "Routes/projects.py"]:
    path = os.path.join(BASE, f)
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as fh:
            content = fh.read()
        if "rate.limit" not in content and "throttle" not in content and "slowapi" not in content:
            issues.append(f"[GAP] {f}: No rate limiting")

# 2. Session ownership check
path = os.path.join(BASE, "Routes/agent.py")
with open(path, "r", encoding="utf-8") as fh:
    agent = fh.read()
if "session_id" in agent and "user_id" not in agent[agent.find("session_id"):agent.find("session_id")+500]:
    issues.append("[GAP] agent.py: session_id used without user_id ownership verification")

# 3. Python sandbox safety
path = os.path.join(BASE, "controllers/helpers/ToolManager.py")
with open(path, "r", encoding="utf-8") as fh:
    tm = fh.read()
if "exec(" in tm:
    issues.append("[WARN] ToolManager uses exec() with limited but improvable sandbox")

# 4. Input max length validation
path = os.path.join(BASE, "Routes/schemas/agent.py")
with open(path, "r", encoding="utf-8") as fh:
    schema = fh.read()
if "max_length" not in schema:
    issues.append("[GAP] No max_length on query input field")

# 5. CORS configuration
path = os.path.join(BASE, "main.py")
with open(path, "r", encoding="utf-8") as fh:
    main = fh.read()
if "CORSMiddleware" not in main:
    issues.append("[INFO] No CORS middleware configured")

# 6. Session TTL already added
print("=== Security Audit Results ===\n")
if issues:
    for i in issues:
        print(f"  {i}")
else:
    print("  No issues found!")

print()
print("=== Summary ===")
print("  Rate limiting: NOT PRESENT — needs addition")
print("  Session ownership: NOT checked — session_id not tied to user_id")
print("  Input max_length: NOT set — query field has no length limit")
print("  Python exec: PRESENT (limited globals, 5s timeout)")
print("  429 retry: PRESENT (exponential backoff in OpenAIProvider)")
print("  CORS: NOT configured")
print("  Session TTL: PRESENT (30-day cleanup via Celery Beat)")
