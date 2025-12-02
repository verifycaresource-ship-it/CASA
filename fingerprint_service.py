import requests
import base64
from .models import Client
from django.conf import settings
from cryptography.fernet import Fernet

FINGERPRINT_SERVICE_URL = getattr(settings, "FINGERPRINT_SERVICE_URL", "http://127.0.0.1:5000/enroll")
FINGERPRINT_ENCRYPTION_KEY = getattr(settings, "FINGERPRINT_ENCRYPTION_KEY", Fernet.generate_key())
fernet = Fernet(FINGERPRINT_ENCRYPTION_KEY)

def capture_fingerprint_from_service(timeout=30) -> bytes | None:
    """Call external fingerprint service; returns raw bytes or None."""
    try:
        resp = requests.get(FINGERPRINT_SERVICE_URL, timeout=timeout)
        resp.raise_for_status()
        data = resp.json()
        if data.get("success") and data.get("template"):
            return base64.b64decode(data["template"])
    except Exception as e:
        print("Fingerprint capture error:", e)
    return None

def find_matching_client(template_bytes: bytes, sdk_match_func) -> "Client | None":
    """Iterate over all active clients and find the first match using SDK."""
    for client in Client.objects.filter(is_active=True):
        if client.fingerprint_data and sdk_match_func(fernet.decrypt(client.fingerprint_data), template_bytes):
            return client
    return None
