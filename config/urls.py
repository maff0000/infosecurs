from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path(
        "accounts/login/",
        auth_views.LoginView.as_view(template_name="registration/login.html"),
        name="login",
    ),
    path("accounts/logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("", include("core.urls")),
    path("organisations/", include("organisations.urls")),
    path("organisations/", include("security_baseline.urls")),
    path(
        "organisations/<uuid:organisation_id>/assets/",
        include("key_assets.urls"),
    ),
    path(
        "organisations/<uuid:organisation_id>/risks/",
        include("risk_register.urls"),
    ),
    path(
        "organisations/<uuid:organisation_id>/evidence/",
        include("evidence.urls"),
    ),
    path(
        "organisations/<uuid:organisation_id>/actions/",
        include("remediation.urls"),
    ),
    path("organisations/", include("activity.urls")),
]
