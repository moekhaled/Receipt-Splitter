from django.urls import path, include

urlpatterns = [
    path("ai/", include("app.ai_urls")),
]
