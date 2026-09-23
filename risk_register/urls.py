from django.urls import path

from risk_register import interpretation_views, views

app_name = "risk_register"

urlpatterns = [
    path("", views.risk_list, name="list"),
    path("generate/", views.risk_generate, name="generate"),
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
