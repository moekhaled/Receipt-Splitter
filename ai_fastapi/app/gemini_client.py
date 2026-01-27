import os
import httpx


class GeminiClient:
    def __init__(self):
        self.api_key = os.getenv("GEMINI_API_KEY", "").strip()
        self.model = os.getenv("GEMINI_MODEL", "gemini-1.5-flash").strip()
        self.timeout_s = float(os.getenv("GEMINI_TIMEOUT_S", "30"))
        if not self.api_key:
            raise RuntimeError("GEMINI_API_KEY is not set")

    async def generate(self, system_prompt: str, user_prompt: str) -> str:
        url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/"
            f"{self.model}:generateContent?key={self.api_key}"
        )
        payload = {
            "contents": [{"role": "user", "parts": [{"text": f"{system_prompt}\n\n{user_prompt}"}]}],
            "generationConfig": {"temperature": 0.2},
        }
        async with httpx.AsyncClient(timeout=self.timeout_s) as client:
            try:
                r = await client.post(url, json=payload)
                # Don't crash; return empty on failure
                if r.status_code >= 400:
                    return ""
                data = r.json()
            except Exception:
                return ""

        try:
            return (data["candidates"][0]["content"]["parts"][0]["text"] or "").strip()
        except Exception:
            return ""
