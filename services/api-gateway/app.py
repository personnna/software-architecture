import os

import requests
from flask import Flask, Response, jsonify, redirect, request, send_from_directory
from flask_cors import CORS


app = Flask(__name__, static_folder="static", static_url_path="/static")
CORS(app)

SERVICE_ROUTES = {
    "/api/auth": os.environ.get("AUTH_SERVICE_URL", "http://auth-service:8001"),
    "/api/tournaments": os.environ.get(
        "TOURNAMENT_SERVICE_URL", "http://tournament-service:8003"
    ),
}


@app.route("/healthz")
def healthz():
    return jsonify({"status": "ok", "service": "api-gateway"}), 200


@app.route("/")
def index():
    return redirect("/static/tournament-setup.html")


@app.route("/static/<path:path>")
def static_files(path):
    return send_from_directory(app.static_folder, path)


def _target_for(path):
    for prefix, service_url in SERVICE_ROUTES.items():
        if path == prefix or path.startswith(prefix + "/"):
            downstream_path = path[len(prefix) :]
            if prefix == "/api/auth":
                downstream_prefix = ""
            else:
                downstream_prefix = "/tournaments"
            return service_url, downstream_prefix + (downstream_path or "")
    return None, None


@app.route("/api/<path:path>", methods=["GET", "POST", "PUT", "PATCH", "DELETE"])
@app.route("/api", methods=["GET", "POST", "PUT", "PATCH", "DELETE"])
def proxy(path=""):
    full_path = "/api" + (f"/{path}" if path else "")
    service_url, downstream_path = _target_for(full_path)
    if not service_url:
        return jsonify({"error": "service route not found"}), 404

    target_url = service_url.rstrip("/") + (downstream_path or "/")
    headers = {
        key: value
        for key, value in request.headers
        if key.lower() not in {"host", "content-length"}
    }

    try:
        upstream = requests.request(
            method=request.method,
            url=target_url,
            headers=headers,
            params=request.args,
            data=request.get_data(),
            cookies=request.cookies,
            timeout=15,
            allow_redirects=False,
        )
    except requests.RequestException as exc:
        return jsonify({"error": f"upstream service unavailable: {exc}"}), 503

    excluded = {"content-encoding", "content-length", "transfer-encoding", "connection"}
    response_headers = [
        (name, value)
        for name, value in upstream.headers.items()
        if name.lower() not in excluded
    ]
    return Response(upstream.content, upstream.status_code, response_headers)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    app.run(host="0.0.0.0", port=port)
