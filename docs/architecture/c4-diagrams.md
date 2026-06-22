# Architecture Diagrams (C4 Model)

This document describes the GYM IT System architecture at two C4 levels: **System Context** and **Container**.

> Note: only the **Tournament Service** is implemented today. The API Gateway, Auth Service, User Service, and Notification Service are part of the target architecture but are not yet built.

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
        Container(gateway, "API Gateway", "Flask planned", "Routes requests to backend services. NOT YET IMPLEMENTED.")
        Container(tournament, "Tournament Service", "Flask, Python 3.11", "Tournaments, participants, brackets, scoring. IMPLEMENTED.")
        Container(auth, "Auth Service", "Flask planned", "Login, JWT issuance, roles. NOT YET IMPLEMENTED.")
        Container(userSvc, "User Service", "Flask planned", "Profiles, staff management. NOT YET IMPLEMENTED.")
        Container(notif, "Notification Service", "Flask planned", "Email/push alerts. NOT YET IMPLEMENTED.")
        ContainerDb(tournamentDb, "Tournament DB", "PostgreSQL 16", "Stores tournaments, participants, matches")
        ContainerDb(authDb, "Auth DB", "PostgreSQL 16 planned", "Stores users, roles, credentials")
        Container(cache, "Redis Cache", "Redis", "Session/cache layer planned")
    }
    Rel(user, gateway, "HTTPS requests", "REST/JSON")
    Rel(gateway, tournament, "Routes tournament requests", "REST/JSON")
    Rel(gateway, auth, "Routes auth requests", "REST/JSON")
    Rel(gateway, userSvc, "Routes user requests", "REST/JSON")
    Rel(tournament, tournamentDb, "Reads/writes", "SQL")
    Rel(auth, authDb, "Reads/writes", "SQL")
    Rel(tournament, notif, "Triggers match notifications", "REST/JSON")
```

---

## Deployment View

```mermaid
flowchart TB
    subgraph current["Current Deployment - docker-compose.yml"]
        TS["tournament-service :8003"] --> TDB[("tournament-db Postgres 16")]
    end
    subgraph k8s["Kubernetes Manifests - k8s/"]
        NS["Namespace: gym-system"]
        AG["api-gateway Deployment - 3 replicas + LoadBalancer"]
        TSK["tournament-service Deployment"]
        ING["tournament-service Ingress"]
        NS --> AG
        NS --> TSK
        ING --> TSK
    end
```

**Notes:**
- `api-gateway.yaml` defines a scalable Deployment (3 replicas) for the API Gateway, ready for when that service is implemented. The Dockerfile in the repo root currently builds the Tournament Service image, since the Gateway code does not exist yet.
- Replica count (3) was chosen as a representative scalable configuration rather than a literal "5x" multiplier.
