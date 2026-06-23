# DevOps & Scalability Documentation
**Author: Kuziyeva**
**Role: Scalability & DevOps**

## Overview
This document describes the DevOps infrastructure, deployment strategy, and scalability design for the GYM IT System.

## Scripts

| Script | Purpose |
|--------|---------|
| `scripts/start-services.sh` | Start all microservices via Docker Compose |
| `scripts/stop-services.sh` | Gracefully stop all services |
| `scripts/test-services.sh` | Health check all running services |
| `scripts/backup-db.sh` | Automated PostgreSQL backup (RTO < 5 min) |

## Kubernetes Scalability

The tournament service is configured with a Horizontal Pod Autoscaler (HPA):
- Minimum replicas: 2
- Maximum replicas: 10
- Scales up when CPU > 70% or Memory > 80%
- Designed to handle 5x traffic growth

## Load Testing

Load tests are defined in `load-test/k6-load-test.js` using k6.

Simulates 1000 concurrent users across 4 stages:
- Stage 1: Ramp up to 100 users (30s)
- Stage 2: Ramp up to 500 users (1m)
- Stage 3: Peak 1000 users (2m)
- Stage 4: Ramp down (30s)

Performance thresholds:
- 95th percentile response time < 2000ms
- Error rate < 1%

## CI/CD Pipeline

Defined in `.github/workflows/devops-ci.yml`:
- Validates all scripts exist
- Validates Kubernetes manifests
- Builds Docker image
- Runs health check

## Fault Tolerance


- Automated daily DB backups via `scripts/backup-db.sh`
- Keeps last 7 backups
- Recovery Time Objective (RTO) < 5 minutes
- PostgreSQL data persisted via Docker volumes

This document describes the containerization, orchestration, and CI/CD setup

for the GYM IT System. The goal is to ensure the system can scale reliably

and deploy consistently across environments.



\---



\## 2. Docker Setup



\### Why Docker?

Docker ensures every service runs identically on any machine — no more

"it works on my computer" problems.



\### How to Run Locally

```bash

docker-compose up --build

```

This starts all services together. Each service has its own database.



\### Root Dockerfile

The root `Dockerfile` builds the API Gateway image:

\- Base: Python 3.11 slim (small and fast)

\- Health check: pings `/healthz` every 30 seconds

\- Workers: 4 Gunicorn workers for handling concurrent requests



\---



\## 3. Kubernetes Setup



Kubernetes manages the deployed containers in production.



\### Files Created



| File | Purpose |

|---|---|

| `k8s/namespace.yaml` | Isolates all gym resources under `gym-system` |

| `k8s/api-gateway.yaml` | Deploys API Gateway with 3 replicas + LoadBalancer |

| `k8s/auth-service.yaml` | Auth service deployment |

| `k8s/tournament-service.yaml` | Tournament service deployment |

| `k8s/notification-service.yaml` | Notification event consumer deployment |

| `k8s/rabbitmq.yaml` | RabbitMQ broker deployment and ClusterIP service |

| `k8s/tournament-service-ingress.yaml` | External routing for tournament service |



\### How to Deploy to Kubernetes

```bash

kubectl apply -f k8s/namespace.yaml

kubectl apply -f k8s/api-gateway.yaml

kubectl apply -f k8s/auth-service.yaml

kubectl apply -f k8s/rabbitmq.yaml

kubectl apply -f k8s/tournament-service.yaml

kubectl apply -f k8s/notification-service.yaml

```



\### Scalability Design

The API Gateway runs \*\*3 replicas\*\* by default. This means:

\- If one instance crashes, 2 others keep serving requests

\- Traffic is automatically load balanced across all 3

\- Replicas can be increased with one command:



```bash

kubectl scale deployment api-gateway --replicas=5 -n gym-system

```



\---



\## 4. CI/CD Pipeline (GitHub Actions)



\### Files Created

\- `.github/workflows/main-ci.yml` — runs on every push to main



\### What the Pipeline Does

Every time code is pushed to `main` or a pull request is opened:



1\. \*\*Lint\*\* — checks for Python syntax errors (flake8)

2\. \*\*Test\*\* — runs all unit tests (pytest)

3\. \*\*Docker Build\*\* — verifies the Docker image builds without errors



This means broken code is caught automatically before it reaches production.



\---



\## 5. Health Checks



Every service exposes a `/healthz` endpoint. Both Docker and Kubernetes

use this to know if a service is alive:



\- If `/healthz` fails → container is restarted automatically

\- This is called \*\*self-healing\*\* and is a key fault-tolerance feature



\---

\## 6. RabbitMQ Event Broker



RabbitMQ is the primary asynchronous integration technology in this version.

Tournament Service publishes lifecycle events to the durable `gym.events`

topic exchange, and Notification Service consumes from `notification.events`.



RabbitMQ keeps notification/profile projections decoupled from the core

tournament write path. If the broker is temporarily unavailable, tournament

API requests complete and the publisher logs the failure after retry attempts.



\---



\## 7. Summary of My Contributions



| Item | File | Description |

|---|---|---|

| Dockerfile | `Dockerfile` | Containerizes the API Gateway |

| Kubernetes Namespace | `k8s/namespace.yaml` | Isolates system resources |

| Kubernetes API Gateway | `k8s/api-gateway.yaml` | 3-replica scalable deployment |

| RabbitMQ | `k8s/rabbitmq.yaml` | Durable event broker for domain events |

| Notification Service | `services/notification-service` | Event consumer for tournament notifications |

| CI Pipeline | `.github/workflows/main-ci.yml` | Automated testing and builds |

| This document | `docs/devops/DEVOPS.md` | DevOps documentation |
