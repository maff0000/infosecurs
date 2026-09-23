from django.contrib import admin

from policy.models import PolicyDocument, PolicyVersion

# Registered for engineering/operational visibility only (superuser-gated) -
# not the product UI (see policy/views.py), matching every other app's
# admin.py in this codebase (e.g. governance/admin.py, evidence/admin.py).
admin.site.register(PolicyDocument)
admin.site.register(PolicyVersion)
