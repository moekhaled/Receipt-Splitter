# Receipt Splitter (Microservices)

This branch refactors the original monolithic Django app into a microservice-style setup while keeping the core AI contract intact:

- The LLM returns **JSON only**
- The JSON is **validated**
- Valid actions are **executed by backend services** (DB writes happen in the backend)

> Note: During the split we intentionally kept some duplicated/legacy modules in place for safety.
> These will be cleaned up in a follow-up commit once the migration is fully stable.

---

## Architecture

The application is split into **4 components**:

1. **Frontend (Django SSR)**
   - Renders HTML templates and serves user-facing pages.
   - Reads data via HTTP from the backend API.
   - Delegates all write operations to the backend via HTTP.

2. **Backend (Django API)**
   - Exposes `/api/...` endpoints.
   - **Only service that writes to the DB**.
   - Validates AI envelopes and executes actions via the backend AI execution layer.

3. **AI Service (Django)**
   - Exposes `/ai/...` endpoints (e.g. `/ai/parse/`).
   - Fetches read-only context from the backend (e.g. `/api/sessions/<id>/context/`).
   - Calls the LLM (Gemini) and forwards `{intent, ai_data}` to the backend writer.

4. **Database (Postgres)**
   - Postgres 16 running as a Docker container.
   - Persistent storage via Docker named volume.

---

## Request routing (nginx)

A single nginx entrypoint routes traffic by path:

- `/` → `frontend:8000`
- `/api/` → `backend:8000`
- `/ai/` → `ai:8080`

Important:
- Any **frontend-only** endpoints must **NOT** be under `/ai/` because nginx forwards `/ai/` to the AI container.

---

## Repository layout (key files)

- `infra/docker-compose.yml` — runs all services together
- `services/nginx/default.conf` — nginx routing rules
- `services/frontend/Dockerfile` — builds the frontend image
- `services/backend/Dockerfile` — builds the backend image
- `services/ai/Dockerfile` — builds the AI image
- `packages/receipt_splitter_contracts/` — shared contract (intents + schema validation)

---

## Environment variables

Create a file named `.env` **in `infra/`**:

```env
DJANGO_SECRET_KEY=change-me-super-secret
GEMINI_API_KEY=put-your-key-here
```

Notes:
- All services should share the same `DJANGO_SECRET_KEY` so cookies/session behavior is consistent.
- `GEMINI_API_KEY` is required by the AI service.

---

## Running with Docker

From the repo root:

```bash
docker compose -f infra/docker-compose.yml up --build -d
```

### Run migrations (backend only)

Backend is the DB writer and owns schema:

```bash
docker compose -f infra/docker-compose.yml exec backend python manage.py migrate
```

Optional:
```bash
docker compose -f infra/docker-compose.yml exec backend python manage.py createsuperuser
```

---

## Makefile convenience

For Linux/Ubuntu (and anyone with `make` installed), you can use the included Makefile:

```bash
make up
```

This is a convenience wrapper around the full Docker Compose command. See the `Makefile` for available targets.

---

## Open the app

Depending on your port mapping (nginx), typically:

- `http://localhost:8000/` — Frontend UI
- `http://localhost:8000/api/...` — Backend API
- `http://localhost:8000/ai/...` — AI service endpoints

---

## How AI changes are applied

1. Frontend sends prompt to AI endpoint: `POST /ai/parse/`
   - Payload shape is:
     ```json
     { "message": "...", "history": [...], "session_id": 123 }
     ```
2. AI service fetches session context from backend: `GET /api/sessions/<id>/context/`
3. AI service calls the LLM (Gemini) and expects strict JSON output.
4. AI service validates `{intent, ai_data}` against shared contracts.
5. AI service forwards `{intent, ai_data}` to backend writer (e.g. `POST /api/ai/execute/`).
6. Backend validates payload and executes DB writes.
7. Backend returns `{ok, message, redirect_url?}` which is returned back to the frontend.

Important:
- Informational prompts like “how does this app work?” should be handled inside the AI service (no backend forwarding).
  Only actionable intents (create/edit) are forwarded.

---

## UI chat history (Django sessions)

Chat history is stored on the **frontend** using Django sessions.

The frontend exposes an endpoint to append a single message to session history:

- `POST /history/append/` — body: `{ "role": "user"|"assistant", "content": "..." }`

The UI/JS calls this endpoint after adding a real user/assistant message (and does **not** persist transient UI messages like “🤖 Thinking…”).

---

## Database persistence

Postgres data is stored in a Docker **named volume** (e.g. `db_data`). Data persists across container restarts and `docker compose down`, but will be deleted by `docker compose down -v` (volume removal).

---

## Useful commands

```bash
docker compose -f infra/docker-compose.yml ps
docker compose -f infra/docker-compose.yml logs -f frontend
docker compose -f infra/docker-compose.yml logs -f backend
docker compose -f infra/docker-compose.yml logs -f ai
docker compose -f infra/docker-compose.yml logs -f nginx
docker compose -f infra/docker-compose.yml logs -f db
```

Stop / start:

```bash
docker compose -f infra/docker-compose.yml down
docker compose -f infra/docker-compose.yml up -d
```

Reset including DB volume (destructive):

```bash
docker compose -f infra/docker-compose.yml down -v
```

---

## Troubleshooting

### DB auth errors (Postgres)
Ensure backend env matches Postgres container credentials:
- DB_HOST=db
- DB_NAME=receipt_splitter
- DB_USER=receipt_splitter
- DB_PASSWORD=receipt_splitter

### CSRF Origin checking failed
Add your development origins in settings:

```python
CSRF_TRUSTED_ORIGINS = [
  "http://localhost:8000",
  "http://127.0.0.1:8000",
]
```

---

## Housekeeping

- Local SQLite files (e.g. `db.sqlite3`) are development artifacts and should not be committed.
  Add them to `.gitignore` and remove from tracking if already committed.

---

## License

Internal / private project (update as needed).
