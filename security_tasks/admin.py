from django.contrib import admin

from security_tasks.models import SecurityTask, SecurityTaskDependency, SecurityTaskEvent

# Registered for engineering/operational visibility only (superuser-gated).
# Not the product UI - see security_tasks/views.py.
admin.site.register(SecurityTask)
admin.site.register(SecurityTaskDependency)
admin.site.register(SecurityTaskEvent)
