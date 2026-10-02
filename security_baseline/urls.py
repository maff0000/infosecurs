from django.urls import path

from security_baseline import views

app_name = "security_baseline"

urlpatterns = [
    # Legacy entry point - kept so existing reverse()s (entitlements'
    # seeded ProductArea.destination_view_name, organisations.overview's
    # next_action_url_name) keep working; the view itself now only
    # redirects into the guided journey below (see views.baseline_view's
    # own docstring).
    path("<uuid:organisation_id>/baseline/", views.baseline_view, name="baseline"),
    # M008C guided Stage 4 journey (docs/design/M008C-UX-FLOW-DESIGN.md).
    # Deliberately NOT "<uuid:organisation_id>/foundations/" -
    # `organisations.urls` already owns that exact path (its own
    # `organisations:foundations` - the read-only 18-item Foundations
    # workspace, a completely different page) at the same
    # "organisations/" prefix `config/urls.py` mounts both apps under;
    # colliding with it would make Django's resolver silently match
    # `organisations.urls`' pattern first (it is `include()`d earlier)
    # for every request to this path, never reaching this app's view at
    # all - found and fixed during this WI's own test run.
    path(
        "<uuid:organisation_id>/baseline/questions/",
        views.foundations_start,
        name="foundations_start",
    ),
    path(
        "<uuid:organisation_id>/baseline/questions/<str:question_key>/",
        views.foundations_question,
        name="foundations_question",
    ),
]
