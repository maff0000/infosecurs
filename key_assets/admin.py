from django.contrib import admin

from key_assets.models import KeyAsset

# Registered for engineering/operational visibility only (superuser-gated).
# This is not the product UI - see key_assets/views.py and PID.md M002 §7.
admin.site.register(KeyAsset)
