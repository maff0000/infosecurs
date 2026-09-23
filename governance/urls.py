from django.urls import path

from governance import views

app_name = "governance"

# organisation_id is supplied by the outer include's path prefix (see
# every other per-organisation app in config/urls.py, e.g.
# "organisations/<uuid:organisation_id>/evidence/" -> evidence.urls),
# not repeated here - the PL wires this in centrally as
# "organisations/<uuid:organisation_id>/governance/" -> governance.urls.
urlpatterns = [
    path("roles/", views.role_assignments, name="roles"),
    path("my-details/", views.edit_my_details, name="edit_my_details"),
]
