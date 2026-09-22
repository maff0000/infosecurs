from django.urls import path

from organisations import views

app_name = "organisations"

urlpatterns = [
    path("", views.organisation_list, name="list"),
    path("new/", views.organisation_create, name="create"),
    path("<uuid:organisation_id>/", views.organisation_detail, name="detail"),
    path("<uuid:organisation_id>/profile/", views.organisation_profile, name="profile"),
]
