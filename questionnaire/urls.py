from django.urls import path

from questionnaire import views

app_name = "questionnaire"

urlpatterns = [
    path("", views.questionnaire_list, name="list"),
    path("analyse/", views.questionnaire_analyse, name="analyse"),
    path("responses/<uuid:response_id>/", views.questionnaire_response_detail, name="response_detail"),
]
