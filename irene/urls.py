from django.urls import path

from irene import views

app_name = "irene"

urlpatterns = [
    # Direct-URL-enforcement destination for the `irene` ProductArea row
    # (entitlements/migrations/0006_irene_real_destination.py) - M010A's
    # own placeholder, now pointed at a real, independently
    # capability-gated route (see views.workspace's own docstring).
    path("", views.workspace, name="workspace"),
    path("ask/", views.ask, name="ask"),
    path("ask/confirm-task/", views.confirm_task, name="confirm_task"),
    path("preference/auto-open/", views.set_auto_open_preference, name="set_auto_open_preference"),
]
