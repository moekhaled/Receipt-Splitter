from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional


@dataclass
class ValidationResult:
    ok: bool
    data: Dict[str, Any]
    errors: List[str]


def _as_number(x: Any) -> Optional[float]:
    try:
        if x is None:
            return None
        return float(x)
    except (TypeError, ValueError):
        return None


def _as_int(x: Any) -> Optional[int]:
    try:
        if x is None:
            return None
        return int(x)
    except (TypeError, ValueError):
        return None


def _clean_str(x: Any) -> str:
    return str(x).strip() if x is not None else ""


def validate_create_session_payload(ai_data: Dict[str, Any]) -> ValidationResult:
    """
    Validates and normalizes AI output for intent=create_session.

    Key behavior:
    - Requires at least 1 person.
    - Allows people to have ZERO items (items are optional at creation time).
    - If items are present, they are validated strictly.
    - Applies sensible defaults for missing fields.

    Returns:
      ValidationResult.ok = True/False
      ValidationResult.data = normalized data ready for DB execution
      ValidationResult.errors = list of human-friendly error messages
    """
    errors: List[str] = []

    if not isinstance(ai_data, dict) or not ai_data:
        return ValidationResult(
            False,
            {},
            ["I couldn’t understand the request. Try including at least one person name."],
        )

    intent = _clean_str(ai_data.get("intent"))
    if intent != "create_session":
        return ValidationResult(
            False,
            {},
            ["Unsupported intent. Please ask me to create a new receipt/session."],
        )

    session_in = ai_data.get("session") or {}
    if not isinstance(session_in, dict):
        session_in = {}

    # Title default
    title = _clean_str(session_in.get("title"))
    if not title:
        title = f"Receipt - {datetime.now().strftime('%b %d')}"

    # Percent fields with defaults
    vat = _as_number(session_in.get("vat"))
    service = _as_number(session_in.get("service"))
    discount = _as_number(session_in.get("discount"))

    vat = 0.0 if vat is None else vat
    service = 0.0 if service is None else service
    discount = 0.0 if discount is None else discount

    for field_name, value in [("VAT", vat), ("service fee", service), ("discount", discount)]:
        if value < 0 or value > 100:
            errors.append(f"{field_name} must be between 0 and 100.")

    people_in = ai_data.get("people") or []
    if not isinstance(people_in, list) or len(people_in) == 0:
        errors.append("Please include at least one person name.")
        return ValidationResult(False, {}, errors)

    normalized_people: List[Dict[str, Any]] = []

    for p_idx, person in enumerate(people_in, start=1):
        if not isinstance(person, dict):
            errors.append(f"Person #{p_idx} is invalid.")
            continue

        person_name = _clean_str(person.get("name"))
        if not person_name:
            errors.append(f"Person #{p_idx} is missing a name.")
            continue

        items_in = person.get("items")
        # ✅ Allow items to be missing or empty
        if items_in is None:
            items_in = []
        if not isinstance(items_in, list):
            errors.append(f"Items for {person_name} must be a list.")
            items_in = []

        normalized_items: List[Dict[str, Any]] = []
        for i_idx, item in enumerate(items_in, start=1):
            if not isinstance(item, dict):
                errors.append(f"Item #{i_idx} for {person_name} is invalid.")
                continue

            item_name = _clean_str(item.get("name"))
            if not item_name:
                errors.append(f"An item for {person_name} is missing a name.")
                continue

            price = _as_number(item.get("price"))
            if price is None or price <= 0:
                errors.append(f"Item '{item_name}' for {person_name} must have a positive price.")
                continue

            qty = _as_int(item.get("quantity"))
            if qty is None:
                qty = 1
            if qty < 1:
                errors.append(f"Item '{item_name}' for {person_name} must have quantity >= 1.")
                continue

            normalized_items.append(
                {
                    "name": item_name,
                    "price": float(price),
                    "quantity": int(qty),
                }
            )

        # ✅ No error if normalized_items is empty
        normalized_people.append(
            {
                "name": person_name,
                "items": normalized_items,
            }
        )

    # Still require at least one valid person
    if len(normalized_people) == 0:
        errors.append("Please include at least one valid person name.")
        return ValidationResult(False, {}, errors)

    if errors:
        return ValidationResult(False, {}, errors)

    normalized = {
        "intent": "create_session",
        "session": {
            "title": title,
            "vat": float(vat),
            "service": float(service),
            "discount": float(discount),
        },
        "people": normalized_people,
    }

    return ValidationResult(True, normalized, [])
def validate_edit_session_payload(ai_data: Dict[str, Any]) -> ValidationResult:
    """
    Normalizes/validates intent=edit_session.

    Accepts:
      - session_id OR session_query
      - updates: title/vat/service/discount (any subset)
    """
    errors: List[str] = []

    if not isinstance(ai_data, dict) or not ai_data:
        return ValidationResult(False, {}, ["Empty AI output."])

    if _clean_str(ai_data.get("intent")) != "edit_session":
        return ValidationResult(False, {}, ["Invalid intent for edit session."])

    session_id = ai_data.get("session_id")
    session_query = _clean_str(ai_data.get("session_query"))

    # session_id can come as str sometimes; normalize
    if session_id is not None:
        session_id = _as_int(session_id)
        if session_id is None or session_id < 1:
            errors.append("session_id must be a positive integer.")

    if session_id is None and not session_query:
        errors.append("Missing session target. Provide session_id or session_query.")
    print(ai_data)
    updates_in = ai_data.get("updates") or {}
    if not isinstance(updates_in, dict):
        errors.append("updates must be an object.")
        updates_in = {}

    # Normalize fields: only include what is present
    updates: Dict[str, Any] = {}

    title = _clean_str(updates_in.get("title"))
    if "title" in updates_in and updates_in.get("title") is not None:
        if not title:
            errors.append("title cannot be empty.")
        else:
            updates["title"] = title

    # Percent fields (AI uses vat; DB uses tax later)
    def _validate_pct(field_key: str, label: str):
        if field_key in updates_in and updates_in.get(field_key) is not None:
            val = _as_number(updates_in.get(field_key))
            if val is None:
                errors.append(f"{label} must be a number.")
            elif val < 0 or val > 100:
                errors.append(f"{label} must be between 0 and 100.")
            else:
                updates[field_key] = float(val)

    _validate_pct("vat", "VAT")
    _validate_pct("service", "service fee")
    _validate_pct("discount", "discount")

    if len(updates) == 0:
        errors.append("No changes found. Tell me what to update (title, VAT, service, discount).")

    if errors:
        return ValidationResult(False, {}, errors)

    normalized = {
        "intent": "edit_session",
        "session_id": session_id,        # may be None if using query
        "session_query": session_query or None,
        "updates": updates,
    }
    return ValidationResult(True, normalized, [])
