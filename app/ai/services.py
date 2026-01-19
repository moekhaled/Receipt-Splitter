from __future__ import annotations
from typing import Any, Dict, List
from django.db import transaction
from app.models import Session, Person, Item
from django.urls import reverse
from django.db.models import Q
from app.models import Session
import re
from typing import Optional




@transaction.atomic
def execute_create_session(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Executes intent=create_session using normalized/validated payload.

    Expected payload format (from validation.py):
    {
      "intent": "create_session",
      "session": {"title": str, "vat": float, "service": float, "discount": float},
      "people": [{"name": str, "items": [{"name": str, "price": float, "quantity": int}, ...]}, ...]
    }

    Returns:
    {
      "session_id": int,
      "redirect_url": str,
      "message": str
    }
    """
    session_data = payload["session"]
    people_data: List[Dict[str, Any]] = payload.get("people", [])

    # ✅ Create session
    session = Session.objects.create(
        title=session_data["title"],
        tax=session_data["vat"],
        service=session_data["service"],
        discount=session_data["discount"],
    )

    people_created = 0
    items_created = 0

    # ✅ Create people and items
    for p in people_data:
        person = Person.objects.create(
            name=p["name"],
            session=session,
        )
        people_created += 1

        for it in p.get("items", []):
            Item.objects.create(
                name=it["name"],
                price=it["price"],
                quantity=it["quantity"],
                person=person,
            )
            items_created += 1

    message = f"✅ Created session '{session.title}' with {people_created} people"
    if items_created:
        message += f" and {items_created} items."
    else:
        message += " (no items yet)."

    return {
        "session_id": session.pk,
        "redirect_url": reverse("session-details", kwargs={"pk": session.pk}),
        "message": message,
    }

STOP_WORDS = {
    "receipt", "session", "sessions", "the", "a", "an", "my", "in", "on", "called", "named"
}

def normalize_session_query(q: str) -> str:
    q = (q or "").strip()
    q = q.lower()

    # remove punctuation except spaces
    q = re.sub(r"[^a-z0-9\s]+", " ", q)

    # collapse whitespace
    q = re.sub(r"\s+", " ", q).strip()

    # remove common filler words
    parts = [p for p in q.split() if p not in STOP_WORDS]

    return " ".join(parts).strip()

def resolve_session(session_id=None, session_query=None):
    """
    Returns a Session object or raises ValueError with a user-facing message.
    For now:
      - If session_id provided => direct get
      - Else do a simple icontains match; if multiple => ask user to clarify
    """
    if session_id:
        try:
            return Session.objects.get(pk=session_id)
        except Session.DoesNotExist:
            raise ValueError("I couldn't find that session.")

    if session_query:
        session_query = normalize_session_query(session_query)
        qs = Session.objects.filter(title__icontains=session_query).order_by("-id")
        count = qs.count()
        if count == 0:
            raise ValueError(f"I couldn't find a session matching '{session_query}'.")
        if count > 1:
            # Keep it simple for now; later we can return options
            raise ValueError(f"Multiple sessions match '{session_query}'. Please open the session and try again.")
        return qs.first()

    raise ValueError("Please tell me which session (title) you mean.")


@transaction.atomic
def execute_edit_session(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    payload from validate_edit_session_payload:
    {
      "intent": "edit_session",
      "session_id": 12 or None,
      "session_query": "homes" or None,
      "updates": {"vat": 14, "service": 10, "discount": 0, "title": "..."}
    }
    """
    session = resolve_session(
        session_id=payload.get("session_id"),
        session_query=payload.get("session_query"),
    )

    updates = payload["updates"]
    changed = []

    if "title" in updates:
        session.title = updates["title"]
        changed.append(f"title='{session.title}'")

    # ✅ AI uses vat, DB uses tax
    if "vat" in updates:
        session.tax = updates["vat"]
        changed.append(f"tax={session.tax}%")

    if "service" in updates:
        session.service = updates["service"]
        changed.append(f"service={session.service}%")

    if "discount" in updates:
        session.discount = updates["discount"]
        changed.append(f"discount={session.discount}%")

    session.save()

    msg = "✅ Updated session: " + ", ".join(changed) if changed else "No changes applied."
    return {
        "session_id": session.pk,
        "redirect_url": reverse("session-details", kwargs={"pk": session.pk}),
        "message": msg,
    }

def execute_edit_person(data: Dict[str, Any]) -> Dict[str, Any]:
    session_id = data["session_id"]
    operation = data["operation"]

    # Ensure session exists
    session = Session.objects.filter(id=session_id).first()
    if not session:
        return {"ok": False, "message": "I couldn’t find that receipt/session."}

    if operation == "add":
        p = Person.objects.create(session=session, name=data["new_name"])
        return {
            "ok": True,
            "message": f"Added {p.name}.",
            "redirect_url": reverse("session-details", kwargs={"pk": session.id}),
            "created_person_id": p.id,
        }

    if operation == "rename":
        p = Person.objects.filter(id=data["person_id"], session=session).first()
        if not p:
            return {"ok": False, "message": "I couldn’t find that person in this session."}
        old = p.name
        p.name = data["new_name"]
        p.save(update_fields=["name"])
        return {
            "ok": True,
            "message": f"Renamed {old} → {p.name}.",
            "redirect_url": reverse("session-details", kwargs={"pk": session.id}),
        }

    if operation == "delete":
        p = Person.objects.filter(id=data["person_id"], session=session).first()
        if not p:
            return {"ok": False, "message": "I couldn’t find that person in this session."}
        name = p.name
        p.delete()
        return {
            "ok": True,
            "message": f"Deleted {name}.",
            "redirect_url": reverse("session-details", kwargs={"pk": session.id}),
        }

    return {"ok": False, "message": "Unsupported edit_person operation."}

def get_session(session_id: int) -> Optional[Session]:
    return Session.objects.filter(pk=session_id).first()

def get_person_in_session(session_id: int, person_id: int) -> Optional[Person]:
    return Person.objects.filter(pk=person_id, session_id=session_id).first()

def get_item_in_session(session_id: int, item_id: int) -> Optional[Item]:
    item = (
        Item.objects
        .select_related("person", "person__session")
        .filter(pk=item_id)
        .first()
    )
    if not item:
        return None
    return item if item.person.session_id == session_id else None

def execute_edit_item(payload: dict) -> dict:

    session_id = payload["session_id"]
    operation = payload["operation"]

    session = get_session(session_id)
    if not session:
        return {"ok": False, "message": "I couldn’t find that session."}

    if operation == "add":
        person = get_person_in_session(session_id, payload["to_person_id"])
        if not person:
            return {"ok": False, "message": "I couldn’t find that person in this session."}

        item = Item.objects.create(
            person=person,
            name=payload["name"],
            price=payload["price"],
            quantity=payload["quantity"],
        )
        return {
            "ok": True,
            "message": f"✅ Added {item.name} to {person.name}.",
            "redirect_url": reverse("session-details", kwargs={"pk": session.pk}),
        }

    if operation == "update":
        item = get_item_in_session(session_id, payload["item_id"])
        if not item:
            return {"ok": False, "message": "I couldn’t find that item in this session."}

        updates = payload["updates"]
        if "name" in updates: item.name = updates["name"]
        if "price" in updates: item.price = updates["price"]
        if "quantity" in updates: item.quantity = updates["quantity"]
        item.save()

        return {
            "ok": True,
            "message": "✅ Updated item.",
            "redirect_url": reverse("session-details", kwargs={"pk": session.pk}),
        }

    if operation == "delete":
        item = get_item_in_session(session_id, payload["item_id"])
        if not item:
            return {"ok": False, "message": "I couldn’t find that item in this session."}
        item.delete()
        return {
            "ok": True,
            "message": "✅ Deleted item.",
            "redirect_url": reverse("session-details", kwargs={"pk": session.pk}),
        }

    if operation == "move":
        item = get_item_in_session(session_id, payload["item_id"])
        if not item:
            return {"ok": False, "message": "I couldn’t find that item in this session."}

        new_owner = get_person_in_session(session_id, payload["to_person_id"])
        if not new_owner:
            return {"ok": False, "message": "I couldn’t find the target person in this session."}

        item.person = new_owner
        item.save(update_fields=["person"])
        return {
            "ok": True,
            "message": "✅ Moved item.",
            "redirect_url": reverse("session-details", kwargs={"pk": session.pk}),
        }

    return {"ok": False, "message": "Unsupported edit_item operation."}

def execute_edit_session_entities(payload: Dict[str, Any]) -> Dict[str, Any]:
    session_id = payload["session_id"]
    ops = payload["operations"]
    created_people = {}


    messages: List[str] = []

    # Stop on first failure (safest behavior)
    for idx, op in enumerate(ops, start=1):
        op_intent = op.get("intent")

        if op_intent == "edit_person":
            res = execute_edit_person(op)
            if res.get("ok") and op.get("operation") == "add" and op.get("ref"):
                created_people[op["ref"]] = res.get("created_person_id")
        elif op_intent == "edit_item":
            if op.get("to_person_ref") and not op.get("to_person_id"):
                ref = op["to_person_ref"]
                if ref not in created_people:
                    return {"ok": False, "message": f"❌ Failed at op #{idx}: unknown to_person_ref '{ref}'."}
                op = {**op, "to_person_id": created_people[ref]}
            res = execute_edit_item(op)
        else:
            return {"ok": False, "message": f"Unsupported operation intent at #{idx}."}

        if not res.get("ok"):
            prefix = "\n".join(messages).strip()
            msg = (prefix + "\n" if prefix else "") + f"❌ Failed at op #{idx}: {res.get('message')}"
            return {"ok": False, "message": msg}

        messages.append(res.get("message", f"✅ Operation #{idx} done."))

    return {
        "ok": True,
        "message": "\n".join(messages),
        "redirect_url": reverse("session-details", kwargs={"pk": session_id}),
    }
