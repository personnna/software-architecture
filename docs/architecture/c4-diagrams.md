# Architecture Diagrams (C4 Model)

This document describes the GYM IT System architecture at two C4 levels: **System Context** and **Container**.

> Current implementation includes the API Gateway, Auth Service, Tournament
> Service, Notification Service skeleton, and RabbitMQ event broker. A separate
> User Service remains a future extraction from auth/profile concerns.

---

## Level 1: System Context

```mermaid
C4Context
    title System Context - GYM IT System
    Person(member, "Gym Member", "Joins tournaments, checks brackets and results")
    Person(admin, "Admin / Trainer", "Creates tournaments, manages participants and scores")
    System(gym, "GYM IT System", "Manages tournaments, brackets, scoring, and notifications")
    System_Ext(email, "Email Provider", "Sends match/result notifications")
    Rel(member, gym, "Views tournaments and results", "HTTPS")
    Rel(admin, gym, "Creates tournaments, scores matches", "HTTPS")
    Rel(gym, email, "Sends notifications via", "SMTP/API")
```

---

## Level 2: Container Diagram

```mermaid
C4Container
    title Container Diagram - GYM IT System
    Person(user, "Member / Admin", "End user of the system")
    System_Boundary(gym, "GYM IT System") {
        Container(gateway, "API Gateway", "Flask", "Routes requests to backend services.")
        Container(tournament, "Tournament Service", "Flask, Python 3.11", "Tournaments, participants, brackets, scoring. IMPLEMENTED.")
        Container(auth, "Auth Service", "Flask, Python 3.11", "Login, JWT issuance, roles, profile stats. IMPLEMENTED.")
        Container(userSvc, "User Service", "Future service", "Profiles and staff management extraction. NOT YET IMPLEMENTED.")
        Container(notif, "Notification Service", "Flask, Python 3.11", "Consumes RabbitMQ events. IMPLEMENTED SKELETON.")
        ContainerQueue(rabbit, "RabbitMQ", "Topic exchange", "Durable domain events")
        ContainerDb(tournamentDb, "Tournament DB", "PostgreSQL 16", "Stores tournaments, participants, matches")
        ContainerDb(authDb, "Auth DB", "PostgreSQL 16", "Stores users, roles, credentials, tournament stats")
    }
    Rel(user, gateway, "HTTPS requests", "REST/JSON")
    Rel(gateway, tournament, "Routes tournament requests", "REST/JSON")
    Rel(gateway, auth, "Routes auth requests", "REST/JSON")
    Rel(gateway, userSvc, "Routes user requests", "REST/JSON")
    Rel(tournament, tournamentDb, "Reads/writes", "SQL")
    Rel(auth, authDb, "Reads/writes", "SQL")
    Rel(tournament, rabbit, "Publishes tournament events", "AMQP")
    Rel(rabbit, notif, "Delivers durable events", "AMQP")
    Rel(tournament, auth, "Updates profile stats", "REST/service token")
```

---

## Deployment View

```mermaid
flowchart TB
    subgraph current["Current Deployment - docker-compose.yml"]
        GW["api-gateway :8000"]
        AS["auth-service :8001"] --> ADB[("auth-db Postgres 16")]
        TS["tournament-service :8003"] --> TDB[("tournament-db Postgres 16")]
        NSVC["notification-service :8004"]
        MQ["rabbitmq :5672/:15672"]
        GW --> AS
        GW --> TS
        TS --> MQ
        MQ --> NSVC
    end
    subgraph k8s["Kubernetes Manifests - k8s/"]
        NS["Namespace: gym-system"]
        AG["api-gateway Deployment - 3 replicas + LoadBalancer"]
        TSK["tournament-service Deployment"]
        RAB["rabbitmq Deployment + ClusterIP"]
        NOTIF["notification-service Deployment"]
        NS --> AG
        NS --> TSK
        NS --> RAB
        NS --> NOTIF
    end
```

**Notes:**
- `api-gateway.yaml` defines a scalable Deployment (3 replicas) for the API Gateway.
- Replica count (3) was chosen as a representative scalable configuration rather than a literal "5x" multiplier.
