from django.contrib import admin
from .models import Person, Item, Session

# Register your models here.
admin.site.register(Person)
admin.site.register(Item)
admin.site.register(Session)