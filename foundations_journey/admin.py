from django.contrib import admin

from foundations_journey.models import JourneyCheckpoint, UserJourneyPreference


@admin.register(JourneyCheckpoint)
class JourneyCheckpointAdmin(admin.ModelAdmin):
    list_display = (
        "organisation",
        "user",
        "journey_code",
        "checkpoint_state",
        "current_question_key",
        "version",
        "last_interaction_at",
    )
    list_filter = ("journey_code", "checkpoint_state")
    search_fields = ("organisation__name", "user__username")


@admin.register(UserJourneyPreference)
class UserJourneyPreferenceAdmin(admin.ModelAdmin):
    list_display = ("user", "auto_open_enabled", "resume_modal_enabled", "updated_at")
    search_fields = ("user__username",)
