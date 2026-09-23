from django.contrib import admin

from evidence.models import EvidenceItem

# Registered for engineering/operational visibility only (superuser-gated).
# This is not the product UI - see evidence/views.py. Read-only by
# convention: EvidenceItem's file-content fields are immutable at the model
# layer (see EvidenceItem.save()), so no custom admin form is provided that
# would invite editing them.
admin.site.register(EvidenceItem)
