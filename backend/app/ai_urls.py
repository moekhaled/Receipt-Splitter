from django.urls import path
from . import ai_views

urlpatterns = [
    path("csrf/", ai_views.ai_csrf, name="ai-csrf"),
    path("parse/", ai_views.ai_parse, name="ai-parse"),
]
