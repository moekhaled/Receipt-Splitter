# Receipt Splitter (Microservices)

Receipt Splitter is a containerized, contract-driven microservices app for splitting receipts among people.
It is deployed as multiple services behind an nginx reverse proxy and is built around a hard boundary:

> **Only the backend writes to the database.**  
> The frontend (SSR) and AI service communicate with the backend over HTTP.

---

## Runtime architecture

The stack runs as **5 containers** via Docker Compose:

- **nginx** — single public entrypoint; routes requests by path prefix
- **frontend** — **Django SSR** UI (HTML rendering + session-based UI endpoints)
- **backend** — **Django API** service (**the only DB writer**; owns migrations)
- **ai** — **FastAPI** AI service (Gemini/LLM caller + contract validation)
- **db** — Postgres (persistent named volume)

### Request routing (nginx)

nginx routes requests by URL prefix:

- `/` → **frontend**
- `/api/` → **backend**
- `/ai/` → **ai**

> **Important:** Frontend-only endpoints must **not** live under `/ai/`, because nginx forwards `/ai/*` to the AI service.

---

## Quickstart (Docker)

### 1) Prerequisites

- Docker + Docker Compose

### 2) Configure environment

Create a `.env` file at the repo root (do **not** commit it). Example:

```bash
# Frontend (Django SSR)
DJANGO_SECRET_KEY=change-me

# AI (Gemini)
GEMINI_API_KEY=your-gemini-api-key

# Database
DB_NAME=receipt_splitter
DB_USER=receipt_splitter
DB_PASSWORD=receipt_splitter
DB_HOST=db
DB_PORT=5432
```

### 3) Boot the stack

From the repository root:

```bash
docker compose -f infra/docker-compose.yml up --build
```

### 4) Run database migrations (backend owns schema)

In another terminal:

```bash
docker compose -f infra/docker-compose.yml exec backend python manage.py migrate
```

### 5) Open the app

Open the nginx entrypoint in your browser:

- `http://localhost:<NGINX_PORT>/`

(Port mapping is defined in `infra/docker-compose.yml`.)

---

## End-to-end flows

### A) UI reads (SSR page loads)

1. Browser → `GET /` (nginx → **frontend**)
2. Frontend SSR calls backend over HTTP for data reads (`/api/...`)
3. Frontend renders templates using backend JSON responses (no cross-service ORM access)

### B) Chat + AI execution flow

1. Browser → frontend chat UI
2. Frontend → `POST /ai/parse/` with:

```json
{
  "message": "user prompt",
  "history": [{"role": "user|assistant", "content": "..."}],
  "session_id": "..."
}
```

3. AI service fetches receipt/session context from the backend as needed (read-only)
4. AI calls Gemini and produces a structured **contract envelope**:

```json
{ "intent": "<intent_name>", "ai_data": { /* intent payload */ } }
```

5. **Validation happens twice**
   - AI validates the LLM output against the shared contracts package
   - Backend validates again before executing any DB writes

6. If the intent is **actionable** (create/edit), AI forwards it to the backend for execution
7. Backend performs the DB write and returns an execution result (often includes a `redirect_url`)
8. Frontend uses the result to refresh UI state / redirect

### C) Frontend-owned history persistence (sessions)

Chat history persistence is owned by the **frontend** using Django sessions:

- `POST /history/append/` with `{ "role": "...", "content": "..." }`

This endpoint is intentionally **not** under `/ai/` to avoid nginx routing it to the AI service.

---

## Shared contracts (single source of truth)

**Path:** `packages/receipt_splitter_contracts/`

This package defines the schema shared between services, including:

- the AI envelope shape: `{ intent, ai_data }`
- intent definitions (action vs non-action) and payload models/validators

### Why contracts matter

- The AI service uses contracts to ensure LLM output is structured and safe to forward.
- The backend uses contracts to ensure only valid, expected actions can write to the database.

If you change an intent payload, update **contracts first**, then update **AI** and **backend** together.

---

## Service boundaries

### Frontend (Django SSR)

- Owns HTML rendering and user-facing UX
- Stores UI session state (chat history) via Django sessions
- Performs **reads** by calling the backend API over HTTP
- Does **not** write to Postgres

### Backend (Django API)

- Exposes `/api/...`
- **Only service that writes to Postgres**
- Owns the data model and schema migrations (`python manage.py migrate`)
- Validates and executes contract-based AI actions

### AI service (FastAPI)

- Exposes `/ai/...` (notably `POST /ai/parse/`)
- Fetches receipt/session context from backend as needed
- Calls Gemini and emits contract envelopes
- Forwards actionable intents to backend; answers non-action queries directly

### Database (Postgres)

- Persistent named volume (data survives container restarts)
- Backend is the schema owner and only writer

---

## Repo layout

- `frontend/` — Django SSR service
- `backend/` — Django API service (DB writer)
- `ai_fastapi/` — FastAPI AI service (Gemini client + contract envelope + validation)
- `ai_Django_LEGACY/` — legacy Django AI module (retained for reference; **not used**)
- `infra/` — Docker Compose + nginx configuration
- `packages/receipt_splitter_contracts/` — shared contract package (AI + backend)

---

## Useful Docker commands

```bash
# show running containers
docker compose -f infra/docker-compose.yml ps

# follow logs (service names come from infra/docker-compose.yml)
docker compose -f infra/docker-compose.yml logs -f nginx
docker compose -f infra/docker-compose.yml logs -f frontend
docker compose -f infra/docker-compose.yml logs -f backend
docker compose -f infra/docker-compose.yml logs -f ai
docker compose -f infra/docker-compose.yml logs -f db
```

### Stop / reset

Stop containers (keeps DB volume):

```bash
docker compose -f infra/docker-compose.yml down
```

Reset everything including the database volume (**destructive**):

```bash
docker compose -f infra/docker-compose.yml down -v
```

---

## Notes for contributors

- Keep **nginx routes** stable: `/` (frontend), `/api/` (backend), `/ai/` (AI).
- Preserve the invariant: **backend is the only DB writer**.
- Treat `packages/receipt_splitter_contracts/` as the **API compatibility layer** between AI and backend.

---

## License

Internal / private project (update as needed).
