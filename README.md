# Software Architecture Project

## Overview

This repository demonstrates a microservices-based Gym IT System focused on
authentication, tournament management, and asynchronous RabbitMQ integration.

## Implemented Architecture

- API Gateway on port `8000`
- Auth Service on port `8001`
- Tournament Service on port `8003`
- Notification Service on port `8004`
- PostgreSQL database per implemented service
- RabbitMQ topic exchange for durable domain events

## Role Scope

Mirgali owns the Tournament Engine and Scalability/DevOps slice:

- tournament creation and bracket generation;
- match scheduling and scoring;
- tournament lifecycle events through RabbitMQ;
- Docker Compose and Kubernetes deployment support;
- event-driven integration with notifications and profile stats.

## Local Run

```bash
docker compose up --build
```

Open:

- App gateway: http://localhost:8000
- RabbitMQ management UI: http://localhost:15672

Development RabbitMQ credentials:

- Username: `gym`
- Password: `gym`

## Verification

```bash
curl http://localhost:8000/healthz
curl http://localhost:8001/healthz
curl http://localhost:8003/healthz
curl http://localhost:8004/healthz
```

Run service tests:

```bash
cd services/auth-service && python -m pytest -q
cd ../tournament-service && python -m pytest -q
cd ../notification-service && python -m pytest -q
```

## Event Flow

Tournament Service publishes RabbitMQ events after successful database commits:

- `tournament.created`
- `tournament.participant_added`
- `tournament.bracket_generated`
- `tournament.match_scheduled`
- `tournament.match_result_recorded`
- `tournament.completed`

Notification Service consumes those events from the durable
`notification.events` queue. See `docs/rabbitmq-events.md` for the contract.

## Notes

This branch contains a reconstructed local development history for the
June 18-23, 2026 work period. The commit dates group the logical
implementation steps for review.
