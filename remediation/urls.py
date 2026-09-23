from django.urls import path

from remediation import views

app_name = "remediation"

urlpatterns = [
    path("", views.action_list, name="list"),
    path("new/", views.action_create, name="create"),
    path("from-risk/<uuid:risk_id>/", views.action_create_from_risk, name="create_from_risk"),
    path("<uuid:action_id>/", views.action_detail, name="detail"),
    path("<uuid:action_id>/edit/", views.action_edit, name="edit"),
    path("<uuid:action_id>/start/", views.action_start, name="start"),
    path("<uuid:action_id>/complete/", views.action_complete, name="complete"),
    path("<uuid:action_id>/accept/", views.action_accept, name="accept"),
    path("<uuid:action_id>/attach-evidence/", views.action_attach_evidence, name="attach_evidence"),
]
