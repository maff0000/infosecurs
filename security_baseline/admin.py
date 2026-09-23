from django.contrib import admin

from security_baseline.models import BaselineAnswer, BaselineAssessment

# Registered for engineering/operational visibility only (superuser-gated),
# matching organisations/admin.py. This is not the product UI - see
# security_baseline/views.py for the real page.
admin.site.register(BaselineAssessment)
admin.site.register(BaselineAnswer)
