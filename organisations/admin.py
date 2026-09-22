from django.contrib import admin

from organisations.models import AuditEvent, Organisation, OrganisationMembership, OrganisationProfile

# Registered for engineering/operational visibility only (superuser-gated).
# This is not the product UI - see PID.md §8 "Do not expose Django Admin
# as product UI".
admin.site.register(Organisation)
admin.site.register(OrganisationMembership)
admin.site.register(OrganisationProfile)
admin.site.register(AuditEvent)
