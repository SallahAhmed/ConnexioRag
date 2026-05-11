# RAG Integration: Complete Answers to Claude's Clarification Questions

**Date:** May 8, 2026  
**Project:** Connexio Backend + Connexios RAG Integration  
**Status:** Ready for Implementation

---

## 📋 Quick Reference: Final Decisions

| Question | Decision |
|----------|----------|
| **1. Authentication** | Service-to-Service with Shared API Key |
| **2. Database Access** | REST API Calls (NOT direct DB connection) |
| **3. Project Identifier** | Integer PID (auto-increment) |
| **4. Document Ingestion** | Manual (users call RAG endpoints) |

---

---

## ❓ Question 1: Authentication & Identity

### **Question:** How does user_id reach the RAG model safely?

### **Answer: Service-to-Service Authentication with Shared Secret**

#### **Authentication Flow:**
```
1. Frontend User logs in → Main Backend (Connexio)
2. Main Backend validates credentials → Issues JWT token
3. Frontend sends authenticated request to Main Backend
4. Main Backend extracts req.user.uid from JWT (server-side)
5. Main Backend calls RAG with:
   - Body: { user_id: 1, project_id: 123, query: "...", ... }
   - Header: X-API-Key: {SHARED_SECRET}
6. RAG validates X-API-Key header → trusts user_id → processes request
```

#### **User ID Format:**
- **Type:** Integer (auto-increment)
- **Field Name:** `UID` in users table
- **Range:** 1, 2, 3, ... (positive integers)
- **Example:** `user_id: 1` (Hassan's account), `user_id: 2` (Another user)

#### **Main Backend Authentication Details:**
- **Token Type:** JWT (JSON Web Token)
- **Token Header:** `Authorization: Bearer eyJhbGciOiJIUzI1NiIs...`
- **Token Payload:** 
  ```json
  {
    "UID": 1,
    "email": "user@example.com",
    "user_type": "technical",
    "iat": 1715000000,
    "exp": 1715600000
  }
  ```
- **JWT Secret:** Stored in `JWT_SECRET` env variable
- **Token Expiry:** 7 days (configurable via `JWT_EXPIRES_IN`)
- **Middleware:** `middleware/authmiddleware.js` - `protect()` function

#### **Authentication Endpoints:**
```
POST /api/auth/signup
  Body: { FullName, email, password, confirmPassword }
  Response: { success: true, message: "Check your email" }

POST /api/auth/signin
  Body: { email, password }
  Response: { success: true, token: "jwt_token", data: { user: {...} } }

POST /api/auth/google-signin
  Body: { email, FullName, googleId, photo, user_type, skills }
  Response: { success: true, token: "jwt_token", data: { user: {...} } }
```

#### **Implementation for RAG:**

**Step 1: Define Shared Secret in .env files**

Main Backend `.env`:
```env
CONNEXIO_RAG_API_KEY=connexio_rag_shared_secret_2024_prod_only
```

RAG `.env`:
```env
CONNEXIO_INTERNAL_API_KEY=connexio_rag_shared_secret_2024_prod_only
```

**Step 2: Main Backend calls RAG (Example)**

```javascript
// In main backend's RAG integration endpoint/service
async function callRagAgent(userId, projectId, query, persona = "student") {
  const apiKey = process.env.CONNEXIO_RAG_API_KEY;
  
  const response = await fetch(
    `http://connexios:8000/api/v1/nlp/agent/chat/${projectId}`,
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-API-Key": apiKey
      },
      body: JSON.stringify({
        user_id: userId,        // ← Already validated on main backend
        query: query,
        persona: persona,
        session_id: null
      })
    }
  );
  
  return response.json();
}
```

**Step 3: RAG validates the header**

```python
# In RAG's src/Routes/agent.py
from fastapi import APIRouter, Request, status, Header
from fastapi.responses import JSONResponse
import os

@agent_router.post("/chat/{project_id}")
async def agent_chat(
    request: Request, 
    project_id: int, 
    chat_request: AgentChatRequest,
    x_api_key: str = Header(None)
):
    # Validate API Key
    expected_key = os.getenv("CONNEXIO_INTERNAL_API_KEY")
    if x_api_key != expected_key:
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={"signal": "UNAUTHORIZED", "error": "Invalid API Key"}
        )
    
    # Now trust user_id from request body
    nlp_controller = get_nlp_controller(request)
    result = await nlp_controller.answer_agent_chat(
        user_id=chat_request.user_id,
        project_id=project_id,
        query=chat_request.query,
        persona=chat_request.persona,
        session_id=chat_request.session_id,
        limit=chat_request.limit
    )
    
    return JSONResponse(content={"signal": "AGENT_CHAT_SUCCESS", **result})
```

#### **User Profile Endpoint (for RAG to fetch user details):**

```
GET /api/users/{user_id}
Response (200):
{
  "UID": 1,
  "FullName": "Hassan Ebrahem Hassan",
  "email": "hassan@example.com",
  "photo": "https://...",
  "fieldexperience": "5 years",
  "rate": 4.5,
  "user_type": "technical",
  "technologies": "Python,JavaScript,React",
  "skills": ["Python", "JavaScript", "React", "FastAPI"],
  "experience_level": "senior",
  "years_of_experience": 5,
  "portfolio_url": "https://portfolio.com",
  "linkedin_url": "https://linkedin.com/...",
  "total_points": 250,
  "tasks_completed": 15,
  "team_rating_avg": 4.3,
  "created_at": "2024-01-15T10:00:00Z"
}
```

#### **What NOT to do:**
- ❌ Do NOT allow frontend to directly call RAG with user_id (spoofing risk)
- ❌ Do NOT trust user_id from request body without API key validation
- ❌ Do NOT send JWT token inside request body (use headers)

---

---

## ❓ Question 2: Database Separation

### **Question:** Which database does ToolManager's SQL tool actually point to?

### **Answer: Use REST API Calls to Main Backend (NOT Direct DB Connection)**

#### **Why NOT Direct Database Access:**
The RAG's ToolManager currently queries tables that **DO NOT EXIST** in the main backend:
- ❌ `technology` table (doesn't exist)
- ❌ `user_technology` table (doesn't exist)
- ❌ `project_technology` table (doesn't exist)

**Actual data location in main backend:**
- User technologies: Stored in `users.technologies` (TEXT) + `user_skills` table
- Project technologies: Stored in `projects.technologyUsed` (JSON array)

#### **Recommended Solution: REST API Calls**

The RAG should call main backend endpoints instead of querying the database directly. This is **safer, more maintainable, and follows microservices patterns**.

#### **Main Backend Database Schema (for reference):**

```sql
-- USERS TABLE
CREATE TABLE users (
    UID INT PRIMARY KEY AUTO_INCREMENT,
    FullName VARCHAR(255) NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    password VARCHAR(255),
    photo TEXT,
    fieldexperience VARCHAR(255),
    rate DECIMAL(3,2),
    email_verified BOOLEAN DEFAULT FALSE,
    google_id VARCHAR(255),
    github_username VARCHAR(255),
    technologies TEXT,               -- ← Comma-separated or JSON
    user_type VARCHAR(20) DEFAULT 'technical',
    skills JSON DEFAULT NULL,         -- ← Array of skill names
    experience_level VARCHAR(50),
    years_of_experience INT DEFAULT 0,
    portfolio_url VARCHAR(500),
    linkedin_url VARCHAR(500),
    total_points INT DEFAULT 0,
    tasks_completed INT DEFAULT 0,
    team_rating_avg DECIMAL(3,2) DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- PROJECTS TABLE
CREATE TABLE projects (
    PID INT PRIMARY KEY AUTO_INCREMENT,
    PName VARCHAR(255) NOT NULL,
    Description TEXT,
    usersNumber INT DEFAULT 0,
    startDate DATE,
    endDate DATE,
    timeLine TEXT,
    technologyUsed JSON,             -- ← Array of technologies
    created_by INT,
    github_repo_url VARCHAR(500),
    github_repo_name VARCHAR(255),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (created_by) REFERENCES users(UID) ON DELETE SET NULL
);

-- PROJECT MEMBERS TABLE
CREATE TABLE project_members (
    id INT PRIMARY KEY AUTO_INCREMENT,
    project_id INT,
    user_id INT,
    role VARCHAR(100) DEFAULT 'member',
    joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY unique_member (project_id, user_id),
    FOREIGN KEY (project_id) REFERENCES projects(PID) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES users(UID) ON DELETE CASCADE
);

-- TASKS TABLE
CREATE TABLE tasks (
    taskID INT PRIMARY KEY AUTO_INCREMENT,
    TaskDesc TEXT NOT NULL,
    project_id INT,
    assigned_to INT,
    assigned_by INT,
    status VARCHAR(50) DEFAULT 'pending',
    priority VARCHAR(20) DEFAULT 'medium',
    points INT DEFAULT 0,
    start_date DATE,
    end_date DATE,
    completed_at DATETIME NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (project_id) REFERENCES projects(PID) ON DELETE CASCADE,
    FOREIGN KEY (assigned_to) REFERENCES users(UID) ON DELETE SET NULL,
    FOREIGN KEY (assigned_by) REFERENCES users(UID) ON DELETE SET NULL
);

-- USER SKILLS TABLE
CREATE TABLE user_skills (
    id INT PRIMARY KEY AUTO_INCREMENT,
    user_id INT,
    skill_name VARCHAR(100) NOT NULL,
    skill_type VARCHAR(20) NOT NULL,
    proficiency_level INT DEFAULT 3,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY unique_user_skill (user_id, skill_name),
    FOREIGN KEY (user_id) REFERENCES users(UID) ON DELETE CASCADE
);

-- TEAM RATINGS TABLE
CREATE TABLE team_ratings (
    id INT PRIMARY KEY AUTO_INCREMENT,
    task_id INT,
    rated_user_id INT,
    rated_by_user_id INT,
    rating DECIMAL(3,2) NOT NULL,
    feedback TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (task_id) REFERENCES tasks(taskID) ON DELETE CASCADE,
    FOREIGN KEY (rated_user_id) REFERENCES users(UID) ON DELETE CASCADE,
    FOREIGN KEY (rated_by_user_id) REFERENCES users(UID) ON DELETE CASCADE
);
```

#### **REST API Endpoints to Call from RAG:**

**1. Get User Profile (with skills)**
```
GET http://connexio-backend:5000/api/users/{user_id}
Headers: Authorization: Bearer {token} (if needed)

Response (200):
{
  "UID": 1,
  "FullName": "Hassan",
  "technologies": "Python,JavaScript,React",
  "skills": ["Python", "JavaScript", "React"],
  "user_type": "technical",
  "experience_level": "senior"
}
```

**2. Get Project Details (with technology requirements)**
```
GET http://connexio-backend:5000/api/projects/{project_id}

Response (200):
{
  "PID": 123,
  "PName": "E-Learning Platform",
  "Description": "Building an online learning system",
  "technologyUsed": ["Python", "React", "PostgreSQL", "Docker"],
  "created_by": 1,
  "usersNumber": 5,
  "startDate": "2024-01-15",
  "endDate": "2024-06-15"
}
```

**3. Get Project Members (with their skills)**
```
GET http://connexio-backend:5000/api/projects/{project_id}/members

Response (200):
[
  {
    "UID": 1,
    "FullName": "Hassan",
    "email": "hassan@example.com",
    "technologies": "Python,React",
    "role": "owner",
    "user_type": "technical"
  },
  {
    "UID": 2,
    "FullName": "Sarah",
    "email": "sarah@example.com",
    "technologies": "JavaScript,CSS",
    "role": "member",
    "user_type": "technical"
  }
]
```

**4. Get Project Tasks**
```
GET http://connexio-backend:5000/api/tasks?project_id={project_id}

Response (200):
[
  {
    "taskID": 10,
    "TaskDesc": "Setup database schema",
    "assigned_to": 1,
    "status": "in_progress",
    "priority": "high",
    "points": 5,
    "end_date": "2024-01-25"
  }
]
```

#### **Implementation in RAG ToolManager:**

```python
# In src/controllers/helpers/ToolManager.py

import httpx
import os

class ToolManager:
    def __init__(self, ...):
        self.backend_url = os.getenv("MAIN_BACKEND_URL", "http://localhost:5000")
        self.api_key = os.getenv("CONNEXIO_INTERNAL_API_KEY")
    
    async def get_matching_rationale(self, user_id: int, project_id: int) -> str:
        """
        Explains why a user was matched to a project based on technology overlap.
        Calls main backend API instead of querying DB directly.
        """
        try:
            async with httpx.AsyncClient() as client:
                # Get user skills
                user_response = await client.get(
                    f"{self.backend_url}/api/users/{user_id}",
                    headers={"X-API-Key": self.api_key}
                )
                user_data = user_response.json()
                user_skills = user_data.get("technologies", "").split(",")
                
                # Get project requirements
                project_response = await client.get(
                    f"{self.backend_url}/api/projects/{project_id}",
                    headers={"X-API-Key": self.api_key}
                )
                project_data = project_response.json()
                project_techs = project_data.get("technologyUsed", [])
                
                # Calculate matching
                matched_techs = [t for t in user_skills if t in project_techs]
                
                # Generate rationale
                prompt = f"""
                Explain to user (UID: {user_id}) why they match 
                Project '{project_data['PName']}' ({project_id}).
                
                User Skills: {', '.join(user_skills)}
                Project Needs: {', '.join(project_techs)}
                Matched Skills: {', '.join(matched_techs)}
                
                Weights: 35% Skills, 25% Availability, 20% Rating, 
                12% Experience, 5% Goals, 3% Domain.
                
                Provide a personalized, encouraging explanation.
                """
                
                response = await self.generation_client.generate_text(prompt=prompt)
                return response
                
        except Exception as e:
            self.logger.error(f"Matching Rationale Error: {str(e)}")
            return "Unable to calculate matching rationale at this time."
    
    async def get_team_gaps(self, project_id: int) -> str:
        """
        Identifies missing technical skills in a project team.
        """
        try:
            async with httpx.AsyncClient() as client:
                # Get project requirements
                project_response = await client.get(
                    f"{self.backend_url}/api/projects/{project_id}",
                    headers={"X-API-Key": self.api_key}
                )
                project_data = project_response.json()
                required_techs = project_data.get("technologyUsed", [])
                
                # Get team members and their skills
                members_response = await client.get(
                    f"{self.backend_url}/api/projects/{project_id}/members",
                    headers={"X-API-Key": self.api_key}
                )
                members = members_response.json()
                
                # Aggregate team skills
                team_skills = set()
                for member in members:
                    techs = member.get("technologies", "").split(",")
                    team_skills.update([t.strip() for t in techs if t.strip()])
                
                # Find gaps
                missing_techs = [t for t in required_techs if t not in team_skills]
                
                if missing_techs:
                    return f"""The project is currently missing expertise in: 
                    {', '.join(missing_techs)}. 
                    Recommendation: Recruit team members with these skills."""
                else:
                    return f"Great news! Your team has all required skills: {', '.join(required_techs)}"
                    
        except Exception as e:
            self.logger.error(f"Team Gap Error: {str(e)}")
            return "Error assessing team gaps."
```

#### **Update RAG .env:**

Add to `src/.env`:
```env
MAIN_BACKEND_URL=http://connexio-backend:5000
CONNEXIO_INTERNAL_API_KEY=connexio_rag_shared_secret_2024_prod_only
```

---

---

## ❓ Question 3: Project Identifier Format

### **Question:** Project_id — integer in RAG, but what format does the main backend use?

### **Answer: Integer PID (Auto-Increment)**

#### **Main Backend Project Identifier:**
- **Field Name:** `PID` (Project ID)
- **Type:** Integer, auto-increment
- **Primary Key:** Yes
- **Examples:** 1, 2, 3, 4, ... (sequential positive integers)
- **Unique:** Yes
- **Format:** `{"project_id": 123}` in requests

#### **Current RAG Implementation:**
The RAG already has both:
```python
# In src/models/db_schemas/connexio/schemas/project.py
class Project(SQLAlchemyBase):
    __tablename__ = "projects"
    
    project_id = Column(Integer, primary_key=True, autoincrement=True)
    project_uuid = Column(UUID(as_uuid=True), default=uuid.uuid4, unique=True, nullable=False)
    project_name = Column(String(255), nullable=True)
```

#### **Recommendation:**

The RAG **should use the main backend's `PID`** as its own `project_id` to maintain consistency.

**Two implementation strategies:**

**Option 1: Direct Use (RECOMMENDED)**
- RAG URL: `POST /api/v1/nlp/agent/chat/{project_id}` 
- Where `project_id` is the main backend's `PID`
- Example: `POST /api/v1/nlp/agent/chat/123` (project PID = 123)
- RAG stores the PID directly, no mapping needed

**Option 2: Project Mapping Table (if needed)**
```sql
CREATE TABLE main_backend_project_mappings (
    rag_project_id INT PRIMARY KEY AUTO_INCREMENT,
    main_backend_pid INT UNIQUE NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

Use mapping when:
- RAG needs to manage multiple main backend instances
- Project ID conflicts are possible
- (Generally not needed for single-instance integration)

#### **Synchronization Flow:**

```
Main Backend creates project
  ↓
  PID = 123 generated
  ↓
Frontend calls RAG: POST /api/v1/nlp/agent/chat/123
  ↓
RAG accepts PID = 123 directly
  ↓
RAG stores: project_id = 123 (same as main backend)
  ↓
RAG can call main backend: GET /api/projects/123
```

#### **API Usage Examples:**

```bash
# Create project on main backend
POST /api/projects
Body: { PName: "E-Learning", Description: "..." }
Response: { PID: 123, ... }

# Call RAG with the PID received
POST /api/v1/nlp/agent/chat/123
Headers: X-API-Key: {...}
Body: { user_id: 1, query: "What's the project about?", ... }
```

---

---

## ❓ Question 4: Document Ingestion Trigger

### **Question:** When does the document upload pipeline get triggered?

### **Answer: Manual Triggers Only (Users Call RAG Endpoints)**

#### **Current State:**
- Main backend has **NO file upload/document pipeline**
- Main backend is purely for **project management & team coordination**
- RAG (Connexios) is solely responsible for **document ingestion & indexing**

#### **Document Upload Pipeline:**

The RAG has 3 main endpoints:

**1. Upload Document**
```
POST /api/v1/data/upload/{project_id}
Content-Type: multipart/form-data

Request:
- file: [binary file, PDF or TXT]

Response (200):
{
  "signal": "FILE_UPLOAD_SUCCESS",
  "file_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

**2. Process Document (Chunking)**
```
POST /api/v1/data/process/{project_id}
Body: {
  "file_id": "550e8400-e29b-41d4-a716-446655440000",
  "chunk_size": 512,
  "overlap_size": 50
}

Response (200):
{
  "signal": "PROCESSING_STARTED",
  "task_id": "celery_task_123"
}
```

**3. Push to Vector DB (Indexing)**
```
POST /api/v1/nlp/index/push/{project_id}

Response (200):
{
  "signal": "PUSH_SUCCESS",
  "vectors_indexed": 42
}
```

**All-in-One Endpoint (RECOMMENDED):**
```
POST /api/v1/data/process-and-push/{project_id}
Body: {
  "file_id": "550e8400-e29b-41d4-a716-446655440000"
}

Response (200):
{
  "signal": "PROCESS_AND_PUSH_SUCCESS",
  "vectors_indexed": 42
}
```

#### **Workflow:**

```
User/Admin uploads document
  ↓
Calls RAG: POST /api/v1/data/upload/123
  ↓
RAG stores file on disk → Returns file_id
  ↓
User/Admin processes document
  ↓
Calls RAG: POST /api/v1/data/process-and-push/123
    with file_id
  ↓
RAG chunks the document
  ↓
RAG embeds chunks using embedding model
  ↓
RAG indexes into Vector DB (Qdrant or PGVector)
  ↓
Documents now searchable for RAG chat
```

#### **Who Handles Uploads:**

- ❌ **NOT automatically triggered** by main backend
- ❌ **NOT webhook-based** (no events from main backend to RAG)
- ✅ **Manual operation**: Users/Admins explicitly call RAG endpoints
- ✅ **Independent systems**: RAG owns its document pipeline

#### **Future Enhancement (Optional):**

If auto-triggering is needed later, the main backend could:
```javascript
// In main backend project creation
const project = await createProject({...});

// Optionally notify RAG
await fetch("http://connexios:8000/api/v1/projects/sync", {
  method: "POST",
  headers: {
    "X-API-Key": process.env.CONNEXIO_RAG_API_KEY
  },
  body: JSON.stringify({
    project_id: project.PID,
    project_name: project.PName,
    action: "created"
  })
});
```

But **this is NOT implemented initially**. Start with manual uploads.

---

---

## 📊 Integration Architecture Summary

```
┌─────────────────────────────────────────────────────────────────┐
│                      FRONTEND (Browser)                         │
└────────────────────────┬────────────────────────────────────────┘
                         │ (JWT Token in Authorization header)
                         ↓
┌─────────────────────────────────────────────────────────────────┐
│           MAIN BACKEND (Connexio) - Port 5000                   │
│                                                                 │
│  - User Authentication (JWT)                                    │
│  - Project Management                                           │
│  - Team Coordination                                            │
│  - Database: PostgreSQL                                         │
│  - Tables: users, projects, project_members, tasks, etc.        │
└────────────────────────┬────────────────────────────────────────┘
                         │ (Validates user via JWT)
                         │ (Calls RAG endpoints with X-API-Key)
                         ↓
┌─────────────────────────────────────────────────────────────────┐
│         CONNEXIOS RAG SYSTEM - Port 8000                        │
│                                                                 │
│  - Document Ingestion & Indexing                               │
│  - Vector Search                                               │
│  - Agentic Chat                                                │
│  - Multi-source Retrieval                                      │
│  - Database: PostgreSQL + PGVector                             │
│                                                                │
│  Calls Main Backend REST APIs:                                 │
│    GET /api/users/{user_id}                                    │
│    GET /api/projects/{project_id}                              │
│    GET /api/projects/{project_id}/members                      │
│    GET /api/tasks?project_id={project_id}                      │
└─────────────────────────────────────────────────────────────────┘
```

#### **Communication Ports:**
- Frontend ↔ Main Backend: `http://connexio-backend:5000`
- Main Backend ↔ RAG: `http://connexios:8000` (internal only)
- Frontend ↔ RAG: **NOT direct** (goes through main backend)

#### **Authentication Flow:**
```
Frontend Request:
  Authorization: Bearer {jwt_token}
  ↓
Main Backend validates JWT
  ↓
Main Backend calls RAG with:
  X-API-Key: {shared_secret}
  Body: { user_id: 1, ... }
  ↓
RAG validates X-API-Key
  ↓
RAG trusts user_id → processes request
```

---

---

## 🚀 Implementation Checklist for Claude

### **Phase 1: Authentication & Security**
- [ ] Add `X-API-Key` validation middleware in RAG agent routes
- [ ] Add `.env` variables: `CONNEXIO_INTERNAL_API_KEY`
- [ ] Implement bearer token extraction in agent requests
- [ ] Add request logging for security audit trail

### **Phase 2: REST API Integration**
- [ ] Create `BackendApiClient` class in RAG to call main backend
- [ ] Implement HTTP client with retry logic and timeout
- [ ] Add error handling for failed API calls
- [ ] Cache user profiles to reduce API calls

### **Phase 3: Fix ToolManager Queries**
- [ ] Rewrite `get_matching_rationale()` to use REST API
- [ ] Rewrite `get_team_gaps()` to use REST API
- [ ] Remove SQL queries to non-existent `technology` tables
- [ ] Add proper error messages when data unavailable

### **Phase 4: Project ID Synchronization**
- [ ] Accept main backend `PID` in RAG URL paths
- [ ] Map RAG's `project_uuid` to main backend's `PID`
- [ ] Validate project_id exists on main backend before processing

### **Phase 5: Documentation**
- [ ] Add integration guide to both backends
- [ ] Document shared secret setup
- [ ] Create troubleshooting guide

### **Phase 6: Testing**
- [ ] Test end-to-end user auth flow
- [ ] Test API key validation
- [ ] Test project data retrieval
- [ ] Test error handling for invalid users/projects

---

---

## 📝 Environment Variables Needed

### **Main Backend `(.env`)**
```env
CONNEXIO_RAG_API_KEY=connexio_rag_shared_secret_2024_prod_only
JWT_SECRET=your-main-backend-jwt-secret
JWT_EXPIRES_IN=7d
```

### **RAG Backend (.env)**
```env
CONNEXIO_INTERNAL_API_KEY=connexio_rag_shared_secret_2024_prod_only
MAIN_BACKEND_URL=http://connexio-backend:5000
POSTGRES_USERNAME=postgres
POSTGRES_PASSWORD=123456
POSTGRES_HOST=172.17.80.1
POSTGRES_PORT=5433
POSTGRES_MAIN_DATABASE=connexio
```

---

---

## ✅ Ready for Implementation

This document provides Claude with:
1. ✅ Exact authentication mechanism
2. ✅ Database schema and API endpoints
3. ✅ Project identifier format
4. ✅ Document ingestion flow
5. ✅ Implementation checklist
6. ✅ Environment configuration

**Claude can now proceed with integration code without further ambiguities.**
