from django.contrib import admin

from governance.models import GovernanceRoleAssignment, OrganisationPerson

# Registered for engineering/operational visibility only (superuser-gated) -
# not the product UI (see governance/views.py), matching every other app's
# admin.py in this codebase (e.g. evidence/admin.py).
admin.site.register(OrganisationPerson)
admin.site.register(GovernanceRoleAssignment)
