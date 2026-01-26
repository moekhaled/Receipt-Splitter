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

def validate_edit_person_payload(payload: Dict[str, Any]) -> ValidationResult:
    errors: List[str] = []

    session_id = payload.get("session_id")
    operation = payload.get("operation")
    person_id = payload.get("person_id")
    new_name = (payload.get("new_name") or "").strip()

    # ✅ NEW: optional temp ref (only meaningful for add)
    ref = payload.get("ref")
    ref = (ref or "").strip() if isinstance(ref, str) else None
    if ref == "":
        ref = None

    if not isinstance(session_id, int) or session_id <= 0:
        errors.append("Missing or invalid session_id.")

    if operation not in {"add", "rename", "delete"}:
        errors.append("Invalid operation for edit_person.")

    if operation in {"rename", "delete"}:
        if not isinstance(person_id, int) or person_id <= 0:
            errors.append("person_id is required for rename/delete.")

    if operation in {"add", "rename"}:
        if not new_name:
            errors.append("new_name is required for add/rename.")

    # ✅ NEW: allow ref only for add (ignore it otherwise)
    if operation != "add":
        ref = None

    if errors:
        return ValidationResult(False, {}, errors)

    normalized = {
        "intent": "edit_person",
        "session_id": session_id,
        "operation": operation,
        "person_id": person_id if operation in {"rename", "delete"} else None,
        "new_name": new_name if operation in {"add", "rename"} else None,
        "ref": ref,  # ✅ NEW
    }
    return ValidationResult(True, normalized, [])

def validate_edit_item_payload(ai_data: Dict[str, Any]) -> ValidationResult:
    """
    Normalizes/validates intent=edit_item.
    Supports operations: add/update/delete/move
    """
    errors: List[str] = []

    if not isinstance(ai_data, dict) or not ai_data:
        return ValidationResult(False, {}, ["Empty AI output."])

    if _clean_str(ai_data.get("intent")) != "edit_item":
        return ValidationResult(False, {}, ["Invalid intent for edit item."])

    session_id = _as_int(ai_data.get("session_id"))
    if not session_id or session_id <= 0:
        errors.append("Missing session_id (open the session page and try again).")

    operation = _clean_str(ai_data.get("operation"))
    if operation not in {"add", "update", "delete", "move"}:
        errors.append("Invalid operation for editing items.")

    item_id = _as_int(ai_data.get("item_id"))
    to_person_id = _as_int(ai_data.get("to_person_id"))

    to_person_ref = ai_data.get("to_person_ref")
    to_person_ref = (to_person_ref or "").strip() if isinstance(to_person_ref, str) else None

    if to_person_ref == "":
        to_person_ref = None

    # Required fields per operation
    if operation in {"update", "delete", "move"}:
        if not item_id or item_id <= 0:
            errors.append("item_id is required for update/delete/move.")

    if operation in {"add", "move"}:
        valid_id = isinstance(to_person_id, int) and to_person_id > 0
        valid_ref = isinstance(to_person_ref, str) and len(to_person_ref) > 0
        if not valid_id and not valid_ref:
            errors.append("to_person_id or to_person_ref is required for add/move.")


    normalized: Dict[str, Any] = {
        "intent": "edit_item",
        "session_id": session_id,
        "operation": operation,
    }

    # add
    if operation == "add":
        name = _clean_str(ai_data.get("name"))
        price = _as_number(ai_data.get("price"))
        quantity = _as_int(ai_data.get("quantity"))
        if quantity is None:
            quantity = 1

        if not name:
            errors.append("Item name is required for add.")
        if price is None or price <= 0:
            errors.append("Item price must be a number greater than 0.")
        if not isinstance(quantity, int) or quantity < 1:
            errors.append("Item quantity must be an integer >= 1.")

        normalized.update({
            "to_person_id": to_person_id,
            "to_person_ref": to_person_ref,
            "name": name,
            "price": float(price) if price is not None else None,
            "quantity": quantity,
        })

    # update
    if operation == "update":
        updates_in = ai_data.get("updates") or {}
        if not isinstance(updates_in, dict):
            errors.append("updates must be an object.")
            updates_in = {}

        updates: Dict[str, Any] = {}
        if "name" in updates_in:
            nm = _clean_str(updates_in.get("name"))
            if not nm:
                errors.append("Updated name cannot be empty.")
            else:
                updates["name"] = nm

        if "price" in updates_in:
            pr = _as_number(updates_in.get("price"))
            if pr is None or pr <= 0:
                errors.append("Updated price must be > 0.")
            else:
                updates["price"] = float(pr)

        if "quantity" in updates_in:
            qt = _as_int(updates_in.get("quantity"))
            if qt is None or qt < 1:
                errors.append("Updated quantity must be an integer >= 1.")
            else:
                updates["quantity"] = qt

        if not updates:
            errors.append("updates must include at least one of: name, price, quantity.")

        normalized.update({
            "item_id": item_id,
            "updates": updates,
        })

    # delete
    if operation == "delete":
        normalized.update({
            "item_id": item_id,
        })

    # move
    if operation == "move":
        normalized.update({
            "item_id": item_id,
            "to_person_id": to_person_id,
            "to_person_ref": to_person_ref,

        })

    if errors:
        return ValidationResult(False, {}, errors)

    return ValidationResult(True, normalized, [])


def validate_edit_session_entities_payload(ai_data: Dict[str, Any]) -> ValidationResult:
    errors: List[str] = []

    if not isinstance(ai_data, dict) or not ai_data:
        return ValidationResult(False, {}, ["Empty AI output."])

    if _clean_str(ai_data.get("intent")) != "edit_session_entities":
        return ValidationResult(False, {}, ["Invalid intent for edit_session_entities."])

    session_id = _as_int(ai_data.get("session_id"))
    if not session_id or session_id <= 0:
        errors.append("Missing session_id (open the session page and try again).")

    ops_in = ai_data.get("operations")
    if not isinstance(ops_in, list) or not ops_in:
        errors.append("operations must be a non-empty list.")

    if errors:
        return ValidationResult(False, {}, errors)

    if len(ops_in) > 15:
        return ValidationResult(False, {}, ["Too many operations in one request (max 15)."])

    normalized_ops: List[Dict[str, Any]] = []

    for idx, op in enumerate(ops_in, start=1):
        if not isinstance(op, dict):
            errors.append(f"Operation #{idx} is not a valid object.")
            continue

        op_intent = _clean_str(op.get("intent"))
        if op_intent not in {"edit_person", "edit_item"}:
            errors.append(f"Operation #{idx}: intent must be edit_person or edit_item.")
            continue

        # Inject session_id if missing inside the op
        if not op.get("session_id"):
            op = {**op, "session_id": session_id}

        if op_intent == "edit_person":
            r = validate_edit_person_payload(op)
            if not r.ok:
                errors.append(f"Operation #{idx} (edit_person): " + " | ".join(r.errors))
                continue
            normalized_ops.append(r.data)

        elif op_intent == "edit_item":
            r = validate_edit_item_payload(op)
            if not r.ok:
                errors.append(f"Operation #{idx} (edit_item): " + " | ".join(r.errors))
                continue
            normalized_ops.append(r.data)

    if errors:
        return ValidationResult(False, {}, errors)

    return ValidationResult(
        True,
        {"intent": "edit_session_entities", "session_id": session_id, "operations": normalized_ops},
        [],
    )
