# RabbitMQ Domain Events

RabbitMQ is the primary asynchronous broker for the GYM IT System. Redis is not
used as the main pub/sub layer in this project version.

## Broker Contract

- Exchange: `gym.events`
- Exchange type: `topic`
- Notification queue: `notification.events`
- Queue durability: durable
- Message durability: persistent

## Event Envelope

```json
{
  "event_id": "uuid",
  "event_type": "tournament.created",
  "occurred_at": "2026-06-20T10:00:00+00:00",
  "source_service": "tournament-service",
  "correlation_id": null,
  "payload": {}
}
```

## Tournament Events

| Event | Producer | Purpose |
|---|---|---|
| `tournament.created` | Tournament Service | A trainer/admin created a tournament |
| `tournament.participant_added` | Tournament Service | A participant was added to a tournament |
| `tournament.bracket_generated` | Tournament Service | A single-elimination bracket was generated |
| `tournament.match_scheduled` | Tournament Service | A match received a scheduled datetime |
| `tournament.match_result_recorded` | Tournament Service | A final score was recorded |
| `tournament.completed` | Tournament Service | The final match ended and a champion exists |

## Reliability Notes

Tournament operations publish events after successful database commits. If
RabbitMQ is temporarily unavailable, the API logs the error and still returns the
user-facing result. This keeps core tournament scoring available while allowing
notifications to recover independently.
