## 5. Every File That Changed — Backend Side

**You do not make these changes. Send this section to your teammate.**

---

### 5.1 `tasks.routes.js` — UPDATED

**Change required:**
Remove the `protect` middleware from the `GET /api/tasks` route only. Every
other HTTP method on tasks must remain protected.

**Before:**
```javascript
router.get('/', protect, TaskController.getTasks);
router.post('/', protect, TaskController.createTask);
router.put('/:id', protect, TaskController.updateTask);
router.delete('/:id', protect, TaskController.deleteTask);
```

**After:**
```javascript
router.get('/', TaskController.getTasks);           // ← public (read only)
router.post('/', protect, TaskController.createTask);
router.put('/:id', protect, TaskController.updateTask);
router.delete('/:id', protect, TaskController.deleteTask);
```

**Why this is safe:**
Reading task data (descriptions, statuses, dates) for display purposes is not
sensitive. The RAG needs this data to give contextually accurate answers about
project progress. Write operations (create, update, delete) remain fully
protected by JWT.

---

### 5.2 `utils/ragClient.js` — NEW FILE (teammate creates)

```javascript
// utils/ragClient.js

const RAG_BASE_URL = process.env.RAG_BASE_URL;
const RAG_API_KEY  = process.env.CONNEXIO_RAG_API_KEY;

/**
 * Send a chat message to the Connexios RAG agent.
 *
 * @param {number} userId     - UID from the validated JWT (req.user.UID)
 *                              NEVER pass this from req.body — it must come
 *                              from the server-side JWT extraction only.
 * @param {number} projectId  - PID from the projects table (integer)
 * @param {string} query      - The user's message
 * @param {string} persona    - "student" | "early_career" | "educator" | "company"
 * @param {number|null} sessionId - RAG session ID for conversation continuity
 *                                  (null on the first message, then use what RAG returns)
 * @returns {Promise<Object>} - { answer, node, language, sources, session_id }
 */
async function callRagChat(userId, projectId, query, persona = "student", sessionId = null) {
  const response = await fetch(
    `${RAG_BASE_URL}/api/v1/nlp/agent/chat/${projectId}`,
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-API-Key": RAG_API_KEY,
      },
      body: JSON.stringify({
        user_id:    userId,
        query:      query,
        persona:    persona,
        session_id: sessionId,
        limit:      5,
      }),
    }
  );

  if (!response.ok) {
    const err = await response.json().catch(() => ({}));
    throw new Error(`RAG error ${response.status}: ${err.error || response.statusText}`);
  }

  return response.json();
}

module.exports = { callRagChat };
```

**Usage inside a controller:**
```javascript
const { callRagChat } = require("../utils/ragClient");

exports.chat = async (req, res) => {
  try {
    const userId    = req.user.UID;                        // ← from JWT middleware
    const projectId = parseInt(req.params.projectId, 10);
    const { query, persona, session_id } = req.body;

    const result = await callRagChat(userId, projectId, query, persona, session_id);

    res.json({
      success:    true,
      answer:     result.answer,
      session_id: result.session_id,  // store this and pass back on next turn
      node:       result.node,
      language:   result.language,
      sources:    result.sources,
    });
  } catch (err) {
    console.error("[RAG Chat Error]", err.message);
    res.status(500).json({ success: false, message: "AI service temporarily unavailable." });
  }
};
```

---

### 5.3 Backend `.env` additions

```env
CONNEXIO_RAG_API_KEY=<same_key_as_rag_CONNEXIO_INTERNAL_API_KEY>
RAG_BASE_URL=http://connexios:8000
```

Replace `connexios` with whatever the RAG container is named in the shared
`docker-compose.yml`.

---

## 6. Frontend Notes — For When It Is Built

No frontend changes are needed right now because there is no frontend. When the
frontend is built, here is exactly what it needs to know:

### What the frontend calls
The frontend calls **the main backend only**. It never calls the RAG directly.

```javascript
// CORRECT — frontend calls main backend
fetch('/api/rag/chat/123', {
  method: 'POST',
  headers: {
    'Authorization': `Bearer ${jwtToken}`,
    'Content-Type': 'application/json',
  },
  body: JSON.stringify({
    query:      userMessage,
    persona:    'student',
    session_id: storedSessionId ?? null,  // null on first message
  }),
});

// WRONG — frontend must never call the RAG directly
fetch('https://connexios:8000/api/v1/nlp/agent/chat/123', { ... });
```

### session_id — critical for conversation memory
The RAG returns a `session_id` on every response. The frontend must store this
value and include it on every follow-up message in the same conversation. If
`session_id` is not passed, the RAG starts a fresh session and loses memory of
everything said before.

### Streaming chat (future)
The streaming endpoint (`GET /api/v1/nlp/agent/chat/stream/{project_id}`) uses
Server-Sent Events. The browser's native `EventSource` API cannot send custom
headers, which means the `X-API-Key` cannot be sent from the browser. The
recommended approach is for the main backend to proxy the SSE stream — the
frontend connects to the main backend's streaming endpoint, and the backend
opens the RAG stream with the key in the header and forwards chunks.

---
