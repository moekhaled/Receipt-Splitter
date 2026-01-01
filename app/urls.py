from django.urls import path
from . import views
# urlpatterns = [
#     path("",views.PersonsView.as_view(),name="all-persons"),
#     path("persons/<int:pk>",views.PersonDetailsView.as_view(),name="person-details"),
#     path('persons/add/', views.AddPersonView.as_view(), name='add-person'),
#     path('persons/<int:person_pk>/add-item/', views.AddItemView.as_view(), name='add-item'),
#     path('persons/<int:pk>/alter/', views.AlterUserView.as_view(), name='alter-user'),
#     path('persons/<int:pk>/delete/', views.PersonDeleteView.as_view(), name='delete-person'),
#     path('items/<int:pk>/alter/', views.AlterItemView.as_view(), name='alter-item'),
#     path('items/<int:pk>/delete/', views.ItemDeleteView.as_view(), name='delete-item'),
#     path('sessions/', views.SessionsView.as_view(), name='all-sessions'),
#     path('sessions/<int:pk>/', views.SessionDetailView.as_view(), name='session-details'),]
urlpatterns = [
    #base
    path('', views.HomeView.as_view()),
    # Sessions
    path('sessions/', views.SessionsView.as_view(), name='all-sessions'),
    path('sessions/<int:pk>/', views.SessionDetailView.as_view(), name='session-details'),
    path("sessions/<int:pk>/details/",views.SessionDetailDetailedView.as_view(),name="session-details-detailed"),
    path('sessions/add/', views.AddSessionView.as_view(), name='add-session'),
    path('sessions/<int:session_pk>/edit/', views.EditSessionView.as_view(), name='edit-session'),
    path('sessions/<int:session_pk>/delete/', views.DeleteSessionView.as_view(), name='delete-session'),


    # Persons under a session
    path('sessions/<int:session_pk>/persons/', views.PersonsView.as_view(), name='all-persons'),
    path('sessions/<int:session_pk>/persons/add/', views.AddPersonView.as_view(), name='add-person'),
    path('sessions/<int:session_pk>/persons/<int:pk>/', views.PersonDetailsView.as_view(), name='person-details'),
    path('sessions/<int:session_pk>/persons/<int:pk>/alter/', views.AlterUserView.as_view(), name='alter-user'),
    path('sessions/<int:session_pk>/persons/<int:pk>/delete/', views.PersonDeleteView.as_view(), name='delete-person'),

    # Items under a person
    path('sessions/<int:session_pk>/persons/<int:person_pk>/add-item/', views.AddItemView.as_view(), name='add-item'),
    path('items/<int:pk>/alter/', views.AlterItemView.as_view(), name='alter-item'),
    path('items/<int:pk>/delete/', views.ItemDeleteView.as_view(), name='delete-item'),
]
