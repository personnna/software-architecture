\# DevOps \& Scalability Documentation



\*\*Author:\*\* Shattyk Kuziyeva  

\*\*Role:\*\* Scalability \& DevOps  

\*\*Course:\*\* Software Architectures (CM90)



\---



\## 1. Overview



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
