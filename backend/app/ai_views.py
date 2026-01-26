import json
import os

import requests
from requests import RequestException

from django.conf import settings
from django.http import JsonResponse
from django.template.loader import render_to_string
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_GET, require_POST

from .ai.llm import parse_receipt_prompt

BACKEND_URL = os.getenv("BACKEND_URL", "http://backend:8000")

# =========================================================
# AI Assistant (AI calls backend for context + execute)
# =========================================================
CHAT_KEY = "ai_chat_history"
MAX_TURNS = 30
MAX_CHARS = 2000

# =========================================================
# CSRF helper for AI widget
# =========================================================
@require_GET
@ensure_csrf_cookie
def ai_csrf(request):
    return JsonResponse({"ok": True})

def get_history(request):
    return request.session.get(CHAT_KEY, [])


def save_history(request, history):
    request.session[CHAT_KEY] = history[-MAX_TURNS:]
    request.session.modified = True


def add_turn(request, role, content):
    content = (content or "").strip()
    if not content:
        return
    history = get_history(request)
    history.append({"role": role, "content": content[:MAX_CHARS]})
    save_history(request, history)


def render_history_html(request):
    return render_to_string(
        "app/_ai_messages.html",
        {"history": get_history(request)},
        request=request,
    )


def reply(request, message, *, status=200, action="none", redirect_url=None):
    add_turn(request, "assistant", message)
    payload = {"response": message, "action": action, "html": render_history_html(request)}
    if redirect_url:
        payload["redirect_url"] = redirect_url
    return JsonResponse(payload, status=status)


def backend_ai_execute(intent: str, ai_data: dict):
    try:
        r = requests.post(
            f"{BACKEND_URL}/api/ai/execute/",
            json={"intent": intent, "ai_data": ai_data},
            timeout=20,
        )
        try:
            payload = r.json() if r.content else {}
        except ValueError:
            payload = {"message": (r.text or "")[:500] or "Backend returned non-JSON response."}

    except requests.RequestException as e:
        return False, {"message": f"Backend call failed: {type(e).__name__}: {e}"}, 502

    if not r.ok:
        msg = payload.get("message")
        if not msg and payload.get("errors"):
            msg = " | ".join(payload["errors"])
        return False, {"message": msg or "Backend rejected the request."}, r.status_code

    if "ok" not in payload:
        payload["ok"] = True

    return bool(payload.get("ok")), payload, r.status_code


@require_POST
def ai_parse(request):
    try:
        try:
            data = json.loads(request.body.decode("utf-8"))
        except json.JSONDecodeError:
            return JsonResponse(
                {"response": "Invalid JSON payload.", "action": "none", "html": render_history_html(request)},
                status=400,
            )

        prompt = (data.get("prompt") or "").strip()
        if not prompt:
            return JsonResponse(
                {"response": "Please type something.", "action": "none", "html": render_history_html(request)},
                status=400,
            )

        add_turn(request, "user", prompt)

        ctx = data.get("context") or {}
        session_id = ctx.get("session_id")

        # fetch context from backend
        context = {}
        if session_id:
            try:
                r = requests.get(f"{BACKEND_URL}/api/sessions/{session_id}/context/", timeout=10)
                context = r.json() if r.ok else {}
            except requests.RequestException:
                context = {}

        try:
            ai_data = parse_receipt_prompt(prompt, history=get_history(request), context=context)
        except Exception as e:
            return reply(request, "⚠️ The AI model is busy right now. Please try again in a moment.", status=400)

        if not ai_data:
            return reply(
                request,
                "I couldn’t understand that. Try asking a question or describing a receipt.",
                status=400,
            )

        intent = (ai_data.get("intent") or "").strip()

        # session_id fallback for edit intents
        if intent in {"edit_session", "edit_person", "edit_item", "edit_session_entities"} and not ai_data.get("session_id") and session_id:
            ai_data["session_id"] = session_id

        if intent == "general_inquiry":
            response_text = ai_data.get("answer", "Sure — what would you like to know?")
            return reply(request, response_text, action="none")

        if intent in {"create_session", "edit_session", "edit_person", "edit_item", "edit_session_entities"}:
            ok, exec_result, _http_status = backend_ai_execute(intent, ai_data)
            if not ok:
                return reply(request, "❌ " + (exec_result.get("message") or "Execution failed."), status=400)

            redirect_url = exec_result.get("redirect_url")
            return reply(
                request,
                exec_result.get("message", "✅ Done."),
                action="redirect" if redirect_url else "none",
                redirect_url=redirect_url,
            )

        return reply(
            request,
            "I wasn’t sure what you meant. Ask me what I can do, or tell me to create a receipt.",
            status=400,
        )

    except Exception as e:
        msg = f"{type(e).__name__}: {e}" if settings.DEBUG else "Error processing your request."
        return JsonResponse(
            {"response": msg, "action": "none", "html": render_history_html(request)},
            status=400,
        )
