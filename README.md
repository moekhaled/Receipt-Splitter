# Receipt Splitter (Microservices)

This repository contains a receipt-splitting application that was originally a single Django project and has now been **physically split into three separate Django services** (each with its own Dockerfile) plus shared infrastructure in `infra/`.

The system preserves the core contract-driven AI workflow:
- The LLM produces **structured JSON**
- JSON is **validated** against shared contracts
- **Only the backend** performs database writes

---

## Services

### 1) Frontend (Django SSR)
- Renders HTML pages (server-side rendered).
- Reads data from the backend over HTTP.
- Hosts UI-only helpers such as **chat-history persistence** using Django sessions.

### 2) Backend (Django API + DB writer)
- Exposes `/api/...` endpoints.
- **Single source of truth** for persistence.
- Owns database schema and migrations (Postgres).

### 3) AI Service (Django)
- Exposes `/ai/...` endpoints (notably `POST /ai/parse/`).
- Fetches receipt/session context from the backend.
- Calls the LLM (Gemini) and forwards validated action envelopes to the backend writer.

### 4) Infrastructure
Located under `infra/`:
- `infra/docker-compose.yml` — orchestrates all containers
- `infra/nginx/` — nginx config used to route traffic
- Postgres container + a persistent Docker volume

---

## Routing (nginx)

nginx routes requests by path prefix:

- `/` → frontend
- `/api/` → backend
- `/ai/` → ai service

⚠️ Important: frontend-only endpoints must **not** live under `/ai/` (because nginx forwards `/ai/` to the AI service).

---

## Repository layout (high-level)

- `ai/` — AI Django project (Gemini + intent envelope creation)
  - `ai_app/`, `ai_core/`, `ai_service/`, `Dockerfile`, `manage.py`, `requirements.txt`
- `backend/` — Backend Django project (API + DB writer)
  - `app/`, `order_splitter/`, `Dockerfile`, `manage.py`, `requirements.txt`
- `frontend/` — Frontend Django project (SSR UI)
  - `frontend_service/`, `webapp/`, `Dockerfile`, `manage.py`, `requirements.txt`
- `infra/`
  - `docker-compose.yml` — orchestrates containers
  - `nginx/` — nginx config (routing)
- `packages/` — shared packages (e.g., `receipt_splitter_contracts/`)
- `venv/` — local dev virtualenv (not used by Docker; should be ignored)
- `.env` — local secrets (should NOT be committed)


---

## Environment variables

Create `.env` (do not commit it):

```env
DJANGO_SECRET_KEY=change-me
GEMINI_API_KEY=change-me
```

If you keep DB credentials configurable, also add (or rely on compose defaults):

```env
DB_NAME=receipt_splitter
DB_USER=receipt_splitter
DB_PASSWORD=receipt_splitter
DB_HOST=db
DB_PORT=5432
```

---

## Run locally (Docker)

From the repository root:

```bash
docker compose -f infra/docker-compose.yml up --build -d
```

### Run migrations (backend only)
On first run (or after model changes):

```bash
docker compose -f infra/docker-compose.yml exec backend python manage.py migrate
```

Optional:

```bash
docker compose -f infra/docker-compose.yml exec backend python manage.py createsuperuser
```

### Logs
```bash
docker compose -f infra/docker-compose.yml logs -f backend
docker compose -f infra/docker-compose.yml logs -f frontend
docker compose -f infra/docker-compose.yml logs -f ai
docker compose -f infra/docker-compose.yml logs -f nginx
docker compose -f infra/docker-compose.yml logs -f db
```

### Stop / reset
Stop containers (keeps DB volume):

```bash
docker compose -f infra/docker-compose.yml down
```

Reset everything including the database volume (destructive):

```bash
docker compose -f infra/docker-compose.yml down -v
```

---

## Makefile (optional convenience)

If you have `make` installed:

```bash
make up
```

See `Makefile` for available targets.

---

## AI flow (high level)

1. Frontend sends user prompt to AI:
   - `POST /ai/parse/`
   - payload shape: `{ "message": "...", "history": [...], "session_id": 123 }`
2. AI service optionally fetches context from backend (e.g. session context endpoint).
3. AI calls the LLM and produces a structured `{intent, ai_data}` envelope.
4. Envelope is validated using `packages/receipt_splitter_contracts`.
5. Action intents are forwarded to the backend writer (backend validates again and writes to DB).
6. Backend responds with `{ok, message, redirect_url?}` which is returned to the frontend.

Non-action queries (e.g. “how does this app work?”) should be answered by the AI service without forwarding to the backend writer.

---

## Chat history persistence (frontend sessions)

The UI persists chat history using **frontend Django sessions** so it survives reloads/redirects.

Frontend endpoint:
- `POST /history/append/`
  - body: `{ "role": "user"|"assistant", "content": "..." }`

(Transient UI messages like “🤖 Thinking…” should not be appended.)

---

## Housekeeping

- Do not commit local SQLite artifacts (e.g. `db.sqlite3`). Add them to `.gitignore` and remove from tracking if already committed.

---

## Next milestone

Migrate the **backend** from Django to **FastAPI** while preserving:
- `/api/...` surface behavior used by the frontend
- AI writer/execute endpoint semantics
- shared contracts validation (`receipt_splitter_contracts`)
