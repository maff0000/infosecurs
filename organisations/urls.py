from django.urls import path

from organisations import views

app_name = "organisations"

urlpatterns = [
    path("", views.organisation_list, name="list"),
    path("new/", views.organisation_create, name="create"),
    path("<uuid:organisation_id>/", views.organisation_detail, name="detail"),
    path("<uuid:organisation_id>/profile/", views.organisation_profile, name="profile"),
    path("<uuid:organisation_id>/hub/", views.organisation_hub, name="organisation_hub"),
    path("<uuid:organisation_id>/foundations/", views.organisation_foundations, name="foundations"),
    # M008C/M008B-WI2a: the three new Stage 1-3 guided-journey pages
    # (docs/design/M008B-STAGES-1-3-CATALOGUE.md). Nested under
    # "foundations/" to read as part of that same journey in the URL
    # itself, same as `organisations:foundations` just above.
    path(
        "<uuid:organisation_id>/foundations/stage-1-business/",
        views.organisation_stage1_business,
        name="stage1_business",
    ),
    path(
        "<uuid:organisation_id>/foundations/stage-2-people-workplaces/",
        views.organisation_stage2_people_workplaces,
        name="stage2_people_workplaces",
    ),
    path(
        "<uuid:organisation_id>/foundations/stage-3-technology-data/",
        views.organisation_stage3_technology_data,
        name="stage3_technology_data",
    ),
    # M008A: dev-only Customer Zero reset
    # (docs/evidence/M008A-RESET-DELETION-MANIFEST.md). Reachable at all
    # only when settings.CUSTOMER_ZERO_RESET_ENABLED is True - see
    # views.customer_zero_reset for the fail-closed 404 gate checked
    # first, before anything else, for both GET and POST.
    path(
        "<uuid:organisation_id>/dev-tools/reset/",
        views.customer_zero_reset,
        name="customer_zero_reset",
    ),
]
