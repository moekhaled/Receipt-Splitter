from django.urls import path
from . import views

urlpatterns = [
    path("health/", views.health, name="ai-health"),
    path("csrf/", views.csrf, name="ai-csrf"),  
    path("forward/", views.forward_execute, name="ai-forward"),
    path("parse/", views.parse_and_execute, name="ai-parse"),

]
