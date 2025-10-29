from flask import Flask, jsonify
import base64
import subprocess

app = Flask(__name__)

# ---------- Helper Functions ----------
def enroll_fingerprint_system(finger="right-index-finger"):
    """
    Call system fprintd to enroll a fingerprint.
    Returns Base64-encoded template or raises Exception.
    """
    try:
        # Call fprintd-enroll to capture fingerprint
        result = subprocess.run(
            ["fprintd-enroll", "--finger", finger],
            capture_output=True, text=True, timeout=30
        )
        if result.returncode != 0:
            raise Exception(result.stderr or result.stdout)

        # Simulate capturing template (replace with real binary if possible)
        # In a real system, you could read template from fprintd
        template_bytes = b"RealFingerprintTemplateBytes"  
        fingerprint_base64 = base64.b64encode(template_bytes).decode("utf-8")
        return fingerprint_base64

    except subprocess.TimeoutExpired:
        raise Exception("Fingerprint capture timed out. Try again.")
    except Exception as e:
        raise e

# ---------- Flask Routes ----------
@app.route("/enroll", methods=["GET"])
def enroll():
    try:
        fingerprint_base64 = enroll_fingerprint_system()
        return jsonify({
            "success": True,
            "message": "Fingerprint enrolled successfully.",
            "fingerprint": fingerprint_base64
        })
    except Exception as e:
        return jsonify({
            "success": False,
            "message": str(e)
        }), 500

@app.route("/verify", methods=["GET"])
def verify():
    try:
        # Call system fprintd-verify
        result = subprocess.run(
            ["fprintd-verify"],
            capture_output=True, text=True, timeout=30
        )
        success = "verify-result: verify-match" in result.stdout.lower()
        return jsonify({"success": success, "message": result.stdout})
    except subprocess.TimeoutExpired:
        return jsonify({"success": False, "message": "Verification timed out."}), 500
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500


if __name__ == "__main__":
    print("🔹 Starting Fingerprint Service on http://127.0.0.1:5000 ...")
    app.run(host="127.0.0.1", port=5000)