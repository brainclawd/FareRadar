# FareRadar v1 API Contracts

## Create user
`POST /users`

```json
{
  "email": "founder@example.com",
  "plan": "free"
}
```

## Create alert
`POST /alerts`

```json
{
  "user_id": "00000000-0000-0000-0000-000000000000",
  "name": "Europe under 500",
  "origin_airports": ["SLC", "LAX"],
  "destination_type": "region",
  "destinations": ["EUROPE"],
  "max_price": 500,
  "cabin_class": "economy",
  "date_flexibility": "plus_minus_7",
  "min_discount_percent": 35,
  "channels": ["email"],
  "is_active": true,
  "metadata_json": {
    "regions": ["europe"]
  }
}
```

## Build route buckets
`POST /scan/plan`

```json
{
  "origins": ["SLC", "LAX"],
  "destinations": ["NRT", "FCO", "CDG"],
  "cabins": ["economy", "business"],
  "departure_months": 3,
  "trip_length_min": 5,
  "trip_length_max": 10
}
```

Response includes:
- route bucket id
- departure month
- priority score
- refresh interval

## Enqueue scan jobs
`POST /scan/jobs?provider=mock&limit=25`

Response includes:
- scan job ids
- provider
- route
- cabin
- date range
- priority score
- status

## Run a scan synchronously
`POST /scan/run?provider=mock`

```json
{
  "origins": ["SLC"],
  "destinations": ["NRT", "FCO"],
  "cabins": ["economy"],
  "trip_length_min": 5,
  "trip_length_max": 10,
  "adults": 1,
  "max_results": 3
}
```

Response:
```json
{
  "provider": "mock",
  "prices_created": 18,
  "deals_created": 3,
  "queued_alerts": 2,
  "window": {
    "start": "2026-04-05",
    "end": "2026-09-02"
  }
}
```

## Live provider search
`POST /search/flights?provider=amadeus`

```json
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

## List validated deals
`GET /deals?origin=LAX&cabin_class=economy`

## List candidate deals
`GET /deals/candidates`

## Preview which alerts match a deal
`GET /deals/{deal_id}/match-preview`

Response item:
```json
{
  "alert_id": 3,
  "alert_name": "Japan from West Coast",
  "matched": true,
  "reasons": [
    "origin LAX is tracked",
    "destination NRT is tracked",
    "price 421 is within threshold",
    "discount 60.0% meets threshold",
    "cabin economy matches"
  ],
  "channels": ["email"]
}
```

## Queue alerts for a specific deal
`POST /deals/{deal_id}/alerts/queue`
