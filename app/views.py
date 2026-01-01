from django.shortcuts import render
from django.views import View
from django.views.generic import TemplateView
from django.views.generic import ListView,DetailView,RedirectView
from django.views.generic.edit import CreateView,UpdateView, DeleteView
from .models import Person,Item,Session
from django.urls import reverse_lazy

# Create your views here.
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
        return reverse_lazy('all-sessions')
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
