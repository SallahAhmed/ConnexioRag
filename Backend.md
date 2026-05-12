File 1: Connexio-backend/.env — add these 4 variables

AI_AGENT_URL=https://salla-masarx-agent.hf.space
RAG_SERVICE_URL=https://salla-connexios-rag.hf.space
CONNEXIO_RAG_API_KEY=90abeeeaa98cec6d68c47bebf65400ba3eb4cdb89ca87d0958d9c3b25533b091
BACKEND_JWT_SECRET=your-super-secret-jwt-key-change-this-in-production-2024
Replace the HF Space URLs with your actual Space URLs. CONNEXIO_RAG_API_KEY is the same as CONNEXIO_INTERNAL_API_KEY in Connexios .env. BACKEND_JWT_SECRET must be identical to the existing JWT_SECRET.

File 2: Create Connexio-backend/services/aiService.js (new file)

import axios from "axios";
import jwt from "jsonwebtoken";

const AI_AGENT_URL = process.env.AI_AGENT_URL;
const RAG_SERVICE_URL = process.env.RAG_SERVICE_URL;
const BACKEND_JWT_SECRET = process.env.BACKEND_JWT_SECRET;
const CONNEXIO_RAG_API_KEY = process.env.CONNEXIO_RAG_API_KEY;

function makeServiceToken(uid, projectId, intent) {
return jwt.sign({ uid, project_id: projectId, intent }, BACKEND_JWT_SECRET, {
expiresIn: "5m",
});
}

// Fire-and-forget: returns immediately, result ignored
export const fireEvent = async (eventType, projectId, uid, payload = {}) => {
try {
const token = makeServiceToken(uid, projectId, eventType);
await axios.post(
`${AI_AGENT_URL}/api/v1/masarx/webhook/event/${eventType}/${projectId}`,
payload,
{ headers: { Authorization: `Bearer ${token}` }, timeout: 10000 }
);
} catch (err) {
console.warn(`[MasarX] Event ${eventType} failed (non-fatal):`, err.message);
}
};

// Blocking — use only when user waits for result
export const triggerIntent = async (intent, projectId, uid, payload = {}) => {
const token = makeServiceToken(uid, projectId, intent);
const response = await axios.post(
`${AI_AGENT_URL}/api/v1/masarx/agent/${intent}/${projectId}`,
payload,
{ headers: { Authorization: `Bearer ${token}` }, timeout: 120000 }
);
return response.data;
};

// Forward HITL approval from user
export const submitApproval = async (approvalToken, approved) => {
const response = await axios.post(
`${AI_AGENT_URL}/api/v1/masarx/approval/${approvalToken}`,
{ approved }
);
return response.data;
};

// RAG chat proxy (non-streaming)
export const ragChat = async (projectId, query, userId, persona) => {
const response = await axios.post(
`${RAG_SERVICE_URL}/api/v1/nlp/agent/chat/${projectId}`,
{ query, user_id: userId, persona },
{ headers: { "x-api-key": CONNEXIO_RAG_API_KEY }, timeout: 30000 }
);
return response.data;
};
File 3: Create Connexio-backend/modules/ai/ai.routes.js (new file)

import express from "express";
import { authMiddleware } from "../../middleware/authMiddleware.js";
import { ragChat, triggerIntent, submitApproval } from "../../services/aiService.js";
import axios from "axios";

const router = express.Router();
const RAG_SERVICE_URL = process.env.RAG_SERVICE_URL;
const CONNEXIO_RAG_API_KEY = process.env.CONNEXIO_RAG_API_KEY;

// Non-streaming RAG chat
router.post("/chat/:projectId", authMiddleware, async (req, res) => {
try {
const result = await ragChat(req.params.projectId, req.body.query, req.user.UID, req.body.persona);
res.json(result);
} catch (err) {
res.status(502).json({ error: "RAG service unavailable", detail: err.message });
}
});

// Streaming RAG chat (SSE)
router.get("/chat/stream/:projectId", authMiddleware, async (req, res) => {
res.setHeader("Content-Type", "text/event-stream");
res.setHeader("Cache-Control", "no-cache");
res.setHeader("Connection", "keep-alive");
try {
const response = await axios.get(
`${RAG_SERVICE_URL}/api/v1/nlp/agent/chat/stream/${req.params.projectId}`,
{
params: { query: req.query.query, user_id: req.user.UID, persona: req.query.persona },
headers: { "x-api-key": CONNEXIO_RAG_API_KEY },
responseType: "stream",
}
);
response.data.pipe(res);
} catch (err) {
res.write(`data: {"error": "Stream failed"}\n\n`);
res.end();
}
});

// Manual MasarX intent trigger
router.post("/agent/:intent/:projectId", authMiddleware, async (req, res) => {
try {
const result = await triggerIntent(req.params.intent, req.params.projectId, req.user.UID, req.body);
res.json(result);
} catch (err) {
res.status(502).json({ error: "Agent unavailable", detail: err.message });
}
});

// HITL approval forwarding
router.post("/approval/:token", authMiddleware, async (req, res) => {
try {
const result = await submitApproval(req.params.token, req.body.approved);
res.json(result);
} catch (err) {
res.status(502).json({ error: "Approval failed", detail: err.message });
}
});

export default router;
File 4: Connexio-backend/bootstrap.js — register AI routes
Find the block where other routes are registered (like app.use("/api/auth", ...)) and add:

import aiRoutes from "./modules/ai/ai.routes.js";
// ...existing imports...

app.use("/api/ai", aiRoutes);
File 5: Connexio-backend/modules/fileUpload/fileUpload.controller.js
Inside the uploadProjectFile function, after the file is saved locally, add this block before the res.json(...) response:

import FormData from "form-data";
import fs from "fs";
// ...at the top of the file

// Inside uploadProjectFile, after saving the file:
try {
const formData = new FormData();
formData.append("file", fs.createReadStream(savedFilePath), { filename: originalName });
formData.append("chunk_size", "500");
formData.append("overlap_size", "50");
formData.append("do_reset", "0");

await axios.post(
`${process.env.RAG_SERVICE_URL}/api/v1/data/upload-and-process/${projectId}`,
formData,
{ headers: { "x-api-key": process.env.CONNEXIO_RAG_API_KEY, ...formData.getHeaders() } }
);
} catch (err) {
console.warn("[RAG] File indexing failed (non-fatal):", err.message);
}
projectId should already be available in that function from the route param or the request body.

File 6: Connexio-backend/modules/projects (project creation controller)
Inside the function that creates a project, after the MySQL INSERT succeeds (where you already have result.rows[0].PID), add:

try {
await axios.post(
`${process.env.RAG_SERVICE_URL}/api/v1/projects/sync`,
{
mysql_pid: newProject.PID,
name: newProject.PName,
description: newProject.Description || "",
},
{ headers: { "x-api-key": process.env.CONNEXIO_RAG_API_KEY } }
);
} catch (err) {
console.warn("[RAG] Project sync failed (non-fatal):", err.message);
}
Event Wires (for Hassan — add fireEvent calls in existing controllers)
Where After what action Call
auth.controller.js User signs up fireEvent("user.joined_platform", null, newUser.UID)
projects controller User joins a project fireEvent("user.joined_project", projectId, uid)
tasks/projects controller Sprint starts fireEvent("project.sprint_started", projectId, uid)
tasks controller Task marked complete fireEvent("task.completed", projectId, uid, { task_id })
tasks/projects controller Sprint closed fireEvent("sprint.closed", projectId, uid)
tasks controller Milestone completed fireEvent("milestone.completed", projectId, uid)
projects controller Project closed/archived fireEvent("project.closed", projectId, uid)
All fireEvent calls are non-fatal — they catch errors internally and just log a warning, so they won't break any existing functionality.
