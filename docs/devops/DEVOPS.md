# DevOps & Scalability Documentation
**Author: Shattyk Kuziyeva**
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
