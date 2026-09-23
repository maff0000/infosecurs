from django.urls import path

from risk_register import views

app_name = "risk_register"

urlpatterns = [
    path("", views.risk_list, name="list"),
    path("generate/", views.risk_generate, name="generate"),
    path("<uuid:risk_id>/", views.risk_detail, name="detail"),
    path("<uuid:risk_id>/edit/", views.risk_edit, name="edit"),
    path("<uuid:risk_id>/confirm/", views.risk_confirm, name="confirm"),
    path("<uuid:risk_id>/dismiss/", views.risk_dismiss, name="dismiss"),
]
