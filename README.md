# Order Splitter (Microservices)

This branch refactors the original monolithic Django app into a small microservice-style setup while keeping the core AI contract intact:

- **The LLM returns JSON only**
- The JSON is **validated**
- Valid actions are **executed by backend services** (DB writes happen in the backend)

## Architecture

The application is split into **4 components**:

1. **Frontend (Django SSR)**
   - Renders HTML templates and serves the user-facing pages.
   - **Does not write to the database**.
   - Delegates all write operations to the backend via HTTP.

2. **Backend (Django API)**
   - Exposes `/api/...` endpoints.
   - **Only service that writes to the DB**.
   - Validates AI payloads and runs `services.py` executors.

3. **AI Service (Django)**
   - Exposes `/ai/...` endpoints.
   - Fetches read-only context from the backend.
   - Calls the LLM and forwards `{intent, ai_data}` to the backend to execute changes.

4. **Database**
   - Postgres (Docker container).
   - Shared by services (initially), but writes are enforced by design through backend only.

### Request routing (nginx)

A single nginx entrypoint routes traffic by path:

- `/` → `frontend:8000`
- `/api/` → `backend:8000`
- `/ai/` → `ai:8000`

## Repository layout (key files)

- `services/nginx/default.conf` — nginx routing rules
- `services/frontend/Dockerfile` — builds the frontend image
- `services/backend/Dockerfile` — builds the backend image
- `services/ai/Dockerfile` — builds the AI image
- `docker-compose.yml` — runs all services together
- `app/views.py` — **frontend views only** (SSR + delegates writes to backend)
- `app/ai_views.py` — **AI endpoints only** (`/ai/csrf/`, `/ai/parse/`)
- `app/api_views.py` — **backend API endpoints** (`/api/...`)
- `app/web_urls.py`, `app/ai_urls.py`, `app/api_urls.py` — split URL routing
- `order_splitter/urls_frontend.py`, `urls_backend.py`, `urls_ai.py` — per-service root URLConfs
- `order_splitter/settings_frontend.py`, `settings_backend.py`, `settings_ai.py` — per-service settings modules

## Environment variables

Create a file named `.env` at the repo root:

```env
DJANGO_SECRET_KEY=change-me-super-secret
GEMINI_API_KEY=put-your-key-here
```

Notes:
- **All services should share the same `DJANGO_SECRET_KEY`** so sessions/cookies behave consistently.
- `GEMINI_API_KEY` is needed by the **AI service**.
- `BACKEND_URL` is configured in compose for frontend/ai to call the backend.

## Running with Docker

From the repo root:

```bash
docker compose up --build
```

Then open (depending on your host port mapping):
- `http://localhost:8081/` (or `http://localhost:8080/`) — Frontend UI
- `http://localhost:8081/api/health/` — Backend health check
- `http://localhost:8081/ai/csrf/` — AI csrf endpoint
- `http://localhost:8081/ai/parse/` — AI parse endpoint (POST)

### Useful commands

```bash
docker compose ps
docker compose logs -f frontend
docker compose logs -f backend
docker compose logs -f ai
docker compose logs -f nginx
```

## How AI changes are applied

1. Frontend sends prompt to AI endpoint (`POST /ai/parse/`)
2. AI service fetches session context from backend (`GET /api/sessions/<id>/context/`)
3. AI service calls the LLM (Gemini) and expects **strict JSON**
4. AI service forwards `{intent, ai_data}` to backend (`POST /api/ai/execute/`)
5. Backend validates payload and executes DB writes via `app/ai/validation.py` + `app/ai/services.py`
6. Backend returns `{ok, message, redirect_url?}`

## Troubleshooting

### CSS not loading / paths look wrong
Ensure:

```python
STATIC_URL = "/static/"
```

and static serving is enabled (e.g., WhiteNoise or nginx static config).

### CSRF Origin checking failed
Add your development origins in settings:

```python
CSRF_TRUSTED_ORIGINS = [
  "http://localhost:8081",
  "http://127.0.0.1:8081",
  "http://localhost:8000",
  "http://127.0.0.1:8000",
]
```

### AI timeouts / worker timeout
LLM responses can be slow or overloaded.
Consider increasing AI gunicorn timeout (AI container only), and handle LLM errors gracefully.

## License

Internal / private project (update as needed).
