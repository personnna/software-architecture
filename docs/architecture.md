# Architecture

## System Type
Microservices architecture

## Components

Client → API Gateway → Services

- Auth Service (login, JWT)
- User Service (profiles)
- Tournament Service (matches)
- Notification Service (emails)

## Principle
Each service is independent and communicates via REST APIs.