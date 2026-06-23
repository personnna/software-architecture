from event_publisher import build_event, publish_event


def test_build_event_envelope():
    event = build_event("tournament.created", {"tournament_id": "t1"})
    assert event["event_id"]
    assert event["event_type"] == "tournament.created"
    assert event["source_service"] == "tournament-service"
    assert event["payload"]["tournament_id"] == "t1"
    assert event["occurred_at"]


def test_publish_event_returns_false_when_broker_unavailable(monkeypatch):
    def fail_connection(_params):
        raise RuntimeError("broker down")

    monkeypatch.setattr("event_publisher.pika.BlockingConnection", fail_connection)

    assert publish_event("tournament.created", {"id": 1}, retries=1) is False
