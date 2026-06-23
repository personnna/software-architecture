// Load Testing Script - Tournament Service
// Author: Shattyk Kuziyeva
// Simulates 1000 concurrent users
// Scalability & DevOps responsibility

import http from "k6/http";
import { check, sleep } from "k6";

export let options = {
  stages: [
    { duration: "30s", target: 100 },
    { duration: "1m", target: 500 },
    { duration: "2m", target: 1000 },
    { duration: "30s", target: 0 },
  ],
  thresholds: {
    http_req_duration: ["p(95)<2000"],
    http_req_failed: ["rate<0.01"],
  },
};

const BASE_URL = "http://localhost:8003";

export default function () {
  let res = http.get(`${BASE_URL}/healthz`);
  check(res, {
    "healthz status 200": (r) => r.status === 200,
  });

  let list = http.get(`${BASE_URL}/tournaments`);
  check(list, {
    "tournaments list OK": (r) => r.status === 200 || r.status === 401,
  });

  sleep(1);
}
