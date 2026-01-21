# Receipt Splitter (Order Splitter) — Django Expense & Receipt Splitting App

Receipt Splitter is a Django web application for splitting shared expenses across **sessions** (think: a receipt for a dinner, group order, trip purchase, etc.). A session contains **people**, and each person has **items** (name, price, quantity). The app calculates totals per person and applies session-level **VAT (tax)**, **service**, and **discount**.

The project focuses on clean, scalable structure using Django CBVs — and now includes an **AI assistant** that can create/edit sessions from natural language prompts.

---

## Live Demo

Try the hosted app here: https://receipt-splitter-omvm.onrender.com/

Note: The Render instance may **spin down when idle**. On your first visit it can take up to **~50 seconds** to wake up.

---


## Key Features

### Core App
- **Session-based grouping** (each session = one receipt)
- **People inside sessions**, **items inside people**
- Per-item: `name`, `price`, `quantity`
- Session-level adjustments:
  - **VAT** (stored in DB as `tax`)
  - **service**
  - **discount**
- Automatic calculations:
  - Session subtotal from item totals
  - Session total with VAT/service/discount applied
  - Per-person totals (raw + adjusted)

### UI / Views
- Session list + session detail views
- Detailed session breakdown view (prefetches people + items)
- Full CRUD:
  - Sessions: create, edit, delete
  - People: create, edit, delete (scoped under a session)
  - Items: create (under a person), edit, delete

---

## AI Assistant (Natural Language → Actions)

The app includes an AI endpoint that accepts natural language and returns a structured action the server can validate and execute.

### What it can do (current)
1. **General questions** about the app (“what can you do?”, “how does VAT work?”)
2. **Create a session** from a prompt (optionally with people + items)
3. **Edit a session** (title / VAT / service / discount)
4. **Edit people inside a session** (add / rename / delete)
5. **Edit items inside a session** (add / update / delete / move between people)
6. **Batch editing (multi-operations)**: apply multiple people/items edits in a single prompt (e.g., add a person + add items + rename someone)

### How it works
- The assistant is powered by **Google Gemini** via `google-genai`.
- The model is forced into **JSON output** and constrained by a **Pydantic JSON schema**.
- The server then:
  1. stores chat history (in Django session)
  2. validates the AI output
  3. executes DB writes in a transaction
  4. returns a JSON response (plus re-rendered chat HTML)

### Important mapping: VAT vs DB field name
- The AI speaks in terms of **`vat`**
- The database field is **`tax`**
- Creation + updates map: `vat → tax`

---

## AI Endpoints

### `GET /ai/csrf/`
Sets the CSRF cookie so the frontend can POST safely.

### `POST /ai/parse/`
Accepts JSON payload:
```json
{
  "prompt": "create a dinner for Ali and Sara...",
  "context": { "session_id": 12 }
}
```

Returns:
```json
{
  "response": "✅ Created session '...' with 2 people and 5 items.",
  "action": "redirect|none",
  "redirect_url": "/sessions/12/",
  "html": "<rendered chat messages html...>"
}
```

Notes:
- Chat history is stored server-side in the Django session (trimmed to a max number of turns + max chars per message).
- If intent requires a session id and it isn’t provided by the model, the server can fall back to `context.session_id` (when available).

---

## Data Model

### `Session`
- `title`
- `tax` (AI calls it `vat`)
- `service`
- `discount`
- `created_at`
- Methods: `subtotal()`, `total()`, `taxed(amount)`

### `Person`
- `name`
- `session` (FK)
- Methods: `calculate_amount()`, `calculate_taxed_amount()`

### `Item`
- `name`
- `price` (> 0)
- `quantity` (>= 1)
- `person` (FK)
- Method: `total()` (`price * quantity`)

---

## AI Schemas (Strict JSON)

The AI is constrained to one of these intents:

### `general_inquiry`
```json
{ "intent": "general_inquiry", "answer": "..." }
```

### `create_session`
```json
{
  "intent": "create_session",
  "session": { "title": "...", "vat": 14, "service": 10, "discount": 0 },
  "people": [
    { "name": "Ali", "items": [{ "name": "Burger", "price": 120, "quantity": 1 }] }
  ]
}
```

### `edit_session`
```json
{
  "intent": "edit_session",
  "session_id": 12,
  "session_query": null,
  "updates": { "vat": 14, "service": 12 }
}
```

### `edit_person`
```json
{
  "intent": "edit_person",
  "session_id": 12,
  "operation": "rename",
  "person_id": 55,
  "new_name": "Moe"
}
```

### `edit_item`
```json
{
  "intent": "edit_item",
  "session_id": 12,
  "operation": "update",
  "item_id": 901,
  "updates": { "quantity": 2 }
}
```

### `edit_session_entities` (batch operations)
```json
{
  "intent": "edit_session_entities",
  "session_id": 12,
  "operations": [
    { "intent": "edit_person", "operation": "add", "new_name": "Saaeed" },
    { "intent": "edit_item", "operation": "add", "to_person_id": 55, "name": "Pepsi", "price": 30, "quantity": 2 },
    { "intent": "edit_person", "operation": "rename", "person_id": 10, "new_name": "Moe" }
  ]
}
```

Validation rules enforced server-side:
- VAT/service/discount must be between **0–100**
- Item price must be **> 0**
- Quantity must be **>= 1** (defaults to 1)
- `create_session` requires **at least 1 person**
- `edit_session` requires either `session_id` or `session_query`, plus at least one field in `updates`
- `edit_person` / `edit_item` enforce required fields per operation
- Batch operations require a non-empty `operations[]` list, and each operation must validate independently

---

## Tech Stack

- **Django** (CBVs, templates, server-side rendering)
- **SQLite** (default; easy to switch to Postgres)
- **Pydantic** for schema validation + JSON schema generation
- **Google Gemini (google-genai)** for structured JSON actions

---

## Local Setup

### 1) Create & activate a virtual env
```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
```

### 2) Install dependencies
```bash
pip install -r requirements.txt
```

### 3) Configure environment variables (AI)
Set:
- `GEMINI_API_KEY` (used automatically by the Gemini client)

Example:
```bash
export GEMINI_API_KEY="your_key_here"
```

### 4) Run migrations + start server
```bash
python manage.py migrate
python manage.py runserver
```

Open:
- Sessions list: `/sessions/`
- AI endpoints: `/ai/csrf/`, `/ai/parse/`

---

## URL Structure Overview

- `/sessions/` — list sessions
- `/sessions/add/` — create session
- `/sessions/<id>/` — session details
- `/sessions/<id>/details/` — detailed breakdown
- `/sessions/<id>/edit/` — edit session
- `/sessions/<id>/delete/` — delete session

- `/sessions/<session_id>/persons/` — list people in session
- `/sessions/<session_id>/persons/add/` — add person
- `/sessions/<session_id>/persons/<person_id>/` — person details
- `/sessions/<session_id>/persons/<person_id>/alter/` — edit person
- `/sessions/<session_id>/persons/<person_id>/delete/` — delete person

- `/sessions/<session_id>/persons/<person_id>/add-item/` — add item to person
- `/items/<item_id>/alter/` — edit item
- `/items/<item_id>/delete/` — delete item

- `/ai/csrf/` — CSRF cookie helper for AI UI
- `/ai/parse/` — AI prompt → action endpoint

---

## Project Direction / Next Ideas

- Authentication (users + private sessions)
- Upload receipt text/image → parse into structured items (OCR + extraction flow)
- Postgres + deployment hardening
