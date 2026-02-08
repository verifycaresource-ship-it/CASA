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
    verify_client,
    verify_qr_api,
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

    # Fingerprint AJAX Capture
    path("capture_fingerprint/", capture_fingerprint, name="capture_fingerprint"),

    # QR Code (image generator for agents)
    path("qr/generate/<int:client_id>/", generate_qr, name="generate_qr"),

    # Hospital verification page (QR points here)
    path("verify/<str:token>/", verify_client, name="verify_client"),

    # Optional API for mobile scanners / hardware
    path("qr/verify/", verify_qr_api, name="verify_qr_api"),

    # DRF API Endpoints
    path("api/", include(router.urls)),
    path("verify/<uuid:token>/", verify_client, name="verify_client"),

]
