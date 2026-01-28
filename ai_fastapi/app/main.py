import os
from typing import Any, Dict, List, Optional, Literal
import json
from fastapi import FastAPI
from pydantic import BaseModel, Field
import anyio
from receipt_splitter_contracts.schemas import validate_ai_envelope  # shared contracts

from .backend_client import get_session_context, execute_action
from google import genai
from google.genai import types

from .prompts import SYSTEM_PROMPT
from .llm_schema import AIAction


class HistoryMsg(BaseModel):
    role: Literal["user", "assistant", "system"]
    content: str


class ParseRequest(BaseModel):
    message: str
    history: List[HistoryMsg] = Field(default_factory=list)
    session_id: Optional[int] = None


app = FastAPI(title="Receipt Splitter AI (FastAPI)")
client = genai.Client()

@app.get("/ai/health/")
async def health():
    return {"ok": True, "service": "ai_fastapi"}

def to_gemini_contents(history: List[Dict[str, str]]) -> List[types.Content]:
    contents: List[types.Content] = []
    for m in history:
        role = "user" if m.get("role") == "user" else "model"  # assistant -> model
        contents.append(types.Content(role=role, parts=[types.Part(text=m.get("content", ""))]))
    return contents
def _safe_json_loads(text: str) -> Dict[str, Any]:
    if not text:
        return {}
    try:
        data = json.loads(text)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}

def parse_receipt_prompt(user_prompt: str, history: Optional[List[Dict[str, str]]] = None, *, context: Optional[Dict[str, Any]] = None,) -> Dict[str, Any]:
    """
    Returns a dict that matches AIAction schema, or {} if invalid.
    """
    user_prompt = (user_prompt or "").strip()
    if not user_prompt:
        return {}

    history = history or []
    # Ensure current user message is included
    if not history or history[-1].get("role") != "user" or history[-1].get("content") != user_prompt:
        history = history + [{"role": "user", "content": user_prompt}]

    model_id = os.getenv("GEMINI_MODEL") or "gemini-3-flash-preview"

    system = SYSTEM_PROMPT
    if context:
        system += "\n\nCURRENT_SESSION_CONTEXT_JSON:\n" + json.dumps(context, ensure_ascii=False)
    try:
        response = client.models.generate_content(
            model=model_id,
            contents=to_gemini_contents(history),
            config=types.GenerateContentConfig(
                system_instruction=system,
                temperature=0.1,
                response_mime_type="application/json",
                response_json_schema=AIAction.model_json_schema(),
            ),
        )
    except Exception as e:
        print("Gemini error:", repr(e))
        return {}

    raw = (response.text or "").strip()
    data = _safe_json_loads(raw)
    if not data:
        return {}

    try:
        validated = AIAction.model_validate(data)
        return validated.root.model_dump(exclude_none=True)
    except Exception:
        return {}

@app.post("/ai/parse/")
async def parse(req: ParseRequest):
    # 1) Fetch context (optional)
    context = None
    if req.session_id is not None:
        context = await get_session_context(req.session_id)

    # 2) Call Gemini
    history = [m.model_dump() for m in req.history]
    parsed = await anyio.to_thread.run_sync(
        lambda: parse_receipt_prompt(req.message, history, context=context)
        )
    if not parsed:
        return {"ok": False, "message": "AI is temporarily unavailable. Please try again."}
    # 3) Extract + validate envelope
    intent = (parsed.get("intent") or "").strip()
    ai_data = dict(parsed)
    ai_data.pop("intent", None)

    envelope = {"intent": intent, "ai_data": ai_data}

    try:
        validate_ai_envelope(envelope)
    except Exception as e:
        return {"ok": False, "message": "AI response failed contract validation.", "errors": [str(e)],"intent":intent , "raw": ai_data}


    # 4) If informational, answer directly
    if intent == "general_inquiry":
        answer = (ai_data.get("answer") or "").strip()
        return {"ok": True, "message": answer}

    # 5) Otherwise forward to backend writer and return backend response as-is
    return await execute_action({"intent": intent, "ai_data": ai_data})
