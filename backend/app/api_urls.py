from django.urls import path
from . import api_views

urlpatterns = [
    path("health/", api_views.health, name="api-health"),

    # Used by AI to fetch context without DB writes in AI:
    path("sessions/<int:session_id>/context/", api_views.session_context, name="api-session-context"),

    # Used by AI: validate + execute via services.py (backend is the writer)
    path("ai/execute/", api_views.ai_execute, name="api-ai-execute"),
    path("ai/history/append/", api_views.ai_history_append, name="ai-history-append"),

    # Used by Frontend: UI reads from the backend 
    path("sessions/", api_views.sessions_list, name="api-sessions-list"),


    # Used by Frontend: UI writes (backend is the writer)
    path("ui/session/create/", api_views.ui_create_session, name="ui-create-session"),
    path("ui/session/<int:session_id>/update/", api_views.ui_update_session, name="ui-update-session"),
    path("ui/session/<int:session_id>/delete/", api_views.ui_delete_session, name="ui-delete-session"),

    path("ui/session/<int:session_id>/person/add/", api_views.ui_add_person, name="ui-add-person"),
    path("ui/person/<int:person_id>/rename/", api_views.ui_rename_person, name="ui-rename-person"),
    path("ui/person/<int:person_id>/delete/", api_views.ui_delete_person, name="ui-delete-person"),

    path("ui/person/<int:person_id>/item/add/", api_views.ui_add_item, name="ui-add-item"),
    path("ui/item/<int:item_id>/update/", api_views.ui_update_item, name="ui-update-item"),
    path("ui/item/<int:item_id>/delete/", api_views.ui_delete_item, name="ui-delete-item"),
]
