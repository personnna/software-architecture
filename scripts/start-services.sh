#!/bin/bash
# Start all microservices
# Author: Shattyk Kuziyeva

set -e

echo "Starting all services..."
docker compose up --build -d
sleep 10
echo "Checking tournament-service health..."
curl -f http://localhost:8003/healthz && echo "tournament-service OK"
curl -f http://localhost:8001/healthz && echo "auth-service OK"
echo "All services started."
