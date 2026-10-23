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
    # M010E PID §3 - the Monthly/PRO-gated Customer Assurance status page
    # (see views.assurance_status's own docstring for the explicit
    # capability-gating reasoning).
    path("assurance/", views.assurance_status, name="assurance_status"),
    # WO-IRENE-001 Increment 2 (browser-wiring) - Stage 3 question-engine
    # wiring (see views.stage3_panel/stage3_save/stage3_explain's own
    # docstrings). Additive only - nothing above this is touched.
    path("stage3/", views.stage3_panel, name="stage3_panel"),
    path("stage3/save/", views.stage3_save, name="stage3_save"),
    path("stage3/explain/", views.stage3_explain, name="stage3_explain"),
]
