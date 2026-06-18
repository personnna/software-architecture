# Implementation Scope — RabbitMQ Microservice Integration

This note captures the repository state before the RabbitMQ integration work.
It is part of a reconstructed local development history for the Danial role:
Tournament Engine plus Scalability/DevOps.

## Implemented Today

- `auth-service`: JWT login/register, RBAC roles, AES-encrypted phone field,
  admin user management, PostgreSQL storage, Docker/Kubernetes docs.
- `tournament-service`: tournament creation, participant registration, bracket
  generation, match scheduling/scoring, PostgreSQL storage, tests, Kubernetes
  deployment.
- Architecture and OpenAPI documentation for auth and tournament services.

## Missing Integration Pieces

- No executable API Gateway service exists yet, although Kubernetes manifests
  reference one.
- `docker-compose.yml` runs only the tournament service and database.
- No RabbitMQ event broker is present.
- No notification service consumes tournament events.
- Tournament write endpoints do not yet enforce JWT/RBAC.
- Tournament match results are not reflected in user profile/statistics data.

## Danial Scope

This work stays inside the Tournament Engine and Scalability/DevOps boundary:

- add RabbitMQ as the durable event bus;
- publish tournament lifecycle events after successful commits;
- add a minimal gateway and notification consumer to prove integration;
- update Docker Compose, Kubernetes, CI, tests, and architecture docs.
