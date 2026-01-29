from django.urls import path, include
from rest_framework import routers
from .views import (
    client_list,
    add_client,
    edit_client,
    client_detail,
    capture_fingerprint,
    ClientViewSet,
    generate_qr,
    verify_qr
)

app_name = "clients"

# -----------------------------
# DRF Router
# -----------------------------
router = routers.DefaultRouter()
router.register(r"api", ClientViewSet, basename="client-api")

# -----------------------------
# URL Patterns
# -----------------------------
urlpatterns = [
    # Web Views
    path("", client_list, name="client_list"),
    path("add/", add_client, name="add_client"),
    path("edit/<int:pk>/", edit_client, name="edit_client"),
    path("detail/<int:pk>/", client_detail, name="client_detail"),

    # Fingerprint AJAX Capture (used in client_form.html)
    path("capture_fingerprint/", capture_fingerprint, name="capture_fingerprint"),

    # QR Code Endpoints (only agents)
    path("qr/generate/<int:client_id>/", generate_qr, name="generate_qr"),
    path("qr/verify/", verify_qr, name="verify_qr"),

    # DRF API Endpoints
    path("api/", include(router.urls)),
]
