from django.shortcuts import render
from django.views import View
from django.views.generic import TemplateView
from django.views.generic import ListView,DetailView,RedirectView
from django.views.generic.edit import CreateView,UpdateView, DeleteView
from .models import Person,Item,Session
from django.urls import reverse_lazy
import json
from django.http import JsonResponse
from .ai.llm import parse_receipt_prompt
from django.views.decorators.http import require_POST
from .ai.validation import validate_create_session_payload,validate_edit_session_payload,validate_edit_person_payload,validate_edit_item_payload,validate_edit_session_entities_payload
from .ai.services import execute_create_session, execute_edit_session,execute_edit_person,execute_edit_item,execute_edit_session_entities
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_GET
from django.conf import settings
from django.template.loader import render_to_string




# Create your views here.
@require_GET
@ensure_csrf_cookie  # ✅ this forces csrftoken cookie to be set on the response
def ai_csrf(request):
    return JsonResponse({"ok": True})
class HomeView(RedirectView):
    url = reverse_lazy('all-sessions')    
class PersonsView(ListView):
    template_name = "app/all_persons.html"
    model = Person
    context_object_name = 'persons'
    def get_queryset(self):
        session_id = self.kwargs['session_pk']
        return Person.objects.filter(session_id=session_id)
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['grand_total'] = sum(
            person.calculate_amount() for person in context['persons']
        )
        return context
    # def get_queryset(self):
    #     base_query = super().get_queryset()
    #     data = base_query.filter(rating__gt=0)
    #     return data

class PersonDetailsView(DetailView):
    template_name = "app/single_person.html"
    model = Person
    context_object_name = "person"
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['session'] = Session.objects.get(pk=self.kwargs['session_pk'])
        return context
class AddPersonView(CreateView):
    model = Person
    fields = ['name']
    template_name = 'app/add_person.html'
    def get_success_url(self):
        return reverse_lazy('person-details', kwargs={'session_pk': self.object.session.pk,
                                                      'pk': self.object.pk})

    def form_valid(self, form):
        session = Session.objects.get(pk=self.kwargs['session_pk'])
        form.instance.session = session
        return super().form_valid(form)
class AddItemView(CreateView):
    model = Item
    fields = ['name', 'price', 'quantity']
    template_name = 'app/add_item.html'
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["name"] =  Person.objects.get(pk=self.kwargs['person_pk']).name
        context["session_pk"] = self.kwargs['session_pk']
        return context
    

    def form_valid(self, form):
        # Attach the item to the correct Person
        person = Person.objects.get(pk=self.kwargs['person_pk'])
        form.instance.person = person
        return super().form_valid(form)

    def get_success_url(self):
        return reverse_lazy(
        'person-details',
        kwargs={
            'session_pk': self.object.person.session.pk,
            'pk': self.object.person.pk
        }
    )
    
class AlterUserView(UpdateView):
    model = Person
    fields = ['name']
    template_name = 'app/alter_user.html'
    context_object_name = 'person'

        # redirect back to the person's detail page after saving
    def get_success_url(self):
        return reverse_lazy(
        'person-details',
        kwargs={
            'session_pk': self.object.session.pk,
            'pk': self.object.pk
        }   
    )
class PersonDeleteView(DeleteView):
    model = Person
    template_name = 'app/delete_person.html'
    def get_success_url(self):
        return reverse_lazy(
            'session-details',
            kwargs={'pk': self.object.session.pk}
        )

class AlterItemView(UpdateView):
    model = Item
    fields = ['name', 'price', 'quantity']
    template_name = 'app/alter_item.html'
    context_object_name = 'item'

    def get_success_url(self):
        return reverse_lazy(
        'person-details',
        kwargs={
            'session_pk': self.object.person.session.pk,
            'pk': self.object.person.pk
        }
    )


class ItemDeleteView(DeleteView):
    model = Item
    template_name = 'app/delete_item.html'

    def get_success_url(self):
        return reverse_lazy(
            'person-details',
            kwargs={
            'session_pk': self.object.person.session.pk,
            'pk': self.object.person.pk
        }
        )
class SessionsView(ListView):
    model = Session
    template_name = 'app/all_sessions.html'
    context_object_name = 'sessions'
class SessionDetailView(DetailView):
    model = Session
    template_name = 'app/single_session.html'
    context_object_name = 'session'


    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['grand_total'] = self.object.total()#sum(person.calculate_amount() for person in self.object.persons.all())
        return context
class AddSessionView(CreateView):
    model = Session
    fields = ['title', 'tax', 'service', 'discount']
    template_name = 'app/add_session.html'

    def get_success_url(self):
        return reverse_lazy('session-details', kwargs={'pk': self.object.pk})
class EditSessionView(UpdateView):
    model = Session
    template_name = "app/edit_session.html"
    fields = ['title', 'tax', 'service', 'discount']  # fields to edit
    pk_url_kwarg = 'session_pk'

    def get_success_url(self):
        return reverse_lazy('session-details', kwargs={'pk': self.object.pk})
class DeleteSessionView(DeleteView):
    model = Session
    pk_url_kwarg = 'session_pk'
    template_name = 'app/delete_session.html' 
    context_object_name = "session"
    success_url = reverse_lazy('all-sessions')  # your main sessions page
class SessionDetailDetailedView(DetailView):
    model = Session
    template_name = "app/single_session_detailed.html"
    context_object_name = "session"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['persons'] = (
            self.object.persons
            .prefetch_related('items')
        )
        return context

# =========================================================
# AI Assistant
# =========================================================
CHAT_KEY = "ai_chat_history"
MAX_TURNS = 30
MAX_CHARS = 2000


def get_history(request):
    # centralized history access
    return request.session.get(CHAT_KEY, [])


def save_history(request, history):
    # centralized trimming + session update
    request.session[CHAT_KEY] = history[-MAX_TURNS:]
    request.session.modified = True


def add_turn(request, role, content):
    # centralized sanitizing + trimming (prevents duplication bugs)
    content = (content or "").strip()
    if not content:
        return
    history = get_history(request)
    history.append({"role": role, "content": content[:MAX_CHARS]})
    save_history(request, history)


def render_history_html(request):
    # render chat from session (server is source of truth)
    return render_to_string(
        "app/_ai_messages.html",
        {"history": get_history(request)},
        request=request,
    )


def reply(request, message, *, status=200, action="none", redirect_url=None):
    add_turn(request, "assistant", message)

    payload = {
        "response": message,
        "action": action,
        "html": render_history_html(request), 
    }
    if redirect_url:
        payload["redirect_url"] = redirect_url

    return JsonResponse(payload, status=status)

def build_session_context(session_id: int) -> dict:
    people = (
        Person.objects
        .filter(session_id=session_id)
        .prefetch_related("items")
        .order_by("id")
    )

    return {
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
    }



@require_POST
def ai_parse(request):
    try:
        data = json.loads(request.body.decode("utf-8"))
        prompt = (data.get("prompt") or "").strip()
        if not prompt:
            return JsonResponse(
                {"response": "Please type something.", "action": "none", "html": render_history_html(request)},
                status=400,
            )

        # store user prompt ONCE immediately for all intents/errors
        add_turn(request, "user", prompt)
        session_id = data.get("context", {}).get("session_id")
        context = build_session_context(session_id)

        ai_data = parse_receipt_prompt(prompt, history=get_history(request),context=context)

        if not ai_data:
            return reply(
                request,
                "I couldn’t understand that. Try asking a question or describing a receipt.",
                status=400,
            )

        intent = (ai_data.get("intent") or "").strip()

        # ✅ kept: session_id fallback for edit_session (from context)
        ctx = data.get("context") or {}
        ctx_session_id = ctx.get("session_id")
        if intent in {"edit_session", "edit_person", "edit_item", "edit_session_entities"} and not ai_data.get("session_id") and ctx_session_id:
            ai_data["session_id"] = ctx_session_id

        # =========================
        # Intent: general_inquiry
        # =========================
        if intent == "general_inquiry":
            response_text = ai_data.get("answer", "Sure — what would you like to know?")
            # reply() (stores assistant + returns html consistently)
            return reply(request, response_text, action="none")

        # =========================
        # Intent: create_session
        # =========================
        if intent == "create_session":
            result = validate_create_session_payload(ai_data)
            if not result.ok:
                return reply(request, "❌ " + " | ".join(result.errors), status=400)

            exec_result = execute_create_session(result.data)
            return reply(
                request,
                exec_result["message"],
                action="redirect",
                redirect_url=exec_result["redirect_url"],
            )

        # =========================
        # Intent: edit_session
        # =========================
        if intent == "edit_session":
            edit_result = validate_edit_session_payload(ai_data)
            if not edit_result.ok:
                return reply(request, "❌ " + " | ".join(edit_result.errors), status=400)

            try:
                exec_result = execute_edit_session(edit_result.data)
            except ValueError as ve:
                return reply(request, f"❌ {ve}", status=400)

            return reply(
                request,
                exec_result["message"],
                action="redirect",
                redirect_url=exec_result["redirect_url"],
            )
        # =========================
        # Intent: edit_person
        # =========================
        if intent == "edit_person":
            result = validate_edit_person_payload(ai_data)
            if not result.ok:
                return reply(request, "\n".join(result.errors), status=400)

            exec_result = execute_edit_person(result.data)
            if not exec_result.get("ok"):
                return reply(request, exec_result["message"], status=400)

            return reply(
                request,
                exec_result["message"],
                action="redirect",
                redirect_url=exec_result["redirect_url"],
            )
        # =========================
        # Intent: edit_item
        # =========================
        if intent == "edit_item":
            result = validate_edit_item_payload(ai_data)
            if not result.ok:
                return reply(request, "\n".join(result.errors), status=400)

            exec_result = execute_edit_item(result.data)
            if not exec_result.get("ok"):
                return reply(request, exec_result["message"], status=400)

            return reply(
                request,
                exec_result["message"],
                action="redirect",
                redirect_url=exec_result["redirect_url"],
            )

        # =========================
        # Intent: edit_session_entities
        # =========================
        if intent == "edit_session_entities":
            result = validate_edit_session_entities_payload(ai_data)
            if not result.ok:
                return reply(request, "\n".join(result.errors), status=400)

            exec_result = execute_edit_session_entities(result.data)
            if not exec_result.get("ok"):
                return reply(request, exec_result["message"], status=400)

            return reply(
                request,
                exec_result["message"],
                action="redirect",
                redirect_url=exec_result["redirect_url"],
            )


        # =========================
        # Unknown intent fallback
        # =========================
        return reply(
            request,
            "I wasn’t sure what you meant. Ask me what I can do, or tell me to create a receipt.",
            status=400,
        )

    except json.JSONDecodeError:
        return JsonResponse(
            {"response": "Invalid JSON payload.", "action": "none", "html": render_history_html(request)},
            status=400,
        )
    except Exception as e:
        msg = f"{type(e).__name__}: {e}" if settings.DEBUG else "Error processing your request."
        return JsonResponse(
            {"response": msg, "action": "none", "html": render_history_html(request)},
            status=400,
        )
