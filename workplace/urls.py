from django.urls import path

from workplace import views

app_name = "workplace"

urlpatterns = [
    path("", views.workplace_list, name="list"),
    path("new/", views.workplace_create, name="create"),
    path("onboarding/", views.workplace_onboarding_start, name="onboarding_start"),
    path(
        "onboarding/all-remote/",
        views.workplace_onboarding_all_remote,
        name="onboarding_all_remote",
    ),
    path(
        "onboarding/one-office/",
        views.workplace_onboarding_one_office,
        name="onboarding_one_office",
    ),
    path(
        "onboarding/shared-coworking/",
        views.workplace_onboarding_shared_coworking,
        name="onboarding_shared_coworking",
    ),
    path(
        "onboarding/office-and-home/",
        views.workplace_onboarding_office_and_home,
        name="onboarding_office_and_home",
    ),
    path("<uuid:workplace_id>/edit/", views.workplace_edit, name="edit"),
    path("<uuid:workplace_id>/deactivate/", views.workplace_deactivate, name="deactivate"),
    path("<uuid:workplace_id>/activate/", views.workplace_activate, name="activate"),
]
