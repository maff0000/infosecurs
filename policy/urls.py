from django.urls import path

from policy import views

app_name = "policy"

urlpatterns = [
    path("", views.policy_detail, name="detail"),
    path("generate/", views.policy_generate, name="generate"),
]
