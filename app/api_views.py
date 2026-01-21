import json
from decimal import Decimal, InvalidOperation

from django.http import JsonResponse
from django.views.decorators.http import require_GET, require_POST
from django.views.decorators.csrf import csrf_exempt

from .models import Session, Person, Item

from .ai.validation import (
    validate_create_session_payload,
    validate_edit_session_payload,
    validate_edit_person_payload,
    validate_edit_item_payload,
    validate_edit_session_entities_payload,
)
from .ai.services import (
    execute_create_session,
    execute_edit_session,
    execute_edit_person,
    execute_edit_item,
    execute_edit_session_entities,
)


# ---------------------------
# Helpers
# ---------------------------
def parse_json_body(request):
    try:
        return True, json.loads(request.body.decode("utf-8") or "{}")
    except json.JSONDecodeError:
        return False, None


def bad_json():
    return JsonResponse({"ok": False, "message": "Invalid JSON payload."}, status=400)


def to_decimal(val, default=Decimal("0")):
    if val is None or val == "":
        return default
    try:
        return Decimal(str(val))
    except (InvalidOperation, ValueError, TypeError):
        return default


def to_int(val, default=1):
    try:
        return int(val)
    except (ValueError, TypeError):
        return default


def ok(payload=None):
    payload = payload or {}
    payload.setdefault("ok", True)
    return JsonResponse(payload)


def fail(message, status=400, errors=None):
    payload = {"ok": False, "message": message}
    if errors:
        payload["errors"] = errors
    return JsonResponse(payload, status=status)


# ---------------------------
# Health / context
# ---------------------------
@require_GET
def health(request):
    return ok({"service": "backend"})


@require_GET
def session_context(request, session_id: int):
    session = Session.objects.filter(pk=session_id).first()
    if not session:
        return ok({"session_id": session_id, "people": []})

    people = (
        Person.objects.filter(session_id=session_id)
        .prefetch_related("items")
        .order_by("id")
    )

    return ok({
        "session_id": session_id,
        "people": [
            {
                "id": p.id,
                "name": p.name,
                "items": [
                    {"id": it.id, "name": it.name, "price": float(it.price), "quantity": it.quantity}
                    for it in p.items.all().order_by("id")
                ],
            }
            for p in people
        ],
    })


# ---------------------------
# AI execute (Backend is the only writer)
# ---------------------------
@csrf_exempt
@require_POST
def ai_execute(request):
    ok_json, data = parse_json_body(request)
    if not ok_json:
        return bad_json()

    intent = (data.get("intent") or "").strip()
    ai_data = data.get("ai_data") or {}

    if intent == "create_session":
        vr = validate_create_session_payload(ai_data)
        if not vr.ok:
            return fail("Validation failed.", errors=vr.errors, status=400)
        result = execute_create_session(vr.data)
        # normalize response
        result.setdefault("ok", True)
        result.setdefault("message", "✅ Session created.")
        return ok(result)

    if intent == "edit_session":
        vr = validate_edit_session_payload(ai_data)
        if not vr.ok:
            return fail("Validation failed.", errors=vr.errors, status=400)
        result = execute_edit_session(vr.data)
        result.setdefault("ok", True)
        result.setdefault("message", "✅ Session updated.")
        return ok(result)

    if intent == "edit_person":
        vr = validate_edit_person_payload(ai_data)
        if not vr.ok:
            return fail("Validation failed.", errors=vr.errors, status=400)
        result = execute_edit_person(vr.data)
        # execute_edit_person already tends to return ok/message/redirect_url but normalize anyway
        result.setdefault("ok", True)
        result.setdefault("message", "✅ Person updated.")
        return ok(result)

    if intent == "edit_item":
        vr = validate_edit_item_payload(ai_data)
        if not vr.ok:
            return fail("Validation failed.", errors=vr.errors, status=400)
        result = execute_edit_item(vr.data)
        result.setdefault("ok", True)
        result.setdefault("message", "✅ Item updated.")
        return ok(result)

    if intent == "edit_session_entities":
        vr = validate_edit_session_entities_payload(ai_data)
        if not vr.ok:
            return fail("Validation failed.", errors=vr.errors, status=400)
        result = execute_edit_session_entities(vr.data)
        result.setdefault("ok", True)
        result.setdefault("message", "✅ Changes applied.")
        return ok(result)

    return fail("Unknown intent.", status=400, errors=["Unknown intent."])


# ---------------------------
# UI endpoints (Frontend writes through Backend)
# ---------------------------
@csrf_exempt
@require_POST
def ui_create_session(request):
    ok_json, data = parse_json_body(request)
    if not ok_json:
        return bad_json()

    s = Session.objects.create(
        title=data.get("title") or "",
        tax=to_decimal(data.get("tax"), Decimal("0")),
        service=to_decimal(data.get("service"), Decimal("0")),
        discount=to_decimal(data.get("discount"), Decimal("0")),
    )
    return ok({"session_id": s.id, "message": "✅ Session created."})


@csrf_exempt
@require_POST
def ui_update_session(request, session_id: int):
    ok_json, data = parse_json_body(request)
    if not ok_json:
        return bad_json()

    s = Session.objects.filter(pk=session_id).first()
    if not s:
        return fail("Session not found.", status=404)

    if "title" in data:
        s.title = data["title"] or s.title
    if "tax" in data:
        s.tax = to_decimal(data.get("tax"), s.tax)
    if "service" in data:
        s.service = to_decimal(data.get("service"), s.service)
    if "discount" in data:
        s.discount = to_decimal(data.get("discount"), s.discount)

    s.save()
    return ok({"message": "✅ Session updated."})


@csrf_exempt
@require_POST
def ui_delete_session(request, session_id: int):
    deleted, _ = Session.objects.filter(pk=session_id).delete()
    if not deleted:
        return fail("Session not found.", status=404)
    return ok({"message": "✅ Session deleted."})


@csrf_exempt
@require_POST
def ui_add_person(request, session_id: int):
    ok_json, data = parse_json_body(request)
    if not ok_json:
        return bad_json()

    if not Session.objects.filter(pk=session_id).exists():
        return fail("Session not found.", status=404)

    p = Person.objects.create(session_id=session_id, name=data.get("name") or "")
    return ok({"person_id": p.id, "message": "✅ Person added."})


@csrf_exempt
@require_POST
def ui_rename_person(request, person_id: int):
    ok_json, data = parse_json_body(request)
    if not ok_json:
        return bad_json()

    p = Person.objects.filter(pk=person_id).first()
    if not p:
        return fail("Person not found.", status=404)

    p.name = data.get("name") or p.name
    p.save(update_fields=["name"])
    return ok({"message": "✅ Person renamed."})


@csrf_exempt
@require_POST
def ui_delete_person(request, person_id: int):
    deleted, _ = Person.objects.filter(pk=person_id).delete()
    if not deleted:
        return fail("Person not found.", status=404)
    return ok({"message": "✅ Person deleted."})


@csrf_exempt
@require_POST
def ui_add_item(request, person_id: int):
    ok_json, data = parse_json_body(request)
    if not ok_json:
        return bad_json()

    p = Person.objects.filter(pk=person_id).first()
    if not p:
        return fail("Person not found.", status=404)

    it = Item.objects.create(
        person_id=person_id,
        name=data.get("name") or "",
        price=to_decimal(data.get("price"), Decimal("0")),
        quantity=to_int(data.get("quantity"), 1),
    )
    return ok({"item_id": it.id, "message": "✅ Item added."})


@csrf_exempt
@require_POST
def ui_update_item(request, item_id: int):
    ok_json, data = parse_json_body(request)
    if not ok_json:
        return bad_json()

    it = Item.objects.filter(pk=item_id).first()
    if not it:
        return fail("Item not found.", status=404)

    if "name" in data:
        it.name = data.get("name") or it.name
    if "price" in data:
        it.price = to_decimal(data.get("price"), it.price)
    if "quantity" in data:
        it.quantity = to_int(data.get("quantity"), it.quantity)

    it.save()
    return ok({"message": "✅ Item updated."})


@csrf_exempt
@require_POST
def ui_delete_item(request, item_id: int):
    deleted, _ = Item.objects.filter(pk=item_id).delete()
    if not deleted:
        return fail("Item not found.", status=404)
    return ok({"message": "✅ Item deleted."})
