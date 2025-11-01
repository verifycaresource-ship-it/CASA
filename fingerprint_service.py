from flask import Flask, request, jsonify
import base64
import subprocess

app = Flask(__name__)

# -----------------------------
# Helper Functions
# -----------------------------
def capture_fingerprint():
    """
    Capture fingerprint using DigitalPersona SDK or fprintd.
    Returns base64 template.
    """
    try:
        # Replace below command with your DigitalPersona SDK CLI or method
        # Example for fprintd: ['fprintd-enroll', '--finger', 'right-index-finger']
        result = subprocess.run(
            ["fprintd-enroll", "--finger", "right-index-finger"],
            capture_output=True, text=True, timeout=30
        )
        if result.returncode != 0:
            raise Exception(result.stderr or result.stdout)

        # Simulate template (replace with real template extraction)
        template_bytes = b"DigitalPersonaTemplateBytes"
        template_base64 = base64.b64encode(template_bytes).decode("utf-8")
        return template_base64

    except subprocess.TimeoutExpired:
        raise Exception("Fingerprint capture timed out.")
    except Exception as e:
        raise e


def verify_fingerprint(template_base64):
    """
    Verify a fingerprint template against enrolled templates.
    """
    try:
        # In a real setup, send template to SDK for verification
        # Here we simulate by checking any template (replace with actual verification)
        template_bytes = base64.b64decode(template_base64)

        # Simulate success if template exists
        verified = bool(template_bytes)
        return verified

    except Exception as e:
        raise e


# -----------------------------
# Flask Routes
# -----------------------------
@app.route("/capture", methods=["GET"])
def capture():
    try:
        template_base64 = capture_fingerprint()
        return jsonify({
            "success": True,
            "template": template_base64,
            "message": "Fingerprint captured successfully."
        })
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500


@app.route("/verify", methods=["POST"])
def verify():
    try:
        data = request.json
        template_base64 = data.get("template")
        if not template_base64:
            return jsonify({"success": False, "message": "No template provided."}), 400

        verified = verify_fingerprint(template_base64)
        return jsonify({"success": verified})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500


if __name__ == "__main__":
    print("🔹 Starting Fingerprint Service on http://127.0.0.1:5000 ...")
    app.run(host="127.0.0.1", port=5000)
