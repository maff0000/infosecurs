from django.urls import path

from activity import views

app_name = "activity"

urlpatterns = [
    path("<uuid:organisation_id>/activity/", views.activity_list, name="list"),
]
