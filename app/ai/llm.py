import json
from typing import Any, Dict, Optional

from google import genai
from google.genai import types

from .prompts import SYSTEM_PROMPT
from .schemas import CreateSessionAction, AIAction 

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

def to_gemini_contents(history):
    from google.genai import types

    contents = []
    for m in history:
        role = "user" if m["role"] == "user" else "model"  # assistant -> model
        contents.append(types.Content(role=role, parts=[types.Part(text=m["content"])]))
    return contents

def parse_receipt_prompt(user_prompt: str, history=None) -> Dict[str, Any]:
    """
    Returns a dict that matches one of the existing schemas, or {} if invalid.
    """
    user_prompt = (user_prompt or "").strip()
    if not user_prompt:
        return {}

    # Choose a fast, good default model; you can change later.
    # Docs show 'gemini-2.5-flash' commonly in examples. :contentReference[oaicite:2]{index=2}
    model_id = "gemini-3-flash-preview"
    contents=to_gemini_contents(history)
    response = client.models.generate_content(
        model=model_id,
        contents=contents,
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_PROMPT,          # system prompt :contentReference[oaicite:3]{index=3}
            temperature=0.1,
            response_mime_type="application/json",     # JSON mode :contentReference[oaicite:4]{index=4}
            response_json_schema=AIAction.model_json_schema(),  # schema :contentReference[oaicite:5]{index=5}
        ),
    )

    raw = (response.text or "").strip()
    data = _safe_json_loads(raw)
    if not data:
        return {}

    # Validate strictly (ensures your DB logic gets clean data)
    try:
        validated = AIAction.model_validate(data)
        return validated.root.model_dump()
    except Exception:
        return {}
