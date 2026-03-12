"""livecustomersupport URL Configuration."""

from django.urls import path, include

urlpatterns = [
    path("", include("agents.urls")),
]
