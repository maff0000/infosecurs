from django.urls import path

from policy import views

app_name = "policy"

urlpatterns = [
    path("", views.policy_detail, name="detail"),
    path("generate/", views.policy_generate, name="generate"),
    path(
        "generate/deterministic/",
        views.policy_generate_deterministic,
        name="generate_deterministic",
    ),
    path("versions/<uuid:version_id>/", views.policy_version_detail, name="version_detail"),
    # M008-WI6 Finding A: the free-text section-editor route
    # (`policy:version_edit` -> `policy.views.policy_edit` ->
    # `PolicyVersionEditForm`) is REMOVED here, not merely unlinked - the
    # URL pattern no longer exists at all, so it 404s for any request,
    # `{% url %}` call, or `reverse()` lookup. See `policy/forms.py`'s
    # module docstring and `policy/tests/test_edit.py` for the full
    # reasoning and regression proof.
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
