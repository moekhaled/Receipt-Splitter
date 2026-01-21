import os

import requests
from requests import RequestException

from django.http import HttpResponseRedirect
from django.shortcuts import render
from django.urls import reverse_lazy, reverse
from django.views.generic import ListView, DetailView, RedirectView
from django.views.generic.edit import CreateView, UpdateView, DeleteView

from .models import Person, Item, Session

BACKEND_URL = os.getenv("BACKEND_URL", "http://backend:8000")


# =========================================================
# Backend HTTP helpers (Frontend is read-only; Backend writes)
# =========================================================
def _extract_error_message(payload: dict, default: str = "Request failed.") -> str:
    msg = payload.get("message")
    if msg:
        return msg
    errs = payload.get("errors")
    if isinstance(errs, list) and errs:
        return " | ".join(str(e) for e in errs)
    return default


def backend_get(path: str, *, timeout: int = 10):
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


def backend_post(path: str, *, payload: dict, timeout: int = 15):
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
# Pages (READS)
# =========================================================
class HomeView(RedirectView):
    url = reverse_lazy("all-sessions")


class SessionsView(ListView):
    model = Session
    template_name = "app/all_sessions.html"
    context_object_name = "sessions"


class SessionDetailView(DetailView):
    model = Session
    template_name = "app/single_session.html"
    context_object_name = "session"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # OK: read-only calculation
        context["grand_total"] = self.object.total()
        return context


class SessionDetailDetailedView(DetailView):
    model = Session
    template_name = "app/single_session_detailed.html"
    context_object_name = "session"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # OK: read-only prefetch
        context["persons"] = self.object.persons.prefetch_related("items")
        return context


class PersonsView(ListView):
    template_name = "app/all_persons.html"
    model = Person
    context_object_name = "persons"

    def get_queryset(self):
        session_id = self.kwargs["session_pk"]
        return Person.objects.filter(session_id=session_id)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        session_id = self.kwargs["session_pk"]
        context["session"] = Session.objects.get(pk=session_id)  # helps templates build URLs
        context["grand_total"] = sum(person.calculate_amount() for person in context["persons"])
        return context


class PersonDetailsView(DetailView):
    template_name = "app/single_person.html"
    model = Person
    context_object_name = "person"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["session"] = Session.objects.get(pk=self.kwargs["session_pk"])
        return context


# =========================================================
# Writes (Frontend delegates to Backend)
# =========================================================
class AddSessionView(CreateView):
    model = Session
    fields = ["title", "tax", "service", "discount"]
    template_name = "app/add_session.html"

    def form_valid(self, form):
        payload = {
            "title": form.cleaned_data.get("title") or "",
            "tax": form.cleaned_data.get("tax") or 0,
            "service": form.cleaned_data.get("service") or 0,
            "discount": form.cleaned_data.get("discount") or 0,
        }
        ok, data, _status, msg = backend_post("/api/ui/session/create/", payload=payload)
        if not ok:
            form.add_error(None, f"❌ {msg or 'Could not create session.'}")
            return self.form_invalid(form)

        session_id = data.get("session_id")
        return HttpResponseRedirect(reverse("session-details", kwargs={"pk": session_id}))


class EditSessionView(UpdateView):
    model = Session
    template_name = "app/edit_session.html"
    fields = ["title", "tax", "service", "discount"]
    pk_url_kwarg = "session_pk"

    def form_valid(self, form):
        session_id = self.kwargs["session_pk"]
        payload = {
            "title": form.cleaned_data.get("title") or "",
            "tax": form.cleaned_data.get("tax") or 0,
            "service": form.cleaned_data.get("service") or 0,
            "discount": form.cleaned_data.get("discount") or 0,
        }
        ok, _data, _status, msg = backend_post(f"/api/ui/session/{session_id}/update/", payload=payload)
        if not ok:
            form.add_error(None, f"❌ {msg or 'Could not update session.'}")
            return self.form_invalid(form)

        return HttpResponseRedirect(reverse("session-details", kwargs={"pk": session_id}))


class DeleteSessionView(DeleteView):
    model = Session
    pk_url_kwarg = "session_pk"
    template_name = "app/delete_session.html"
    context_object_name = "session"
    success_url = reverse_lazy("all-sessions")

    def post(self, request, *args, **kwargs):
        session_id = kwargs["session_pk"]
        ok, _data, _status, msg = backend_post(f"/api/ui/session/{session_id}/delete/", payload={})
        if not ok:
            # Show the same confirmation page with an error message
            self.object = self.get_object()
            return render(
                request,
                self.template_name,
                {"session": self.object, "error": f"❌ {msg or 'Could not delete session.'}"},
            )
        return HttpResponseRedirect(self.success_url)


class AddPersonView(CreateView):
    model = Person
    fields = ["name"]
    template_name = "app/add_person.html"

    def form_valid(self, form):
        session_id = self.kwargs["session_pk"]
        payload = {"name": form.cleaned_data.get("name") or ""}
        ok, data, _status, msg = backend_post(f"/api/ui/session/{session_id}/person/add/", payload=payload)
        if not ok:
            form.add_error(None, f"❌ {msg or 'Could not add person.'}")
            return self.form_invalid(form)

        person_id = data.get("person_id")
        return HttpResponseRedirect(
            reverse("person-details", kwargs={"session_pk": session_id, "pk": person_id})
        )


class AlterUserView(UpdateView):
    model = Person
    fields = ["name"]
    template_name = "app/alter_user.html"
    context_object_name = "person"

    def form_valid(self, form):
        person_id = self.object.pk
        payload = {"name": form.cleaned_data.get("name") or ""}
        ok, _data, _status, msg = backend_post(f"/api/ui/person/{person_id}/rename/", payload=payload)
        if not ok:
            form.add_error(None, f"❌ {msg or 'Could not rename person.'}")
            return self.form_invalid(form)

        return HttpResponseRedirect(
            reverse("person-details", kwargs={"session_pk": self.object.session.pk, "pk": self.object.pk})
        )


class PersonDeleteView(DeleteView):
    model = Person
    template_name = "app/delete_person.html"

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        person_id = self.object.pk
        session_pk = self.object.session.pk

        ok, _data, _status, msg = backend_post(f"/api/ui/person/{person_id}/delete/", payload={})
        if not ok:
            return render(
                request,
                self.template_name,
                {"person": self.object, "error": f"❌ {msg or 'Could not delete person.'}"},
            )

        return HttpResponseRedirect(reverse("session-details", kwargs={"pk": session_pk}))


class AddItemView(CreateView):
    model = Item
    fields = ["name", "price", "quantity"]
    template_name = "app/add_item.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        person = Person.objects.get(pk=self.kwargs["person_pk"])
        context["name"] = person.name
        context["session_pk"] = self.kwargs["session_pk"]
        return context

    def form_valid(self, form):
        person_id = self.kwargs["person_pk"]
        payload = {
            "name": form.cleaned_data.get("name") or "",
            "price": form.cleaned_data.get("price") or 0,
            "quantity": form.cleaned_data.get("quantity") or 1,
        }
        ok, data, _status, msg = backend_post(f"/api/ui/person/{person_id}/item/add/", payload=payload)
        if not ok:
            form.add_error(None, f"❌ {msg or 'Could not add item.'}")
            return self.form_invalid(form)

        # Redirect back to the person details
        person = Person.objects.get(pk=person_id)
        return HttpResponseRedirect(
            reverse("person-details", kwargs={"session_pk": person.session.pk, "pk": person.pk})
        )


class AlterItemView(UpdateView):
    model = Item
    fields = ["name", "price", "quantity"]
    template_name = "app/alter_item.html"
    context_object_name = "item"

    def form_valid(self, form):
        item_id = self.object.pk
        payload = {
            "name": form.cleaned_data.get("name") or "",
            "price": form.cleaned_data.get("price") or 0,
            "quantity": form.cleaned_data.get("quantity") or 1,
        }
        ok, _data, _status, msg = backend_post(f"/api/ui/item/{item_id}/update/", payload=payload)
        if not ok:
            form.add_error(None, f"❌ {msg or 'Could not update item.'}")
            return self.form_invalid(form)

        return HttpResponseRedirect(
            reverse(
                "person-details",
                kwargs={"session_pk": self.object.person.session.pk, "pk": self.object.person.pk},
            )
        )


class ItemDeleteView(DeleteView):
    model = Item
    template_name = "app/delete_item.html"

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        item_id = self.object.pk
        person_pk = self.object.person.pk
        session_pk = self.object.person.session.pk

        ok, _data, _status, msg = backend_post(f"/api/ui/item/{item_id}/delete/", payload={})
        if not ok:
            return render(
                request,
                self.template_name,
                {"item": self.object, "error": f"❌ {msg or 'Could not delete item.'}"},
            )

        return HttpResponseRedirect(
            reverse("person-details", kwargs={"session_pk": session_pk, "pk": person_pk})
        )


