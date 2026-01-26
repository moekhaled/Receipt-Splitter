from __future__ import annotations

from typing import Any, Dict

from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError
from .intents import Intent 


AI_ENVELOPE_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "required": ["intent", "ai_data"],
    "additionalProperties": False,
    "properties": {
        "intent": {"type": "string", "minLength": 1},
        "ai_data": {"type": "object"},
    },
}

_envelope_validator = Draft202012Validator(AI_ENVELOPE_SCHEMA)


def validate_ai_envelope(payload: Dict[str, Any]) -> Dict[str, Any]:
    _envelope_validator.validate(payload)
    intent = payload.get("intent")
    if intent not in {i.value for i in Intent}:
        raise ValidationError(f"Unknown intent: {intent}")
    if not isinstance(payload.get("ai_data"), dict):
        raise ValidationError("ai_data must be an object")

    return payload
