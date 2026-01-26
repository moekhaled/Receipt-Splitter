import json
from typing import Any, Dict, Optional, List

from google import genai
from google.genai import types

from .prompts import SYSTEM_PROMPT
from .schemas import AIAction

# Uses GEMINI_API_KEY automatically (recommended)
client = genai.Client()


def _safe_json_loads(text: str) -> Dict[str, Any]:
    if not text:
        return {}
    try:
        data = json.loads(text)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def to_gemini_contents(history: List[Dict[str, str]]) -> List[types.Content]:
    contents: List[types.Content] = []
    for m in history:
        role = "user" if m.get("role") == "user" else "model"  # assistant -> model
        contents.append(types.Content(role=role, parts=[types.Part(text=m.get("content", ""))]))
    return contents


def parse_receipt_prompt(
    user_prompt: str,
    history: Optional[List[Dict[str, str]]] = None,
    *,
    context: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
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

    model_id = "gemini-3-flash-preview"

    system = SYSTEM_PROMPT
    if context:
        system += "\n\nCURRENT_SESSION_CONTEXT_JSON:\n" + json.dumps(context, ensure_ascii=False)

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

    raw = (response.text or "").strip()
    data = _safe_json_loads(raw)
    if not data:
        return {}

    try:
        validated = AIAction.model_validate(data)
        return validated.root.model_dump(exclude_none=True)
    except Exception:
        return {}
