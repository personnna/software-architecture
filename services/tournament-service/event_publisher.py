import json
import logging
import os
import time
import uuid
from datetime import datetime, timezone

import pika


LOGGER = logging.getLogger(__name__)
RABBITMQ_URL = os.environ.get("RABBITMQ_URL", "amqp://gym:gym@rabbitmq:5672/%2F")
EVENT_EXCHANGE = os.environ.get("EVENT_EXCHANGE", "gym.events")
SOURCE_SERVICE = "tournament-service"


def build_event(event_type, payload, correlation_id=None):
    return {
        "event_id": str(uuid.uuid4()),
        "event_type": event_type,
        "occurred_at": datetime.now(timezone.utc).isoformat(),
        "source_service": SOURCE_SERVICE,
        "correlation_id": correlation_id,
        "payload": payload,
    }


def publish_event(event_type, payload, correlation_id=None, retries=3, delay_seconds=0.25):
    """
    Publish a durable RabbitMQ event.

    Returns False instead of raising after retry exhaustion so user-facing
    tournament operations do not fail when the broker is temporarily down.
    """
    event = build_event(event_type, payload, correlation_id)
    body = json.dumps(event, sort_keys=True).encode("utf-8")
    params = pika.URLParameters(RABBITMQ_URL)

    for attempt in range(1, retries + 1):
        try:
            connection = pika.BlockingConnection(params)
            channel = connection.channel()
            channel.exchange_declare(
                exchange=EVENT_EXCHANGE,
                exchange_type="topic",
                durable=True,
            )
            channel.basic_publish(
                exchange=EVENT_EXCHANGE,
                routing_key=event_type,
                body=body,
                properties=pika.BasicProperties(
                    content_type="application/json",
                    delivery_mode=pika.DeliveryMode.Persistent,
                ),
            )
            connection.close()
            return True
        except Exception as exc:
            LOGGER.warning(
                "RabbitMQ publish failed for %s on attempt %s/%s: %s",
                event_type,
                attempt,
                retries,
                exc,
            )
            if attempt < retries:
                time.sleep(delay_seconds)

    return False
