from django.urls import path

from questionnaire import views

app_name = "questionnaire"

urlpatterns = [
    path("", views.questionnaire_list, name="list"),
    path("analyse/", views.questionnaire_analyse, name="analyse"),
    path("responses/<uuid:response_id>/", views.questionnaire_response_detail, name="response_detail"),
    path("responses/<uuid:response_id>/accept/", views.questionnaire_response_accept, name="response_accept"),
    path("responses/<uuid:response_id>/edit/", views.questionnaire_response_edit, name="response_edit"),
    path(
        "responses/<uuid:response_id>/regenerate/",
        views.questionnaire_response_regenerate,
        name="response_regenerate",
    ),
    # M009A (WO-M009A-SECURE-INGESTION-XLSX.md) - secure questionnaire
    # artifact ingestion. Deliberately under its own "imports/" prefix,
    # never colliding with the "responses/<uuid>/" routes above - a
    # distinct conceptual domain (Correction 1).
    path("imports/upload/", views.questionnaire_import_upload, name="import_upload"),
    path("imports/<uuid:import_id>/", views.questionnaire_import_detail, name="import_detail"),
    path(
        "imports/<uuid:import_id>/retry/",
        views.questionnaire_import_retry,
        name="import_retry",
    ),
]
