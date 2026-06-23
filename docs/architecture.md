# Architecture

## System Type
Microservices architecture with synchronous REST and asynchronous RabbitMQ events.

## Implemented Components

Client -> API Gateway -> Services

- Auth Service: registration, login, JWT, RBAC, encrypted profile field, user stats.
- Tournament Service: tournaments, participants, brackets, match scheduling, scoring.
- Notification Service: RabbitMQ event consumer and notification projection.
- RabbitMQ: durable topic exchange for domain events.

## Target Components

- User Service remains a future split from auth/profile concerns.
- Notification Service can later add WebSocket/email delivery on top of the event consumer.

## Communication

- REST is used for request/response operations through the API Gateway.
- RabbitMQ is used for durable asynchronous domain events.
- Tournament Service publishes events after successful database commits.
- Notification Service consumes events from a durable queue.
- Tournament Service updates auth-service profile stats through an internal service-token endpoint.

## Principle

Each service owns its data and exposes behavior through explicit contracts. RabbitMQ keeps tournament side effects decoupled from the core scoring path, so match recording still succeeds if notification delivery is temporarily unavailable.
