from django.apps import AppConfig


class EntitlementsConfig(AppConfig):
    """
    M007-WI1 architecture/data spine (docs/pids/M007-DASHBOARD-SHELL-
    ENTITLEMENTS-FOUNDATION-METRICS.md): the ProductArea/FoundationRequirement
    registry, the package-tier constants, the session contract service and
    the entitlement decision service all live here. Deliberately a new app
    rather than folded into `core` or `organisations` - this is governed
    product/commercial metadata and a cross-cutting service layer that every
    other app will come to depend on (navigation in WI2, route guards in
    WI3, metrics in WI4), not a domain workspace of its own, so it should
    not carry any single domain app's dependencies or lifecycle.
    """

    default_auto_field = "django.db.models.BigAutoField"
    name = "entitlements"

    def ready(self):
        # Wires the current Django/allauth Beta login into the
        # SessionContextIssuer (PID §6.6) - see entitlements/signals.py's
        # module docstring for the full reasoning, including the real-login
        # default package-tier judgement call this makes.
        from django.contrib.auth.signals import user_logged_in

        from entitlements.signals import issue_context_on_login

        user_logged_in.connect(issue_context_on_login, dispatch_uid="entitlements.issue_context_on_login")
