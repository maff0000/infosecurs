from django.urls import path

from security_state import views

app_name = "security_state"

urlpatterns = [
    path("", views.security_state_list, name="list"),
    path("<str:control_key>/", views.security_state_detail, name="detail"),
]
