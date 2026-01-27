import os
from typing import Any, Dict

import httpx

BACKEND_BASE_URL = os.getenv("BACKEND_BASE_URL", "http://backend:8000").rstrip("/")
TIMEOUT_S = float(os.getenv("BACKEND_TIMEOUT_S", "15"))


async def get_session_context(session_id: int) -> Dict[str, Any]:
    url = f"{BACKEND_BASE_URL}/api/sessions/{session_id}/context/"
    async with httpx.AsyncClient(timeout=TIMEOUT_S) as client:
        try:
            r = await client.get(url)
            r.raise_for_status()
            return r.json()
        except Exception:
            # Match your current robustness: AI should still function even if context fetch fails
            return {"session_id": session_id, "people": []}


async def execute_action(envelope: Dict[str, Any]) -> Dict[str, Any]:
    url = f"{BACKEND_BASE_URL}/api/ai/execute/"
    async with httpx.AsyncClient(timeout=TIMEOUT_S) as client:
        r = await client.post(url, json=envelope)
        try:
            return r.json()
        except Exception:
            return {"ok": False, "message": "Backend returned non-JSON response.", "status": r.status_code}
