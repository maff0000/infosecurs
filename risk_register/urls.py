from django.urls import path

from risk_register import interpretation_views, views

app_name = "risk_register"

urlpatterns = [
    path("", views.risk_list, name="list"),
    path("generate/", views.risk_generate, name="generate"),
    # M008C-WI3: Stage 5 "Your Risks & Actions" guided screen - deliberately
    # NOT nested under "<uuid:risk_id>/" (it is not about one specific
    # risk); placed here, alongside "generate/", as its own top-level
    # action under this app's "organisations/<organisation_id>/risks/"
    # prefix (config/urls.py).
    path("foundations/", views.foundations_risks_actions, name="foundations_risks_actions"),
    # M002-3c dispatch: AI practitioner-interpretation trigger - a new,
    # additive URL/view (risk_register/interpretation_views.py), not a
    # change to the existing views.risk_generate above. See
    # interpretation_views.py's module docstring for why.
    path("interpret/", interpretation_views.risk_interpret, name="interpret"),
    path("<uuid:risk_id>/", views.risk_detail, name="detail"),
    path("<uuid:risk_id>/edit/", views.risk_edit, name="edit"),
    path("<uuid:risk_id>/confirm/", views.risk_confirm, name="confirm"),
    path("<uuid:risk_id>/dismiss/", views.risk_dismiss, name="dismiss"),
]
