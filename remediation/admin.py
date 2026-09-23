from django.contrib import admin

from remediation.models import RemediationAction

# Registered for engineering/operational visibility only (superuser-gated).
# This is not the product UI - see remediation/views.py and
# docs/pids/M003-EVIDENCE-AND-SECURITY-STATE.md §6.5, §13, §18.
admin.site.register(RemediationAction)
