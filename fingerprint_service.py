# fingerprint_service.py
from flask import Flask, Response
import base64, time, json

app = Flask(__name__)

with open("/mnt/data/fa2b31ff-0e42-489f-9fe3-0775f4cd29ae.png", "rb") as f:
    fingerprint_image_base64 = base64.b64encode(f.read()).decode("utf-8")

def capture_fingerprint_live():
    total_steps = 10
    for step in range(total_steps):
        progress = int((step + 1) / total_steps * 100)
        time.sleep(0.5)
        yield {"progress": progress, "status": "scanning"}

    template_bytes = b"DigitalPersonaTemplateBytes"
    template_base64 = base64.b64encode(template_bytes).decode("utf-8")

    yield {
        "progress": 100,
        "success": True,
        "template": template_base64,
        "image": fingerprint_image_base64,
        "status": "done"
    }

@app.route("/enroll", methods=["GET"])
def enroll():
    def event_stream():
        for step in capture_fingerprint_live():
            yield f"data: {json.dumps(step)}\n\n"
    return Response(event_stream(), mimetype="text/event-stream")

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, threaded=True)
