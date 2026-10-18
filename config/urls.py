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
    # Second URL name for the same view/path (M004 - identity app): allauth's
    # own SignupView falls back to reverse("account_login") if it's ever
    # reached with no pending signup in session (rare - only when a provider
    # supplies no email at all). allauth.account.urls is deliberately not
    # mounted (see the identity/socialaccount paths below), so that name
    # would otherwise not exist at all.
    path(
        "accounts/login/",
        auth_views.LoginView.as_view(template_name="registration/login.html"),
        name="account_login",
    ),
    path("accounts/logout/", auth_views.LogoutView.as_view(), name="logout"),
    # M004 - identity app: only allauth's socialaccount + provider urls are
    # mounted, deliberately never allauth.urls/allauth.account.urls, so
    # there is no collision with the two custom accounts/login|logout paths
    # above and no public local-password registration endpoint exists.
    path("identity/", include("allauth.socialaccount.urls")),
    path("identity/", include("allauth.socialaccount.providers.google.urls")),
    path("identity/", include("allauth.socialaccount.providers.microsoft.urls")),
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
    path(
        "organisations/<uuid:organisation_id>/security-state/",
        include("security_state.urls"),
    ),
    path(
        "organisations/<uuid:organisation_id>/governance/",
        include("governance.urls"),
    ),
    path(
        "organisations/<uuid:organisation_id>/workplace/",
        include("workplace.urls"),
    ),
    path(
        "organisations/<uuid:organisation_id>/policy/",
        include("policy.urls"),
    ),
    path(
        "organisations/<uuid:organisation_id>/questionnaire/",
        include("questionnaire.urls"),
    ),
    path(
        "organisations/<uuid:organisation_id>/tasks/",
        include("security_tasks.urls"),
    ),
    # M010B: deliberately NOT "organisations/<uuid:organisation_id>/
    # foundations/" - that exact path already belongs to
    # organisations.urls's own "organisations:foundations" (the
    # read-only 18-item Foundations workspace); colliding with it would
    # make Django's resolver silently match that app's pattern first
    # (included earlier) for every request here, the same path-
    # collision class security_baseline.views.baseline_view's own
    # docstring already documents finding for "foundations/" vs
    # "baseline/questions/".
    path(
        "organisations/<uuid:organisation_id>/foundations-journey/",
        include("foundations_journey.urls"),
    ),
    path("organisations/", include("activity.urls")),
]
