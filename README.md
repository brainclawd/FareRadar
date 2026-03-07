# FareRadar v1

A production-minded starter for a flight deal detection platform with:
- **Frontend:** Next.js 14 + TypeScript + Tailwind
- **Backend API:** FastAPI + SQLAlchemy + Pydantic
- **Worker:** Python scan worker for route-bucket polling, anomaly detection, and alert fan-out
- **Database:** Postgres
- **Cache/Queue:** Redis
- **Infra (local):** Docker Compose

## What's new in this build

This version moves beyond a simple feed and adds the core primitives needed for a real deal engine:

- route-bucket planning
- scan job creation
- candidate deal staging
- validated deal creation
- saved user alerts
- alert-match preview
- queue publisher scaffold
- architecture and API contract docs

## Core tables

- `users`
- `user_search_preferences`
- `user_alerts`
- `route_buckets`
- `scan_jobs`
- `flight_prices`
- `route_price_stats`
- `candidate_deals`
- `detected_deals`
- `deal_alerts`
- `notifications`


## Deployment-ready additions

This package now includes:

- `render.yaml` for Render web/worker/beat services
- `frontend/vercel.json` for Vercel frontend deploys
- `backend/Procfile` with production start commands
- `docs/DEPLOY.md` with a copy-paste deploy checklist
- CORS configuration via `CORS_ALLOWED_ORIGINS`
- production-focused `.env.example` entries

### Recommended first live stack

- Vercel for `frontend/`
- Render for `backend/`
- Supabase Postgres
- Upstash Redis

See `docs/DEPLOY.md` for the exact setup sequence.

## Quick start

```bash
cp .env.example .env
docker compose up --build
```

Services:
- Frontend: http://localhost:3000
- API docs: http://localhost:8000/docs

## Suggested v1 flow

1. `POST /users`
2. `POST /alerts`
3. `POST /scan/plan`
4. `POST /scan/jobs`
5. run worker or call `POST /scan/run`
6. `GET /deals`
7. `GET /deals/{id}/match-preview`

## Important API endpoints

### Provider status
```http
GET /providers
```

### Live provider search
```http
POST /search/flights?provider=amadeus
Content-Type: application/json

{
  "origin": "LAX",
  "destination": "NRT",
  "departure_date": "2026-05-10",
  "return_date": "2026-05-20",
  "adults": 1,
  "cabin_class": "economy",
  "currency_code": "USD",
  "max_results": 5,
  "non_stop": false
}
```

### Create a user alert
```http
POST /alerts
Content-Type: application/json

{
  "user_id": "00000000-0000-0000-0000-000000000000",
  "name": "Japan from West Coast",
  "origin_airports": ["SLC", "LAX", "LAS"],
  "destination_type": "city",
  "destinations": ["NRT", "HND"],
  "max_price": 650,
  "cabin_class": "economy",
  "date_flexibility": "plus_minus_7",
  "min_discount_percent": 35,
  "channels": ["email"]
}
```

### Build route buckets
```http
POST /scan/plan
Content-Type: application/json

{
  "origins": ["SLC", "LAX"],
  "destinations": ["NRT", "FCO", "BCN"],
  "cabins": ["economy", "business"],
  "departure_months": 3,
  "trip_length_min": 5,
  "trip_length_max": 10
}
```

### Enqueue scan jobs from the highest-priority buckets
```http
POST /scan/jobs?provider=mock&limit=25
```

### Trigger a synchronous scan and persist prices + detected deals
```http
POST /scan/run?provider=mock
Content-Type: application/json

{
  "origins": ["LAX", "SLC"],
  "destinations": ["NRT", "FCO"],
  "cabins": ["economy", "business"],
  "trip_length_min": 5,
  "trip_length_max": 10,
  "max_results": 3
}
```

### Inspect validated deals
```http
GET /deals
```

### Inspect candidate deals
```http
GET /deals/candidates
```

### Preview which alerts a deal would trigger
```http
GET /deals/1/match-preview
```

## Real provider setup

Set `FLIGHT_PROVIDER=amadeus`, `kiwi`, or `mock`.

### Amadeus
```bash
AMADEUS_CLIENT_ID=your_key
AMADEUS_CLIENT_SECRET=your_secret
AMADEUS_BASE_URL=https://test.api.amadeus.com
```

### Kiwi / Tequila
```bash
KIWI_API_KEY=your_api_key
KIWI_BASE_URL=https://tequila-api.kiwi.com
```

## Docs

- `docs/ARCHITECTURE.md`
- `docs/API_CONTRACTS.md`

## Suggested next steps

1. swap the queue stub for Celery/RQ/BullMQ workers
2. add auth and per-user rate limits
3. add region mapping, city metadata, and airport popularity tables
4. move `flight_prices` into partitions or ClickHouse once quote volume grows
5. add email/push delivery workers that consume `deal_alerts`


## Distributed workers added

This build now includes:
- Celery + Redis backed queues
- dedicated scanner / validator / alerts workers
- Celery Beat for recurring scan planning
- queued candidate validation
- logged email delivery scaffold

### New endpoints

```http
POST /scan/jobs/dispatch?limit=25
POST /candidates/{candidate_deal_id}/validate
```

### Worker startup

```bash
docker compose up --build
```

Worker containers:
- `scanner-worker`
- `validator-worker`
- `alerts-worker`
- `beat`


## Added in this build

This update adds the last three major backend pieces:
- provider hardening with retries, fallback order, cooldown tracking, and provider health event logging
- better feed quality with computed `feed_score` plus explainable quality factors
- admin / ops endpoints for provider health, scan jobs, and funnel metrics

### New admin endpoints

```http
GET /admin/overview
GET /admin/provider-health
GET /admin/scan-jobs
GET /admin/deals/funnel
```

### New deal sorting

```http
GET /deals?sort_by=feed_score
GET /deals?sort_by=deal_score
GET /deals?sort_by=newest
```
