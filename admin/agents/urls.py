"""URL routing for the agents app."""

from django.urls import path
from . import views

urlpatterns = [
    # Auth
    path("auth/login/", views.login_view, name="login"),
    path("auth/register/", views.agent_register, name="register"),
    path("auth/logout/", views.logout_view, name="logout"),

    # Agents
    path("", views.agent_list_view, name="agent_list"),
    path("agents/create/", views.agent_create, name="agent_create"),
    path("agents/seed-demo/", views.seed_demo_agent, name="seed_demo_agent"),
    path("agents/generate-prompt/", views.generate_system_prompt, name="generate_system_prompt"),
    path("agents/<str:agent_id>/", views.agent_detail, name="agent_detail"),
    path("agents/<str:agent_id>/edit/", views.agent_edit, name="agent_edit"),
    path("agents/<str:agent_id>/delete/", views.agent_delete, name="agent_delete"),
    path("agents/<str:agent_id>/deploy/", views.agent_deploy, name="agent_deploy"),
    path("agents/<str:agent_id>/documents/", views.agent_documents, name="agent_documents"),
    path(
        "agents/<str:agent_id>/documents/upload/",
        views.agent_upload_document,
        name="agent_upload_document",
    ),
    path(
        "agents/<str:agent_id>/documents/<path:doc_name>/delete/",
        views.agent_delete_document,
        name="agent_delete_document",
    ),
]
