# Connexio RAG Model Integration Plan (Phased Execution)

This document is the phased blueprint for integrating the Connexio RAG Model with your frontend and backend teams. The tasks have been broken down into logical phases to ensure a smooth, step-by-step rollout.

> [!NOTE]
> This plan is saved and ready. **No code has been executed yet.** When you are ready, simply say "Start Phase 1" or "Execute the plan," and we will begin.

## Architecture Summary

- **Frontend Integration**: The frontend connects directly to Connexio _only_ for SSE streaming endpoints.
- **Backend Integration**: The main backend acts as an intermediary for all other REST API requests, pushing data to Connexio. Separate databases are maintained.
- **Security**: Service-to-service communication is secured via an `X-API-Key` HTTP header (or query param for streaming).
- **Infrastructure**: Connexio services will be packaged into a portable Docker Compose template for the backend team.

---

## Execution Phases

### Phase 1: Security & Access Control (Backend Prep)

We will secure the API so that only authorized clients (the main backend) can access it.

- **Task 1.1**: Add `CONNEXIO_INTERNAL_API_KEY` to `src/helpers/config.py` and `.env.example`.
- **Task 1.2**: Create a new security dependency in `src/utils/security.py` (or similar) that checks for the `X-API-Key` header.
- **Task 1.3**: _Crucial Edge Case:_ Modify the security dependency so it also accepts the API key via a URL query parameter (e.g., `?api_key=XYZ`). This is strictly necessary because native browser `EventSource` (used for SSE) cannot send custom HTTP headers.
- **Task 1.4**: Apply this security dependency to the `nlp`, `data`, and `agent` routers.

### Phase 2: CORS Configuration (Frontend Prep)

Since the frontend will connect directly to Connexio for streaming, we must configure Cross-Origin Resource Sharing.

- **Task 2.1**: Re-enable `CORSMiddleware` in `src/main.py`.
- **Task 2.2**: Add an `ALLOWED_ORIGINS` environment variable to `config.py` and `.env.example` (defaulting to `*` for easy local development).
- **Task 2.3**: Configure the middleware to allow the required headers and methods.

### Phase 3: Infrastructure Export (DevOps Integration)

We need to provide the backend/DevOps team with a clean way to spin up the Connexio stack alongside their own.

- **Task 3.1**: Create `docker-compose.export.yml` in the root directory.
- **Task 3.2**: Define the Connexio services (API, Celery, Qdrant, Postgres, Redis, RabbitMQ) inside this file.
- **Task 3.3**: Ensure all services are placed on a named Docker network (e.g., `connexio_network`) so the main backend container can easily route to `http://connexio_api:8080`.

### Phase 4: Documentation & API Contracts

Provide the exact instructions the frontend and backend teams need to connect.

- **Task 4.1**: Create `docs/streaming_integration.md` detailing how the frontend should connect to `/api/v1/nlp/agent/chat/stream/{project_id}` using `EventSource` and the `api_key` query parameter.
- **Task 4.2**: Update the Postman collection files in `src/postman/collections/` to include the new `X-API-Key` authorization header.
- **Task 4.3**: Update `README.md` to point the teams to the Swagger UI (`/docs`), the new Docker template, and the streaming documentation.

---

## Verification Plan

Once all phases are executed, we will verify the setup:

### Automated Tests

- Test API Key authentication via `curl` to verify standard endpoints block unauthorized requests.
- Verify CORS preflight `OPTIONS` requests succeed for the streaming endpoint.

### Manual Verification

- **Backend Team**: Spin up `docker-compose.export.yml` and verify they can hit the base endpoints with the API key.
- **Frontend Team**: Connect to the local Connexio instance and successfully stream a chat response using the `api_key` query parameter without triggering CORS errors.
