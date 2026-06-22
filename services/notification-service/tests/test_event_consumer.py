from event_consumer import handle_event


def test_handle_tournament_created_event():
    result = handle_event(
        {
            "event_type": "tournament.created",
            "payload": {"name": "Summer Cup"},
        }
    )

    assert result["event_type"] == "tournament.created"
    assert "Summer Cup" in result["message"]


def test_handle_unknown_event():
    result = handle_event({"event_type": "user.stats_updated", "payload": {}})

    assert result["event_type"] == "user.stats_updated"
    assert result["message"] == "user stats_updated"
