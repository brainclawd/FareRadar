# FareRadar v1 Architecture

## Goal

Detect rare flight deals at scale without turning the product into a slow live-search-only app.

The v1 architecture uses:
- **route buckets** for breadth
- **scan jobs** for controlled polling
- **candidate deals** for anomaly staging
- **validated deals** for user-facing inventory
- **deal alerts** for fan-out into email/push queues

## Service map

### 1. API service
Handles:
- users
- alerts
- provider search
- scan planning
- scan job enqueueing
- deals feed
- alert-match preview

### 2. Planner service
Creates route buckets by:
- origin
- destination
- cabin
- departure month
- trip-length band

Each bucket gets a `priority_score` based on:
- destination demand
- observed route volatility
- historical scan depth / deal frequency
- cabin multiplier

### 3. Scanner service
Consumes scan jobs and:
- calls provider adapters
- normalizes results
- stores price quotes
- updates route stats
- creates candidate deals
- validates candidate deals
- creates pending alert rows

### 4. Alert fan-out service
Consumes pending `deal_alerts` rows and sends:
- email
- push
- sms later

## Data flow

```text
route buckets -> scan jobs -> provider search -> flight_prices
                                          -> route_price_stats
                                          -> candidate_deals
                                          -> detected_deals
                                          -> deal_alerts
```

## Why the split matters

### `candidate_deals`
These are suspicious fares that passed anomaly scoring but have not necessarily been user-notified yet.

### `detected_deals`
These are the validated deals safe to show in the feed and send through alerts.

This split avoids polluting the main feed with low-confidence noise.

## Deal detection formula

The current scorer uses:
- discount vs. route median
- z-score vs. historical price spread
- sudden drop from latest previous quote
- rarity bonus when matching a new route minimum

Roughly:

```text
score =
discount%
+ absolute savings factor
+ z-score bonus
+ sudden drop bonus
+ rarity bonus
```

## Queue strategy

For local dev, the code ships with a print-based queue publisher stub.

Production path:
- Redis
- Celery or RQ for Python workers
- separate workers for:
  - scans
  - revalidation
  - alert delivery

## Scale-up path

### Stage 1
Keep everything in Postgres.

### Stage 2
Partition `flight_prices` by month or provider.

### Stage 3
Move quote history to ClickHouse or BigQuery, keep transactional tables in Postgres.

## Recommended production services

- **Web:** Vercel
- **API:** Fly.io / Railway / ECS / Cloud Run
- **Workers:** ECS / Cloud Run jobs / Kubernetes
- **DB:** Postgres
- **Queue:** Redis
- **Analytics:** ClickHouse later
- **Search/index:** Typesense or OpenSearch for destination/deal browse

## First production hardening tasks

1. provider retries with backoff
2. idempotent scan job execution
3. dedupe windows on alerts
4. auth + admin-only scan endpoints
5. provider usage metering and budget caps
6. synthetic monitoring for stale scanners
