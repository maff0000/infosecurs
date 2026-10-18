from django.urls import path

from security_tasks import views

app_name = "security_tasks"

urlpatterns = [
    path("", views.task_list, name="list"),
    path("create/", views.task_create, name="create"),
    path("<uuid:task_id>/", views.task_detail, name="detail"),
    path("<uuid:task_id>/transition/", views.task_transition, name="transition"),
    path("<uuid:task_id>/assign/", views.task_assign, name="assign"),
    path("<uuid:task_id>/dependencies/", views.task_link_dependency, name="link_dependency"),
]
