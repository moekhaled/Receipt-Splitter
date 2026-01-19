from __future__ import annotations
from typing import Any, Dict, List
from django.db import transaction
from app.models import Session, Person, Item
from django.urls import reverse
from django.db.models import Q
from app.models import Session
import re



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
