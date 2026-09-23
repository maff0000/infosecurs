from django.contrib import admin

from risk_register.models import Risk

# Registered for engineering/operational visibility only (superuser-gated).
# This is not the product UI - see risk_register/views.py and
# docs/pids/M002-SECURITY-BASELINE-AND-INITIAL-RISK.md §8, §19-§20.
admin.site.register(Risk)
