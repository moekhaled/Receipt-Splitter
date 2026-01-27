import json
import re
from typing import Any, Dict, Optional

_JSON_BLOCK_RE = re.compile(r"\{.*\}", re.DOTALL)

def extract_json_object(text: str) -> Optional[Dict[str, Any]]:
    if not text:
        return None
    t = text.strip()

    # direct
    try:
        obj = json.loads(t)
        return obj if isinstance(obj, dict) else None
    except Exception:
        pass

    # strip code fences
    if "```" in t:
        stripped = re.sub(r"^```(?:json)?\s*|\s*```$", "", t, flags=re.IGNORECASE | re.MULTILINE).strip()
        try:
            obj = json.loads(stripped)
            return obj if isinstance(obj, dict) else None
        except Exception:
            pass

    # find {...}
    m = _JSON_BLOCK_RE.search(t)
    if not m:
        return None
    try:
        obj = json.loads(m.group(0))
        return obj if isinstance(obj, dict) else None
    except Exception:
        return None
