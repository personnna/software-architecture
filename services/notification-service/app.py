import os

from flask import Flask, jsonify

from event_consumer import consumer_state, start_consumer_thread


app = Flask(__name__)
if os.environ.get("ENABLE_RABBITMQ_CONSUMER", "1") == "1":
    start_consumer_thread()


@app.route("/healthz")
def healthz():
    return jsonify({
        "status": "ok",
        "service": "notification-service",
        "broker_connected": consumer_state["connected"],
        "last_event_type": consumer_state["last_event_type"],
        "last_error": consumer_state["last_error"],
    }), 200


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8004))
    app.run(host="0.0.0.0", port=port)
