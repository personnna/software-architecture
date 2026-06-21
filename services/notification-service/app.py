import os

from flask import Flask, jsonify


app = Flask(__name__)


@app.route("/healthz")
def healthz():
    return jsonify({"status": "ok", "service": "notification-service"}), 200


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8004))
    app.run(host="0.0.0.0", port=port)
