from django.urls import path

from security_baseline import views

app_name = "security_baseline"

urlpatterns = [
    path("<uuid:organisation_id>/baseline/", views.baseline_view, name="baseline"),
]
