from django.shortcuts import render
import json
import os

import requests
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt, ensure_csrf_cookie
from django.views.decorators.http import require_GET, require_POST
from jsonschema.exceptions import ValidationError

from receipt_splitter_contracts.schemas import validate_ai_envelope

from ai_core.llm import parse_receipt_prompt


BACKEND_BASE_URL = os.getenv("BACKEND_BASE_URL", "http://127.0.0.1:8000")
BACKEND_EXECUTE_PATH = os.getenv("BACKEND_AI_EXECUTE_PATH", "/api/ai/execute/")


@require_GET
def health(request):
    return JsonResponse({"ok": True, "service": "ai"})

@require_GET
@ensure_csrf_cookie
def csrf(request):
    return JsonResponse({"ok": True})


def _bad_json():
    return JsonResponse({"ok": False, "message": "Invalid JSON payload."}, status=400)


@csrf_exempt
@require_POST
def forward_execute(request):
    try:
        payload = json.loads((request.body or b"{}").decode("utf-8"))
    except json.JSONDecodeError:
        return _bad_json()

    # Validate the shared envelope contract here (AI service gate)
    try:
        validate_ai_envelope(payload)
    except ValidationError as e:
        msg = e.message if hasattr(e, "message") else str(e)
        return JsonResponse({"ok": False, "message": "Validation failed.", "errors": [msg]}, status=400)

    url = BACKEND_BASE_URL.rstrip("/") + BACKEND_EXECUTE_PATH
    try:
        r = requests.post(url, json=payload, timeout=30)
    except requests.RequestException as e:
        return JsonResponse({"ok": False, "message": "Backend unreachable.", "errors": [str(e)]}, status=502)

    try:
        return JsonResponse(r.json(), status=r.status_code)
    except ValueError:
        return JsonResponse({"ok": False, "message": "Backend returned non-JSON.", "body": r.text}, status=502)

@csrf_exempt
@require_POST
def parse_and_execute(request):
    try:
        body = json.loads((request.body or b"{}").decode("utf-8"))
    except json.JSONDecodeError:
        return _bad_json()

    message = (body.get("message") or "").strip()
    session_id = body.get("session_id")
    history = body.get("history")  # optional list of {role, content}

    if not message:
        return JsonResponse({"ok": False, "message": "Missing 'message'."}, status=400)

    # Fetch context if session_id is provided
    context = None
    if session_id:
        try:
            ctx_url = BACKEND_BASE_URL.rstrip("/") + f"/api/sessions/{int(session_id)}/context/"
            ctx_resp = requests.get(ctx_url, timeout=15)
            if ctx_resp.ok:
                context = ctx_resp.json()
        except Exception:
            context = None  # context is helpful, but not required

    try:
        parsed = parse_receipt_prompt(message, history=history, context=context)
    except:
        return JsonResponse(
                {"ok": False, "message": "AI is temporarily unavailable. Please try again."},
                status=503,
                )

    if not parsed or "intent" not in parsed:
        return JsonResponse(
            {"ok": False, "message": "AI could not produce a valid action."},
            status=400,
        )

    intent = (parsed.get("intent") or "").strip()
    ai_data = dict(parsed)
    ai_data.pop("intent", None)

    envelope = {"intent": intent, "ai_data": ai_data}

    # Validate against shared contract
    try:
        validate_ai_envelope(envelope)
    except ValidationError as e:
        msg = e.message if hasattr(e, "message") else str(e)
        return JsonResponse({"ok": False, "message": "Validation failed.", "errors": [msg]}, status=400)
    
        # ✅ Do NOT forward general inquiries to backend writer
    if intent == "general_inquiry":
        answer = ai_data.get("answer") or "Sure — what would you like to know?"
        return JsonResponse({"ok": True, "message": answer}, status=200)


    # Forward to backend writer
    url = BACKEND_BASE_URL.rstrip("/") + BACKEND_EXECUTE_PATH
    try:
        r = requests.post(url, json=envelope, timeout=30)
    except requests.RequestException as e:
        return JsonResponse({"ok": False, "message": "Backend unreachable.", "errors": [str(e)]}, status=502)

    try:
        return JsonResponse(r.json(), status=r.status_code)
    except ValueError:
        return JsonResponse({"ok": False, "message": "Backend returned non-JSON.", "body": r.text}, status=502)
