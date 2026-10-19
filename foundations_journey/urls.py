from django.urls import path

from foundations_journey import views

app_name = "foundations_journey"

urlpatterns = [
    path("questions/<str:question_key>/", views.guided_question, name="guided_question"),
    path(
        "questions/<str:question_key>/offer-task/",
        views.offer_followup_task,
        name="offer_followup_task",
    ),
    path("pause/", views.pause_journey, name="pause"),
    path("resume/", views.resume_journey, name="resume"),
]
