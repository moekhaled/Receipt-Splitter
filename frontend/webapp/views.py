import os
from typing import Any, Dict, List, Optional, Tuple

import requests
from requests import RequestException

from django import forms
from django.http import Http404, HttpRequest, HttpResponse, HttpResponseRedirect,JsonResponse
from django.shortcuts import render
from django.urls import reverse, reverse_lazy
from django.views import View
from django.views.generic import RedirectView
import json
from django.views.decorators.http import require_POST
# Internal docker-network URL for backend (SSR frontend calls backend server-side)
BACKEND_URL = os.getenv("BACKEND_URL", "http://backend:8000")



# =========================================================
# Backend HTTP helpers (shared, module-level)
# =========================================================
def _extract_error_message(payload: dict, default: str = "Request failed.") -> str:
    msg = payload.get("message")
    if msg:
        return msg
    errs = payload.get("errors")
    if isinstance(errs, list) and errs:
        return " | ".join(str(e) for e in errs)
    return default


def backend_get(path: str, *, timeout: int = 10) -> Tuple[bool, dict, int, Optional[str]]:
    """
    Returns (ok: bool, payload: dict, status_code: int, message: str|None)
    """
    try:
        r = requests.get(f"{BACKEND_URL}{path}", timeout=timeout)
        try:
            payload = r.json() if r.content else {}
        except ValueError:
            payload = {"message": (r.text or "")[:500] or "Backend returned non-JSON response."}

        if not r.ok:
            return False, payload, r.status_code, _extract_error_message(payload)
        return True, payload, r.status_code, None

    except RequestException as e:
        return False, {"message": str(e)}, 502, f"Backend unreachable: {type(e).__name__}: {e}"


def backend_post(path: str, *, payload: dict, timeout: int = 15) -> Tuple[bool, dict, int, Optional[str]]:
    """
    Returns (ok: bool, payload: dict, status_code: int, message: str|None)
    """
    try:
        r = requests.post(f"{BACKEND_URL}{path}", json=payload, timeout=timeout)
        try:
            data = r.json() if r.content else {}
        except ValueError:
            data = {"message": (r.text or "")[:500] or "Backend returned non-JSON response."}

        if not r.ok:
            return False, data, r.status_code, _extract_error_message(data)
        return True, data, r.status_code, None

    except RequestException as e:
        return False, {"message": str(e)}, 502, f"Backend unreachable: {type(e).__name__}: {e}"


# =========================================================
# Context normalization helpers (shared, module-level)
# =========================================================
def _money(x: Any) -> float:
    try:
        if x is None:
            return 0.0
        return float(x)
    except Exception:
        return 0.0


def _int(x: Any) -> Optional[int]:
    try:
        return int(x)
    except Exception:
        return None


def _calc_item_total(item: dict) -> float:
    price = _money(item.get("price"))
    qty = item.get("quantity", 1)
    try:
        qty = int(qty)
    except Exception:
        qty = 1
    return price * max(qty, 0)


def _calc_person_total(person: dict) -> float:
    return person.get("taxed_total",0)


def _calc_grand_total(people: List[dict]) -> float:
    return sum(p.get("taxed_total",0) for p in people if isinstance(p, dict))


def get_session_context(session_id: int) -> Tuple[bool, dict, Optional[str]]:
    """
    Fetches session context from backend and attaches convenience fields:
      - _people_list
      - _grand_total
    Returns (ok, context_dict, error_message)
    """
    ok, data, _status, msg = backend_get(f"/api/sessions/{session_id}/context/")
    if not ok:
        return False, {}, msg
    tax , service , discount = data.get("session").get("tax"),data.get("session").get("service"),data.get("session").get("discount")
    people = data.get("people")
    if not isinstance(people, list):
        people = []
    
    for p in people:
        if not isinstance(p, dict):
            continue
        p_items = p.get("items") or []
        if not isinstance(p_items, list):
            p_items = []
            p["items"] = p_items

        person_total = 0.0
        for it in p_items:
            if not isinstance(it, dict):
                continue
            qty = it.get("quantity", 1)
            try:
                qty = int(qty)
            except Exception:
                qty = 1
            price = float(it.get("price") or 0)
            item_total = max(qty, 0) * price
            it["total"] = item_total
            person_total += item_total

        p["total"] = round(person_total,2)
        p["taxed_total"] = round(person_total * (1 + (float(tax))/100 ) * (1 + (float(service))/100 ) * (1 - (float(discount))/100 ),2) 


    data["_people_list"] = people
    data["_grand_total"] = round(data.get("grand_total", _calc_grand_total(people)),2)
    return True, data, None


def find_person_in_context(ctx: dict, person_id: int) -> Optional[dict]:
    people = ctx.get("_people_list") or ctx.get("people") or []
    for p in people:
        if isinstance(p, dict) and _int(p.get("id")) == person_id:
            return p
    return None


def find_item_in_context(ctx: dict, item_id: int) -> Tuple[Optional[dict], Optional[dict]]:
    """
    Returns (item_dict, owning_person_dict)
    """
    people = ctx.get("_people_list") or ctx.get("people") or []
    for p in people:
        if not isinstance(p, dict):
            continue
        items = p.get("items") or []
        if not isinstance(items, list):
            continue
        for it in items:
            if isinstance(it, dict) and _int(it.get("id")) == item_id:
                return it, p
    return None, None

# =========================================================
# AI message history helper functions
# =========================================================
AI_HISTORY_KEY = "ai_chat_history"
AI_HISTORY_MAX = 24
AI_ALLOWED_ROLES = {"user", "assistant"}


def ai_history_get(request):
    """
    Fast read. No validation here (by design).
    Returns a list (possibly empty).
    """
    hist = request.session.get(AI_HISTORY_KEY)
    return hist if isinstance(hist, list) else []


def ai_history_append(request, role: str, content: str):
    """
    Single validation point: normalize + validate exactly once when appending.
    """
    role = (role or "").strip()
    content = (content or "").strip()

    if role not in AI_ALLOWED_ROLES:
        return False
    if not content or content == "🤖 Thinking...":
        return False

    hist = request.session.get(AI_HISTORY_KEY)
    if not isinstance(hist, list):
        hist = []

    hist.append({"role": role, "content": content})

    # cap length
    if len(hist) > AI_HISTORY_MAX:
        hist = hist[-AI_HISTORY_MAX :]

    request.session[AI_HISTORY_KEY] = hist
    request.session.modified = True
    return True
@require_POST
def ai_history_append_view(request: HttpRequest) -> JsonResponse:
    """
    Body: {"role": "user"|"assistant", "content": "..."}
    Appends one message to the Django session history (validated once here).
    """
    try:
        body = json.loads((request.body or b"{}").decode("utf-8"))
    except Exception:
        return JsonResponse({"ok": False, "message": "Bad JSON"}, status=400)

    role = body.get("role")
    content = body.get("content")

    ok = ai_history_append(request, role=role, content=content)
    if not ok:
        return JsonResponse({"ok": False, "message": "Invalid role/content"}, status=400)

    return JsonResponse({"ok": True, "history": ai_history_get(request)})
# =========================================================
# Forms (no ModelForms, no ORM)
# =========================================================
class SessionForm(forms.Form):
    title = forms.CharField(required=False)
    tax = forms.FloatField(required=False, initial=0)
    service = forms.FloatField(required=False, initial=0)
    discount = forms.FloatField(required=False, initial=0)


class PersonForm(forms.Form):
    name = forms.CharField(required=True)


class ItemForm(forms.Form):
    name = forms.CharField(required=True)
    price = forms.FloatField(required=True)
    quantity = forms.IntegerField(required=False, initial=1)


# =========================================================
# READ pages (SSR) — use backend HTTP
# =========================================================
class HomeView(RedirectView):
    url = reverse_lazy("all-sessions")


class SessionsView(View):
    template_name = "webapp/all_sessions.html"

    def get(self, request: HttpRequest) -> HttpResponse:
        ok, data, _status, msg = backend_get("/api/sessions/")
        if not ok:
            return render(request, self.template_name, {"sessions": [], "error": msg,"ai_chat_history": ai_history_get(request),})
        return render(request, self.template_name, {"sessions": data.get("sessions", []),"ai_chat_history": ai_history_get(request)})


class SessionDetailView(View):
    template_name = "webapp/single_session.html"

    def get(self, request: HttpRequest, session_pk: int) -> HttpResponse:
        ok, ctx, msg = get_session_context(session_pk)
        if not ok:
            return render(request, self.template_name, {"error": msg, "session_id": session_pk, "people": [],"ai_chat_history": ai_history_get(request),})

        session_dict = ctx.get("session") or {"id": session_pk, "title": ctx.get("title", "")}
        session_dict["id"] = session_dict.get("id", session_pk)

        return render(
            request,
            self.template_name,
            {
                "session": session_dict,
                "people": ctx.get("_people_list", []),
                "persons": ctx.get("_people_list", []),  # backward-compat with older templates
                "grand_total": ctx.get("_grand_total", 0.0),
                "ai_chat_history": ai_history_get(request),
            },
        )


class SessionDetailDetailedView(View):
    template_name = "webapp/single_session_detailed.html"

    def get(self, request: HttpRequest, session_pk: int) -> HttpResponse:
        ok, ctx, msg = get_session_context(session_pk)
        if not ok:
            return render(request, self.template_name, {"error": msg, "session_id": session_pk, "persons": [],"ai_chat_history": ai_history_get(request),})

        session_dict = ctx.get("session") or {"id": session_pk, "title": ctx.get("title", "")}
        session_dict["id"] = session_dict.get("id", session_pk)

        return render(
            request,
            self.template_name,
            {
                "session": session_dict,
                "persons": ctx.get("_people_list", []),
                "grand_total": ctx.get("_grand_total", 0.0),
                "ai_chat_history": ai_history_get(request),
            },
        )


class PersonsView(View):
    template_name = "webapp/all_persons.html"

    def get(self, request: HttpRequest, session_pk: int) -> HttpResponse:
        ok, ctx, msg = get_session_context(session_pk)
        if not ok:
            return render(
                request,
                self.template_name,
                {"persons": [], "error": msg, "session": {"id": session_pk},
                 "ai_chat_history": ai_history_get(request),
                },
                
            )

        session_dict = ctx.get("session") or {"id": session_pk}
        session_dict["id"] = session_dict.get("id", session_pk)

        return render(
            request,
            self.template_name,
            {
                "session": session_dict,
                "persons": ctx.get("_people_list", []),
                "grand_total": ctx.get("_grand_total", 0.0),
                "ai_chat_history": ai_history_get(request),
            },
        )


class PersonDetailsView(View):
    template_name = "webapp/single_person.html"

    def get(self, request: HttpRequest, session_pk: int, person_pk: int) -> HttpResponse:
        ok, ctx, msg = get_session_context(session_pk)
        if not ok:
            return render(request, self.template_name, {"error": msg, "person": None, "session": {"id": session_pk},"ai_chat_history": ai_history_get(request),})

        person = find_person_in_context(ctx, person_pk)
        if not person:
            raise Http404("Person not found")

        session_dict = ctx.get("session") or {"id": session_pk}
        session_dict["id"] = session_dict.get("id", session_pk)

        return render(request, self.template_name, {"person": person, "session": session_dict,"ai_chat_history": ai_history_get(request),})


# =========================================================
# WRITE actions — delegate to backend UI endpoints
# =========================================================
class AddSessionView(View):
    template_name = "webapp/add_session.html"

    def get(self, request: HttpRequest) -> HttpResponse:
        return render(request, self.template_name, {"form": SessionForm(),"ai_chat_history": ai_history_get(request),})

    def post(self, request: HttpRequest) -> HttpResponse:
        form = SessionForm(request.POST)
        if not form.is_valid():
            return render(request, self.template_name, {"form": form,"ai_chat_history": ai_history_get(request),})

        payload = {
            "title": form.cleaned_data.get("title") or "",
            "tax": form.cleaned_data.get("tax") or 0,
            "service": form.cleaned_data.get("service") or 0,
            "discount": form.cleaned_data.get("discount") or 0,
        }
        ok, data, _status, msg = backend_post("/api/ui/session/create/", payload=payload)
        if not ok:
            form.add_error(None, f"❌ {msg or 'Could not create session.'}")
            return render(request, self.template_name, {"form": form,"ai_chat_history": ai_history_get(request),})

        session_id = data.get("session_id")
        return HttpResponseRedirect(reverse("session-details", kwargs={"session_pk": session_id}))


class EditSessionView(View):
    template_name = "webapp/edit_session.html"

    def get(self, request: HttpRequest, session_pk: int) -> HttpResponse:
        ok, ctx, msg = get_session_context(session_pk)
        if not ok:
            return render(request, self.template_name, {"form": SessionForm(), "error": msg, "session_pk": session_pk,"ai_chat_history": ai_history_get(request),})

        session_data = ctx.get("session") or {}
        form = SessionForm(
            initial={
                "title": session_data.get("title", ""),
                "tax": session_data.get("tax", 0),
                "service": session_data.get("service", 0),
                "discount": session_data.get("discount", 0),
            }
        )
        return render(request, self.template_name, {"form": form, "session_pk": session_pk,"ai_chat_history": ai_history_get(request),})

    def post(self, request: HttpRequest, session_pk: int) -> HttpResponse:
        form = SessionForm(request.POST)
        if not form.is_valid():
            return render(request, self.template_name, {"form": form, "session_pk": session_pk,"ai_chat_history": ai_history_get(request),})

        payload = {
            "title": form.cleaned_data.get("title") or "",
            "tax": form.cleaned_data.get("tax") or 0,
            "service": form.cleaned_data.get("service") or 0,
            "discount": form.cleaned_data.get("discount") or 0,
        }
        ok, _data, _status, msg = backend_post(f"/api/ui/session/{session_pk}/update/", payload=payload)
        if not ok:
            form.add_error(None, f"❌ {msg or 'Could not update session.'}")
            return render(request, self.template_name, {"form": form, "session_pk": session_pk,"ai_chat_history": ai_history_get(request),})

        return HttpResponseRedirect(reverse("session-details", kwargs={"session_pk": session_pk}))


class DeleteSessionView(View):
    template_name = "webapp/delete_session.html"
    success_url = reverse_lazy("all-sessions")

    def get(self, request: HttpRequest, session_pk: int) -> HttpResponse:
        ok, ctx, msg = get_session_context(session_pk)
        session_data = ctx.get("session") if ok else {"id": session_pk}
        return render(request, self.template_name, {"session": session_data, "error": msg if not ok else None,"ai_chat_history": ai_history_get(request),})

    def post(self, request: HttpRequest, session_pk: int) -> HttpResponse:
        ok, _data, _status, msg = backend_post(f"/api/ui/session/{session_pk}/delete/", payload={})
        if not ok:
            ok2, ctx2, _ = get_session_context(session_pk)
            session_data = ctx2.get("session") if ok2 else {"id": session_pk}
            return render(request, self.template_name, {"session": session_data, "error": f"❌ {msg or 'Could not delete session.'}","ai_chat_history": ai_history_get(request),})
        return HttpResponseRedirect(self.success_url)


class AddPersonView(View):
    template_name = "webapp/add_person.html"

    def get(self, request: HttpRequest, session_pk: int) -> HttpResponse:
        return render(request, self.template_name, {"form": PersonForm(), "session_pk": session_pk,"ai_chat_history": ai_history_get(request),})

    def post(self, request: HttpRequest, session_pk: int) -> HttpResponse:
        form = PersonForm(request.POST)
        if not form.is_valid():
            return render(request, self.template_name, {"form": form, "session_pk": session_pk,"ai_chat_history": ai_history_get(request),})

        payload = {"name": form.cleaned_data.get("name") or ""}
        ok, data, _status, msg = backend_post(f"/api/ui/session/{session_pk}/person/add/", payload=payload)
        if not ok:
            form.add_error(None, f"❌ {msg or 'Could not add person.'}")
            return render(request, self.template_name, {"form": form, "session_pk": session_pk,"ai_chat_history": ai_history_get(request),})

        person_id = data.get("person_id")
        return HttpResponseRedirect(reverse("person-details", kwargs={"session_pk": session_pk, "person_pk": person_id}))


class AlterUserView(View):
    template_name = "webapp/alter_user.html"

    def get(self, request: HttpRequest, session_pk: int, person_pk: int) -> HttpResponse:
        ok, ctx, msg = get_session_context(session_pk)
        if not ok:
            return render(request, self.template_name, {"form": PersonForm(), "error": msg, "session_pk": session_pk, "person_pk": person_pk,"ai_chat_history": ai_history_get(request),})

        person = find_person_in_context(ctx, person_pk)
        if not person:
            raise Http404("Person not found")

        form = PersonForm(initial={"name": person.get("name", "")})
        return render(request, self.template_name, {"form": form, "person": person, "session_pk": session_pk,"ai_chat_history": ai_history_get(request),})

    def post(self, request: HttpRequest, session_pk: int, person_pk: int) -> HttpResponse:
        form = PersonForm(request.POST)
        if not form.is_valid():
            return render(request, self.template_name, {"form": form, "session_pk": session_pk, "person_pk": person_pk,"ai_chat_history": ai_history_get(request),})

        payload = {"name": form.cleaned_data.get("name") or ""}
        ok, _data, _status, msg = backend_post(f"/api/ui/person/{person_pk}/rename/", payload=payload)
        if not ok:
            form.add_error(None, f"❌ {msg or 'Could not rename person.'}")
            return render(request, self.template_name, {"form": form, "session_pk": session_pk, "person_pk": person_pk,"ai_chat_history": ai_history_get(request),})

        return HttpResponseRedirect(reverse("person-details", kwargs={"session_pk": session_pk, "person_pk": person_pk,}))


class PersonDeleteView(View):
    template_name = "webapp/delete_person.html"

    def get(self, request: HttpRequest, session_pk: int, person_pk: int) -> HttpResponse:
        ok, ctx, msg = get_session_context(session_pk)
        if not ok:
            return render(request, self.template_name, {"person": None, "error": msg,"ai_chat_history": ai_history_get(request),})

        person = find_person_in_context(ctx, person_pk)
        if not person:
            raise Http404("Person not found")

        return render(request, self.template_name, {"person": person, "session_pk": session_pk,"ai_chat_history": ai_history_get(request),})

    def post(self, request: HttpRequest, session_pk: int, person_pk: int) -> HttpResponse:
        ok, _data, _status, msg = backend_post(f"/api/ui/person/{person_pk}/delete/", payload={})
        if not ok:
            ok2, ctx2, _ = get_session_context(session_pk)
            person = find_person_in_context(ctx2, person_pk) if ok2 else None
            return render(request, self.template_name, {"person": person, "session_pk": session_pk, "error": f"❌ {msg or 'Could not delete person.'}",
                                                        "ai_chat_history": ai_history_get(request),})

        return HttpResponseRedirect(reverse("session-details", kwargs={"session_pk": session_pk}))


class AddItemView(View):
    template_name = "webapp/add_item.html"

    def get(self, request: HttpRequest, session_pk: int, person_pk: int) -> HttpResponse:
        ok, ctx, msg = get_session_context(session_pk)
        if not ok:
            return render(request, self.template_name, {"form": ItemForm(), "error": msg, "session_pk": session_pk, "person_pk": person_pk,"ai_chat_history": ai_history_get(request),})

        person = find_person_in_context(ctx, person_pk)
        if not person:
            raise Http404("Person not found")

        return render(
            request,
            self.template_name,
            {"form": ItemForm(), "name": person.get("name", ""), "session_pk": session_pk, "person_pk": person_pk,"ai_chat_history": ai_history_get(request),},
        )

    def post(self, request: HttpRequest, session_pk: int, person_pk: int) -> HttpResponse:
        form = ItemForm(request.POST)
        if not form.is_valid():
            return render(request, self.template_name, {"form": form, "session_pk": session_pk, "person_pk": person_pk,"ai_chat_history": ai_history_get(request),})

        payload = {
            "name": form.cleaned_data.get("name") or "",
            "price": form.cleaned_data.get("price") or 0,
            "quantity": form.cleaned_data.get("quantity") or 1,
        }
        ok, _data, _status, msg = backend_post(f"/api/ui/person/{person_pk}/item/add/", payload=payload)
        if not ok:
            form.add_error(None, f"❌ {msg or 'Could not add item.'}")
            return render(request, self.template_name, {"form": form, "session_pk": session_pk, "person_pk": person_pk,"ai_chat_history": ai_history_get(request),})

        return HttpResponseRedirect(reverse("person-details", kwargs={"session_pk": session_pk, "person_pk": person_pk,"ai_chat_history": ai_history_get(request),}))


class AlterItemView(View):
    template_name = "webapp/alter_item.html"

    def get(self, request: HttpRequest, session_pk: int,person_pk: int, item_pk: int) -> HttpResponse:
        ok, ctx, msg = get_session_context(session_pk)
        if not ok:
            return render(request, self.template_name, {"form": ItemForm(), "error": msg, "session_pk": session_pk, "person_pk":person_pk, "item_pk": item_pk,"ai_chat_history": ai_history_get(request),})

        item, owner = find_item_in_context(ctx, item_pk)
        if not item or not owner:
            raise Http404("Item not found")

        form = ItemForm(
            initial={
                "name": item.get("name", ""),
                "price": item.get("price", 0),
                "quantity": item.get("quantity", 1),
            }
        )
        return render(
            request,
            self.template_name,
            {"form": form, "item": item, "session_pk": session_pk, "person_pk": owner.get("id"),"ai_chat_history": ai_history_get(request),},
        )

    def post(self, request: HttpRequest, session_pk: int, person_pk: int, item_pk: int) -> HttpResponse:
        form = ItemForm(request.POST)
        if not form.is_valid():
            return render(request, self.template_name, {"form": form, "session_pk": session_pk, "person_pk": person_pk, "item_pk": item_pk,"ai_chat_history": ai_history_get(request),})

        payload = {
            "name": form.cleaned_data.get("name") or "",
            "price": form.cleaned_data.get("price") or 0,
            "quantity": form.cleaned_data.get("quantity") or 1,
        }
        ok, _data, _status, msg = backend_post(f"/api/ui/item/{item_pk}/update/", payload=payload)
        if not ok:
            form.add_error(None, f"❌ {msg or 'Could not update item.'}")
            return render(request, self.template_name, {"form": form, "session_pk": session_pk, "person_pk": person_pk, "item_pk": item_pk,"ai_chat_history": ai_history_get(request),})

        # Redirect to owner (best effort)
        ok2, ctx2, _ = get_session_context(session_pk)
        _item, owner = find_item_in_context(ctx2, item_pk) if ok2 else (None, None)
        owner_id = owner.get("id") if owner else None
        if owner_id:
            return HttpResponseRedirect(reverse("person-details", kwargs={"session_pk": session_pk, "person_pk": owner_id}))
        return HttpResponseRedirect(reverse("session-details", kwargs={"session_pk": session_pk}))


class ItemDeleteView(View):
    template_name = "webapp/delete_item.html"

    def get(self, request: HttpRequest, session_pk: int,person_pk: int, item_pk: int) -> HttpResponse:
        ok, ctx, msg = get_session_context(session_pk)
        if not ok:
            return render(request, self.template_name, {"item": None, "error": msg, "session_pk": session_pk, "person_pk": person_pk,"ai_chat_history": ai_history_get(request),})

        item, owner = find_item_in_context(ctx, item_pk)
        if not item:
            raise Http404("Item not found")

        return render(
            request,
            self.template_name,
            {"item": item, "person_pk": person_pk, "session_pk": session_pk,"ai_chat_history": ai_history_get(request),},
        )

    def post(self, request: HttpRequest, session_pk: int,person_pk: int, item_pk: int) -> HttpResponse:
        ok, _data, _status, msg = backend_post(f"/api/ui/item/{item_pk}/delete/", payload={})
        if not ok:
            ok2, ctx2, _ = get_session_context(session_pk)
            item, owner = find_item_in_context(ctx2, item_pk) if ok2 else (None, None)
            return render(
                request,
                self.template_name,
                {
                    "item": item,
                    "person_pk": person_pk,
                    "session_pk": session_pk,
                    "error": f"❌ {msg or 'Could not delete item.'}",
                    "ai_chat_history": ai_history_get(request),
                },
            )

        return HttpResponseRedirect(
            reverse("person-details", kwargs={"session_pk": session_pk, "person_pk": person_pk})
        )