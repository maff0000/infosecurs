from django.contrib import admin

from workplace.models import Workplace

# Registered for engineering/operational visibility only (superuser-gated).
# This is not the product UI - see workplace/views.py and PID §9.
admin.site.register(Workplace)
