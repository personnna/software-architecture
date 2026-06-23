# GYM IT System — Project Overview, Responsibilities, and Commit Plan

## Project Summary

GYM IT System is a microservices-based gym management project. The system is
designed to separate authentication, user/profile logic, tournament workflows,
leaderboards, reporting, notifications, and deployment infrastructure into clear
ownership areas.

The current repository demonstrates:

- microservices architecture;
- database-per-service pattern;
- JWT authentication and role-based access control;
- tournament creation, bracket generation, match scheduling, and scoring;
- RabbitMQ-based asynchronous events;
- notification/event consumer service;
- Docker Compose local orchestration;
- Kubernetes deployment manifests;
- CI workflow and service-level tests;
- architecture and API documentation.

## Current Implementation Status

The active implementation branch is:

```text
codex/rabbitmq-microservice-integration
```

The changes have not been pushed to GitHub yet. They exist locally as a
reconstructed 25-commit development history for the work period
June 18-23, 2026.

## Implemented Services and Infrastructure

| Component | Port | Responsibility | Current Status |
|---|---:|---|---|
| API Gateway | 8000 | Routes frontend/API requests to backend services | Implemented as a minimal Flask gateway |
| Auth Service | 8001 | Registration, login, JWT, RBAC, encrypted profile data, user stats | Implemented |
| Tournament Service | 8003 | Tournaments, participants, brackets, match scheduling, scoring | Implemented |
| Notification Service | 8004 | Consumes RabbitMQ events for reporting/notification projection | Implemented as event consumer skeleton |
| RabbitMQ | 5672 / 15672 | Durable asynchronous event broker | Implemented |
| Auth DB | internal | PostgreSQL database for auth/profile data | Implemented via Docker Compose |
| Tournament DB | internal | PostgreSQL database for tournament data | Implemented via Docker Compose |
| Kubernetes Manifests | — | Deployment, service, scaling, broker configuration | Implemented for core services |
| CI Workflow | — | Service tests and Docker build checks | Updated |

## Architecture Overview

```text
Client / Frontend
      |
      v
API Gateway
      |
      |-----------------> Auth Service -----------> Auth DB
      |
      |-----------------> Tournament Service -----> Tournament DB
                              |
                              v
                           RabbitMQ
                              |
                              v
                       Notification Service
```

## Communication Patterns

### Synchronous REST

REST is used for direct request/response operations:

- frontend to API Gateway;
- API Gateway to Auth Service;
- API Gateway to Tournament Service;
- Tournament Service to Auth Service for internal user tournament stats updates.

### Asynchronous RabbitMQ Events

RabbitMQ is the primary asynchronous event broker. Tournament Service publishes
domain events only after successful database commits.

Implemented events:

- `tournament.created`
- `tournament.participant_added`
- `tournament.bracket_generated`
- `tournament.match_scheduled`
- `tournament.match_result_recorded`
- `tournament.completed`

Notification Service consumes these events from the durable
`notification.events` queue.

## Team Responsibilities

| Team Member | Core Domain | Architectural Responsibility |
|---|---|---|
| Yeldana Kadenova | Challenges & Leaderboards: real-time rankings, point calculation | Simplicity & UI Architecture: shared UI components, UX standards, frontend routing |
| Daniil Glazunov - 912512 | User Management: auth, profiles, roles, staff management | Security: JWT implementation, AES-256 encryption, RBAC middleware |
| Shattyk Kuziyeva | Tournament Engine: brackets, match scheduling, scoring logic | Scalability & DevOps: Dockerization, Kubernetes configuration, CI pipelines |
| Mirgali | Reporting & Notifications: dashboards, email/push-style notifications, logs | Fault Tolerance & Data: backup scripts, load testing, database reliability |

## Mirgali's Additional Contribution

In addition to the Reporting & Notifications and Fault Tolerance & Data role,
Mirgali also contributed to infrastructure and service integration work in this
branch.

Mirgali's extended contribution includes:

- adding RabbitMQ as the main asynchronous broker;
- wiring RabbitMQ into Docker Compose;
- creating the minimal API Gateway service;
- adding Notification Service as a RabbitMQ consumer;
- adding service-to-service integration around tournament events;
- adding tournament event publishing;
- updating user tournament stats through Auth Service;
- extending Kubernetes manifests for RabbitMQ and Notification Service;
- improving DevOps documentation and local verification steps;
- updating CI to test services separately;
- adding tests for RabbitMQ publisher and notification consumer logic;
- documenting the RabbitMQ event contract.

## Changes Introduced in This Branch

### 1. Docker Compose and Local Infrastructure

The main `docker-compose.yml` was expanded from a tournament-only setup into a
multi-service local environment.

Added or integrated:

- API Gateway;
- Auth Service;
- Tournament Service;
- Notification Service;
- RabbitMQ;
- Auth PostgreSQL database;
- Tournament PostgreSQL database;
- shared environment variables such as `RABBITMQ_URL`, `JWT_SECRET`, and
  `SERVICE_TOKEN`.

### 2. API Gateway

A minimal Flask API Gateway was added to route requests:

- `/api/auth/*` to Auth Service;
- `/api/tournaments/*` to Tournament Service;
- `/healthz` for gateway health checks;
- static frontend files through the gateway.

The gateway intentionally does not contain business logic.

### 3. Tournament Service Updates

Tournament Service was extended with:

- JWT verification;
- RBAC protection for trainer/admin write endpoints;
- RabbitMQ event publisher helper;
- tournament lifecycle events;
- match scheduled/result/completed events;
- best-effort event publishing with retry and logging;
- user stats update calls to Auth Service after match results.

### 4. Notification Service

A new Notification Service skeleton was added.

It currently:

- exposes `/healthz`;
- connects to RabbitMQ;
- declares the durable `notification.events` queue;
- listens for `tournament.#`, `user.#`, and `notification.#` routing keys;
- processes events through a testable handler.

Future work can add real email, push, dashboard, or WebSocket delivery.

### 5. Auth/User Stats Integration

Auth Service was extended with tournament statistics fields and an internal
service-token endpoint:

- tournaments played;
- wins;
- losses;
- points;
- championships.

Tournament Service updates these stats after match results.

### 6. Kubernetes and DevOps

Kubernetes support was expanded with:

- RabbitMQ deployment and service;
- Notification Service deployment and service;
- RabbitMQ-related environment variables in Auth and Tournament manifests;
- service token wiring;
- updated DevOps documentation.

### 7. Tests and CI

Added or updated tests for:

- tournament RBAC permissions;
- RabbitMQ event envelope generation;
- graceful publisher failure when RabbitMQ is unavailable;
- notification event handler behavior.

CI was updated to run service tests separately with correct service-level
working directories.

## 25-Commit Split

The work was split into 25 logical commits as follows:

| # | Commit Message | Purpose |
|---:|---|---|
| 1 | `docs: audit current implemented services and missing scope` | Documented current state and missing integration work |
| 2 | `chore(compose): merge auth service into main compose` | Added Auth Service and auth DB to main Compose |
| 3 | `chore(compose): add RabbitMQ broker` | Added RabbitMQ with management UI |
| 4 | `chore(config): add broker env configuration` | Added shared broker/service config |
| 5 | `feat(gateway): add minimal API gateway service` | Added Flask gateway and routing |
| 6 | `fix(frontend): align auth routes with gateway routing` | Updated frontend token/gateway behavior |
| 7 | `feat(tournament): add JWT verification helper` | Added JWT validation in Tournament Service |
| 8 | `feat(tournament): protect trainer/admin write endpoints` | Added RBAC to tournament write endpoints |
| 9 | `feat(tournament): add RabbitMQ publisher helper` | Added durable event publisher |
| 10 | `feat(tournament): publish tournament created event` | Published tournament creation event |
| 11 | `feat(tournament): publish participant event` | Published participant event |
| 12 | `feat(tournament): publish bracket generated event` | Published bracket generated event |
| 13 | `feat(tournament): publish match scheduled event` | Published match scheduled event |
| 14 | `feat(tournament): publish match result event` | Published match result event |
| 15 | `feat(tournament): publish tournament completed event` | Published tournament completion event |
| 16 | `feat(notification): add notification service skeleton` | Added Notification Service base |
| 17 | `feat(notification): consume RabbitMQ domain events` | Added RabbitMQ consumer |
| 18 | `feat(stats): add user tournament stats model or endpoint` | Added stats fields and internal endpoint |
| 19 | `feat(stats): update stats from match results` | Updated stats after tournament results |
| 20 | `test(tournament): cover RBAC permissions` | Added RBAC tests |
| 21 | `test(events): cover publisher with mocks` | Added RabbitMQ publisher tests |
| 22 | `test(notification): cover event consumer handler` | Added notification handler tests |
| 23 | `chore(k8s): add RabbitMQ deployment manifests` | Added RabbitMQ and Notification K8s manifests |
| 24 | `docs: update architecture for RabbitMQ event flow` | Updated architecture and event docs |
| 25 | `docs: update README and verification steps` | Updated README, DevOps, CI, and final verification docs |

## Reconstructed Commit Timeline

The commits were organized as a reconstructed local development history from
June 18 to June 23, 2026:

- June 18: project audit, Docker Compose, RabbitMQ, API Gateway;
- June 19: frontend routing, JWT/RBAC, RabbitMQ publisher setup;
- June 20: tournament lifecycle events;
- June 21: Notification Service, stats integration, RBAC tests;
- June 22: event tests, notification tests, Kubernetes, architecture docs;
- June 23: README, DevOps docs, CI updates, verification notes.

## Verification Status

Local checks completed:

- `docker compose config` passed;
- Auth Service tests: 13 passed;
- Tournament Service tests: 19 passed;
- Notification Service tests: 2 passed.

Docker image build was not verified locally because the Docker daemon was not
running on the machine at verification time.

## Known Limitations and Future Work

- Notification Service currently consumes events and exposes a health check;
  real email, push, dashboard widgets, or WebSocket delivery can be added later.
- User Service is not a separate microservice yet; tournament stats are stored
  through Auth Service for this project stage.
- RabbitMQ publishing is best-effort with retry/logging; a full outbox pattern
  is intentionally not implemented.
- Production observability such as Prometheus, Grafana, central logging, and
  tracing remains future work.
- Docker build should be verified once Docker daemon is running.

## Ownership Summary

Yeldana is responsible for challenges, leaderboards, and UI simplicity.
Daniil Glazunov - 912512 is responsible for user management and security.
Shattyk is responsible for tournament engine work and the main
scalability/devops direction. Mirgali is responsible for reporting,
notifications, fault tolerance, data reliability, and also contributed
additional infrastructure, RabbitMQ, service integration, and DevOps
improvements in this branch.
