from django.urls import path, include
from rest_framework import routers
from . import views

app_name = "clients"

# DRF router
router = routers.DefaultRouter()
router.register(r"api", views.ClientViewSet, basename="client-api")

urlpatterns = [
    # Web views
    path("", views.client_list, name="client_list"),
    path("add/", views.add_client, name="add_client"),
    path("edit/<int:pk>/", views.edit_client, name="edit_client"),
    path("detail/<int:pk>/", views.client_detail, name="client_detail"),

    # Fingerprint AJAX
    path("capture_fingerprint/", views.capture_fingerprint, name="capture_fingerprint"),

    # DRF API
    path("api/", include(router.urls)),
]