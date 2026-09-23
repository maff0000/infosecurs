from django.contrib import admin

from activity.models import ActivityEvent

# Registered for engineering/operational visibility only (superuser-gated),
# matching every other app's admin.py in this codebase. This is not the
# product UI - see activity/views.py for the read-only Activity page, and
# note PID §23: events are not editable from the product UI. Django admin's
# own generic edit/delete affordances are a superuser operational escape
# hatch, not a product code path, so registering here does not violate
# that rule.
admin.site.register(ActivityEvent)
