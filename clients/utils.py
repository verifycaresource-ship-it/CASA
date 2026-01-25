def enroll_client_from_base64(client, base64_data):
    """
    Enroll client fingerprint from a base64 string.
    Replace this with your actual fingerprint SDK logic.
    """
    # Example: store base64 in a field or integrate with your biometric device
    client.fingerprint_data = base64_data.encode('utf-8')  # temporary

def enroll_client_from_file(client, file):
    """
    Enroll client fingerprint from an uploaded file.
    Replace this with your actual fingerprint SDK logic.
    """
    # Example: read file and store as binary
    client.fingerprint_data = file.read()
