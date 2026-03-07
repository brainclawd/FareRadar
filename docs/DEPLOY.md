# Deployment Guide

This repo is prepped for a first live release with:

- **Frontend:** Vercel
- **API:** Render web service
- **Worker:** Render background worker
- **Scheduler:** Render background worker running Celery Beat
- **Postgres:** Supabase
- **Redis:** Upstash Redis

## Required environment variables

### Backend (Render web + worker + beat)

```env
APP_ENV=production
DATABASE_URL=postgresql+psycopg://...
REDIS_URL=rediss://...
CELERY_BROKER_URL=rediss://...
CELERY_RESULT_BACKEND=rediss://...
CORS_ALLOWED_ORIGINS=["https://YOUR-VERCEL-APP.vercel.app"]
JWT_SECRET=replace-with-a-long-random-string
FLIGHT_PROVIDER=mock
NOTIFICATIONS_FROM_EMAIL=deals@yourdomain.com
RESEND_API_KEY=
AMADEUS_CLIENT_ID=
AMADEUS_CLIENT_SECRET=
KIWI_API_KEY=
```

### Frontend (Vercel)

```env
NEXT_PUBLIC_API_URL=https://YOUR-RENDER-API.onrender.com
```

## Recommended first-launch scanner limits

Use `mock` or a tiny real route set first.

```env
SCANNER_ORIGINS=["SLC","LAX","DEN"]
SCANNER_DESTINATIONS=["NRT","CDG","FCO","BCN","BKK"]
SCANNER_WINDOW_START_DAYS=30
SCANNER_WINDOW_END_DAYS=120
SCANNER_TRIP_LENGTH_MIN=5
SCANNER_TRIP_LENGTH_MAX=10
```

## Quick smoke test after deploy

1. Open `https://YOUR-RENDER-API.onrender.com/health`
2. Open `https://YOUR-VERCEL-APP.vercel.app`
3. Create a user via the API docs
4. Create an alert
5. Run one scan:
   - `POST /scan/plan`
   - `POST /scan/jobs/dispatch`
6. Refresh the homepage and verify deals appear

## Notes

- Use the same Redis URL for `REDIS_URL`, `CELERY_BROKER_URL`, and `CELERY_RESULT_BACKEND`.
- Start with `FLIGHT_PROVIDER=mock` until the full loop works.
- After the site is stable, switch to `amadeus` and add real credentials.
