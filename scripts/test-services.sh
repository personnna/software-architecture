#!/bin/bash
# Test all microservices health
# Author: Shattyk Kuziyeva

set -e
PASS=0
FAIL=0

check() {
  if curl -sf $1/healthz > /dev/null; then
    echo "OK: $1"
    PASS=$((PASS+1))
  else
    echo "FAIL: $1"
    FAIL=$((FAIL+1))
  fi
}

check http://localhost:8003
check http://localhost:8001

echo "Results: $PASS passed, $FAIL failed"
