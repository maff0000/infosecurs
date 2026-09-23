from django.urls import path

from key_assets import views

app_name = "key_assets"

urlpatterns = [
    path("", views.key_asset_list, name="list"),
    path("new/", views.key_asset_create, name="create"),
    path("<uuid:asset_id>/edit/", views.key_asset_edit, name="edit"),
    path("<uuid:asset_id>/confirm/", views.key_asset_confirm, name="confirm"),
    path("<uuid:asset_id>/dismiss/", views.key_asset_dismiss, name="dismiss"),
]
