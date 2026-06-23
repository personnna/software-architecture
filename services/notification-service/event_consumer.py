import json
import logging
import os
import threading
import time

import pika


LOGGER = logging.getLogger(__name__)
RABBITMQ_URL = os.environ.get("RABBITMQ_URL", "amqp://gym:gym@rabbitmq:5672/%2F")
EVENT_EXCHANGE = os.environ.get("EVENT_EXCHANGE", "gym.events")
QUEUE_NAME = os.environ.get("NOTIFICATION_QUEUE", "notification.events")
ROUTING_KEYS = ("tournament.#", "user.#", "notification.#")

consumer_state = {"connected": False, "last_event_type": None, "last_error": None}


def handle_event(event):
    """Pure handler used by tests and by the RabbitMQ callback."""
    event_type = event.get("event_type", "unknown")
    consumer_state["last_event_type"] = event_type
    LOGGER.info("notification event received: %s payload=%s", event_type, event.get("payload", {}))
    return {
        "event_type": event_type,
        "message": _message_for(event),
    }


def _message_for(event):
    event_type = event.get("event_type", "notification.created")
    payload = event.get("payload", {})
    if event_type == "tournament.created":
        return f"Tournament created: {payload.get('name')}"
    if event_type == "tournament.completed":
        return f"Tournament completed: {payload.get('name')}"
    if event_type == "tournament.match_result_recorded":
        return f"Match result recorded for tournament {payload.get('tournament_id')}"
    return event_type.replace(".", " ")


def _connect():
    connection = pika.BlockingConnection(pika.URLParameters(RABBITMQ_URL))
    channel = connection.channel()
    channel.exchange_declare(exchange=EVENT_EXCHANGE, exchange_type="topic", durable=True)
    channel.queue_declare(queue=QUEUE_NAME, durable=True)
    for key in ROUTING_KEYS:
        channel.queue_bind(exchange=EVENT_EXCHANGE, queue=QUEUE_NAME, routing_key=key)
    channel.basic_qos(prefetch_count=10)
    return connection, channel


def _consume_forever():
    while True:
        connection = None
        try:
            connection, channel = _connect()
            consumer_state.update({"connected": True, "last_error": None})

            def callback(ch, method, properties, body):
                try:
                    event = json.loads(body.decode("utf-8"))
                    handle_event(event)
                    ch.basic_ack(delivery_tag=method.delivery_tag)
                except Exception as exc:
                    consumer_state["last_error"] = str(exc)
                    LOGGER.exception("failed to process event")
                    ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)

            channel.basic_consume(queue=QUEUE_NAME, on_message_callback=callback)
            channel.start_consuming()
        except Exception as exc:
            consumer_state.update({"connected": False, "last_error": str(exc)})
            LOGGER.warning("RabbitMQ consumer disconnected: %s", exc)
            time.sleep(2)
        finally:
            try:
                if connection and connection.is_open:
                    connection.close()
            except Exception:
                pass


def start_consumer_thread():
    thread = threading.Thread(target=_consume_forever, name="rabbitmq-consumer", daemon=True)
    thread.start()
    return thread
