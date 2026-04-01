"""
IRIS Service Wrapper for VREDA Integration.

Wraps the IRIS Flask app with a /healthz endpoint and CORS support
so VREDA's Next.js frontend can proxy requests to it.
"""

import os
import sys
import time

# Ensure the iris src is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src", "retrieval_api"))

from app import app, socketio

# ── Health endpoint for VREDA service management ──
@app.route("/healthz")
def healthz():
    return {
        "status": "ok",
        "service": "iris-ideation",
        "runtime": {
            "pid": os.getpid(),
            "started_at_epoch_s": _start_time,
            "module_file": __file__,
            "health_protocol_version": 2,
        },
    }

# ── CORS headers for Next.js dev server ──
@app.after_request
def add_cors_headers(response):
    origin = os.environ.get("VREDA_ORIGIN", "http://localhost:3000")
    response.headers["Access-Control-Allow-Origin"] = origin
    response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    return response

_start_time = time.time()

if __name__ == "__main__":
    host = os.environ.get("HOST", "127.0.0.1")
    port = int(os.environ.get("PORT", "5001"))
    debug = os.environ.get("FLASK_DEBUG", "false").lower() == "true"

    print(f"[IRIS] Starting on {host}:{port}")
    socketio.run(app, host=host, port=port, debug=debug, allow_unsafe_werkzeug=True)
