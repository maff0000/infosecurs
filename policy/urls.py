from django.urls import path

from policy import views

app_name = "policy"

urlpatterns = [
    path("", views.policy_detail, name="detail"),
    path("generate/", views.policy_generate, name="generate"),
    path("versions/<uuid:version_id>/", views.policy_version_detail, name="version_detail"),
    path("versions/<uuid:version_id>/edit/", views.policy_edit, name="version_edit"),
    path(
        "versions/<uuid:version_id>/approve/direct/",
        views.policy_approve_direct,
        name="version_approve_direct",
    ),
    path(
        "versions/<uuid:version_id>/approve/external/",
        views.policy_approve_external,
        name="version_approve_external",
    ),
    path(
        "versions/<uuid:version_id>/new-draft/",
        views.policy_new_draft,
        name="version_new_draft",
    ),
    path(
        "versions/<uuid:version_id>/download/",
        views.policy_download,
        name="version_download",
    ),
]
