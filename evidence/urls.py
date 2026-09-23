from django.urls import path

from evidence import views

app_name = "evidence"

urlpatterns = [
    path("", views.evidence_list, name="list"),
    path("upload/", views.evidence_upload, name="upload"),
    path("add-reference/", views.evidence_add_reference, name="add_reference"),
    path("<uuid:evidence_id>/", views.evidence_detail, name="detail"),
    path("<uuid:evidence_id>/download/", views.evidence_download, name="download"),
    path("<uuid:evidence_id>/withdraw/", views.evidence_withdraw, name="withdraw"),
]
