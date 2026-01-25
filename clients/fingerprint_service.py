import sys
import base64

# -----------------------------
# CROSS-PLATFORM FINGERPRINT SERVICE
# -----------------------------

if sys.platform.startswith("win"):
    try:
        # Windows: import Digital Persona SDK
        import dp_sdk  # Make sure you installed dp_sdk on Windows
    except ImportError:
        raise ImportError(
            "Digital Persona SDK not found. Install dp_sdk on Windows to enable fingerprint capture."
        )

# -----------------------------
# ENROLL CLIENT FROM BASE64
# -----------------------------
def enroll_client_from_base64(client, template_base64: str):
    """
    Save fingerprint template from Base64 to client object.
    """
    template_bytes = base64.b64decode(template_base64)
    client.fingerprint_template = template_bytes  # binary field in model


# -----------------------------
# VERIFY CLIENT FROM BASE64
# -----------------------------
def verify_client_from_base64(client, template_base64: str) -> bool:
    """
    Verify fingerprint against stored template.
    Returns True if match, False otherwise.
    """
    if not client.fingerprint_template:
        return False
    template_bytes = base64.b64decode(template_base64)
    # For demo, do a simple byte comparison
    return client.fingerprint_template == template_bytes


# -----------------------------
# CAPTURE FINGERPRINT (AJAX)
# -----------------------------
def capture_fingerprint() -> bytes:
    """
    Capture fingerprint from scanner and return raw bytes.
    - On Windows: uses Digital Persona SDK
    - On Linux: simulated dummy data
    """
    if sys.platform.startswith("win"):
        try:
            reader = dp_sdk.Reader()  # Example, adjust per SDK docs
            template_bytes = reader.capture_fingerprint()
            if not template_bytes:
                raise Exception("No fingerprint captured")
            return template_bytes
        except Exception as e:
            raise Exception(f"Windows SDK error: {e}")
    else:
        # Linux fallback / simulation
        import os
        dummy_template = os.urandom(512)  # 512-byte fake template
        return dummy_template

