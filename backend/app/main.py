
from __future__ import annotations

from datetime import date, datetime, timedelta

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from .config import settings
from .db import Base, engine, get_db
from .models import (
    CabinClass,
    CandidateDeal,
    DealStatus,
    DetectedDeal,
    FlightPrice,
    JobStatus,
    Notification,
    ProviderHealthEvent,
    ScanJob,
    User,
    UserAlert,
    UserSearchPreference,
)
from .schemas import (
    AdminOverview,
    AlertCreate,
    AlertMatchPreview,
    AlertRead,
    CandidateDealRead,
    DealFunnelRead,
    DealRead,
    FlightOfferRead,
    FlightSearchRequest,
    HealthResponse,
    PreferenceCreate,
    PreferenceRead,
    ProviderHealthRead,
    ProviderStatus,
    QueuePublishResponse,
    RouteBucketRead,
    ScanJobRead,
    ScanPlanRequest,
    ScanRunRequest,
    UserCreate,
)
from .services.alert_matching import alert_matches_deal, create_pending_alerts_for_deal
from .services.deal_detection import maybe_create_deal
from .services.provider import FlightProviderError, FlightSearchParams, provider_statuses
from .services.provider_runtime import search_with_resilience
from .services.queue import publisher
from .services.ranking import apply_feed_score
from .services.scan_planner import build_route_buckets, create_scan_jobs

Base.metadata.create_all(bind=engine)

app = FastAPI(title="FareRadar API", version="0.4.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health", response_model=HealthResponse)
def health():
    return HealthResponse(status="ok")


@app.get("/providers", response_model=list[ProviderStatus])
def get_providers():
    return provider_statuses()


@app.post("/users")
def create_user(payload: UserCreate, db: Session = Depends(get_db)):
    existing = db.scalar(select(User).where(User.email == payload.email))
    if existing:
        return {"id": str(existing.id), "email": existing.email, "plan": existing.plan}

    user = User(email=payload.email, plan=payload.plan)
    db.add(user)
    db.commit()
    db.refresh(user)
    return {"id": str(user.id), "email": user.email, "plan": user.plan}


@app.post("/preferences", response_model=PreferenceRead)
def create_preference(payload: PreferenceCreate, db: Session = Depends(get_db)):
    user = db.get(User, payload.user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    pref = UserSearchPreference(**payload.model_dump())
    db.add(pref)
    db.commit()
    db.refresh(pref)
    return pref


@app.post("/alerts", response_model=AlertRead)
def create_alert(payload: AlertCreate, db: Session = Depends(get_db)):
    user = db.get(User, payload.user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    alert = UserAlert(**payload.model_dump())
    db.add(alert)
    db.commit()
    db.refresh(alert)
    return alert


@app.get("/alerts", response_model=list[AlertRead])
def list_alerts(user_id: str | None = None, db: Session = Depends(get_db)):
    stmt = select(UserAlert).order_by(desc(UserAlert.created_at))
    if user_id:
        stmt = stmt.where(UserAlert.user_id == user_id)
    return db.scalars(stmt).all()


@app.get("/deals", response_model=list[DealRead])
def get_deals(
    limit: int = 50,
    origin: str | None = None,
    destination: str | None = None,
    cabin_class: CabinClass | None = None,
    sort_by: str = Query(default="feed_score", pattern="^(feed_score|deal_score|newest)$"),
    db: Session = Depends(get_db),
):
    stmt = select(DetectedDeal)
    if origin:
        stmt = stmt.where(DetectedDeal.origin == origin.upper())
    if destination:
        stmt = stmt.where(DetectedDeal.destination == destination.upper())
    if cabin_class:
        stmt = stmt.where(DetectedDeal.cabin_class == cabin_class)

    if sort_by == "deal_score":
        stmt = stmt.order_by(desc(DetectedDeal.deal_score), desc(DetectedDeal.created_at))
    elif sort_by == "newest":
        stmt = stmt.order_by(desc(DetectedDeal.created_at))
    else:
        stmt = stmt.order_by(desc(DetectedDeal.feed_score), desc(DetectedDeal.created_at))

    deals = db.scalars(stmt.limit(limit)).all()
    mutated = False
    for deal in deals:
        if not deal.feed_score:
            apply_feed_score(deal)
            mutated = True
    if mutated:
        db.commit()
    return deals


@app.get("/deals/candidates", response_model=list[CandidateDealRead])
def get_candidate_deals(limit: int = 50, db: Session = Depends(get_db)):
    return db.scalars(select(CandidateDeal).order_by(desc(CandidateDeal.score)).limit(limit)).all()


@app.get("/deals/{deal_id}/match-preview", response_model=list[AlertMatchPreview])
def preview_alert_matches(deal_id: int, db: Session = Depends(get_db)):
    deal = db.get(DetectedDeal, deal_id)
    if not deal:
        raise HTTPException(status_code=404, detail="Deal not found")

    rows = db.scalars(select(UserAlert).order_by(desc(UserAlert.created_at))).all()
    previews: list[AlertMatchPreview] = []
    for alert in rows:
        matched, reasons = alert_matches_deal(alert, deal)
        previews.append(
            AlertMatchPreview(
                alert_id=alert.id,
                alert_name=alert.name,
                matched=matched,
                reasons=reasons,
                channels=alert.channels or ["email"],
            )
        )
    return previews


@app.post("/search/flights", response_model=list[FlightOfferRead])
def search_flights(payload: FlightSearchRequest, provider: str | None = Query(default=None), db: Session = Depends(get_db)):
    try:
        offers, _used = search_with_resilience(
            db,
            provider_name=provider or settings.flight_provider,
            params=FlightSearchParams(
                origin=payload.origin,
                destination=payload.destination,
                departure_date=payload.departure_date,
                return_date=payload.return_date,
                adults=payload.adults,
                cabin_class=payload.cabin_class,
                max_price=payload.max_price,
                currency_code=payload.currency_code,
                max_results=payload.max_results,
                non_stop=payload.non_stop,
            ),
            operation="search",
        )
    except FlightProviderError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return [FlightOfferRead(**offer.to_dict()) for offer in offers]


@app.post("/scan/plan", response_model=list[RouteBucketRead])
def plan_scan(payload: ScanPlanRequest, db: Session = Depends(get_db)):
    buckets = build_route_buckets(
        db=db,
        origins=payload.origins or settings.scanner_origins,
        destinations=payload.destinations or settings.scanner_destinations,
        cabins=payload.cabins,
        departure_months=payload.departure_months,
        trip_length_min=payload.trip_length_min,
        trip_length_max=payload.trip_length_max,
    )
    return sorted(buckets, key=lambda b: b.priority_score, reverse=True)


@app.get("/route-buckets", response_model=list[RouteBucketRead])
def get_route_buckets(limit: int = 100, db: Session = Depends(get_db)):
    from .models import RouteBucket
    stmt = select(RouteBucket).order_by(desc(RouteBucket.priority_score)).limit(limit)
    return db.scalars(stmt).all()


@app.post("/scan/jobs", response_model=list[ScanJobRead])
def enqueue_scan_jobs(limit: int = 50, provider: str | None = Query(default=None), db: Session = Depends(get_db)):
    jobs = create_scan_jobs(db, provider=provider or settings.flight_provider, limit=limit)
    for job in jobs:
        publisher.publish_scan_job(job.id)
    return jobs


@app.post("/scan/jobs/dispatch", response_model=QueuePublishResponse)
def dispatch_scan_jobs(limit: int = 25, provider: str | None = Query(default=None), db: Session = Depends(get_db)):
    jobs = create_scan_jobs(db, provider=provider or settings.flight_provider, limit=limit)
    for job in jobs:
        publisher.publish_scan_job(job.id)
    return QueuePublishResponse(queued=len(jobs), detail="queued scan jobs")


@app.post("/candidates/{candidate_deal_id}/validate", response_model=QueuePublishResponse)
def validate_candidate(candidate_deal_id: int, db: Session = Depends(get_db)):
    candidate = db.get(CandidateDeal, candidate_deal_id)
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate deal not found")
    publisher.publish_validation(candidate.id)
    return QueuePublishResponse(queued=1, detail="queued candidate validation")


@app.post("/scan/run")
def run_scan(payload: ScanRunRequest, provider: str | None = Query(default=None), db: Session = Depends(get_db)):
    origins = payload.origins or settings.scanner_origins
    destinations = payload.destinations or settings.scanner_destinations
    selected_provider = provider or settings.flight_provider

    departure_start = payload.departure_start or (date.today() + timedelta(days=settings.scanner_window_start_days))
    departure_end = payload.departure_end or (date.today() + timedelta(days=settings.scanner_window_end_days))
    if departure_end < departure_start:
        raise HTTPException(status_code=400, detail="departure_end must be on or after departure_start")

    created_prices = 0
    created_deals = 0
    queued_alerts = 0

    for origin in origins:
        for destination in destinations:
            for cabin in payload.cabins:
                departure_date = departure_start
                while departure_date <= departure_end:
                    return_date = departure_date + timedelta(days=payload.trip_length_min)
                    try:
                        offers, used_provider = search_with_resilience(
                            db,
                            provider_name=selected_provider,
                            params=FlightSearchParams(
                                origin=origin,
                                destination=destination,
                                departure_date=departure_date,
                                return_date=return_date,
                                cabin_class=cabin,
                                adults=1,
                                max_results=payload.max_results,
                            ),
                            operation="scan",
                        )
                    except FlightProviderError as exc:
                        raise HTTPException(status_code=400, detail=str(exc)) from exc

                    for offer in offers:
                        row = FlightPrice(
                            provider=used_provider,
                            origin=offer.origin,
                            destination=offer.destination,
                            departure_date=offer.departure_date,
                            return_date=offer.return_date or return_date,
                            airline=offer.airline,
                            cabin_class=offer.cabin_class,
                            price=offer.price,
                            currency_code=offer.currency_code,
                            deep_link=offer.deep_link,
                            raw_json=offer.raw or {},
                        )
                        db.add(row)
                        db.commit()
                        db.refresh(row)
                        created_prices += 1

                        deal = maybe_create_deal(db, row)
                        if deal:
                            apply_feed_score(deal)
                            db.commit()
                            created_deals += 1
                            pending = create_pending_alerts_for_deal(db, deal)
                            queued_alerts += len(pending)
                            for item in pending:
                                publisher.publish_alert(item.id)
                    departure_date += timedelta(days=7)

    return {
        "status": "completed",
        "provider": selected_provider,
        "prices_created": created_prices,
        "deals_created": created_deals,
        "alerts_queued": queued_alerts,
    }


@app.get("/admin/overview", response_model=AdminOverview)
def admin_overview(db: Session = Depends(get_db)):
    since = datetime.utcnow() - timedelta(hours=24)
    return AdminOverview(
        queued_jobs=db.scalar(select(func.count()).select_from(ScanJob).where(ScanJob.status == JobStatus.queued)) or 0,
        running_jobs=db.scalar(select(func.count()).select_from(ScanJob).where(ScanJob.status == JobStatus.running)) or 0,
        failed_jobs_24h=db.scalar(select(func.count()).select_from(ScanJob).where(ScanJob.status == JobStatus.failed, ScanJob.completed_at >= since)) or 0,
        candidate_deals=db.scalar(select(func.count()).select_from(CandidateDeal)) or 0,
        validated_deals=db.scalar(select(func.count()).select_from(DetectedDeal).where(DetectedDeal.status == DealStatus.validated)) or 0,
        active_alerts=db.scalar(select(func.count()).select_from(UserAlert).where(UserAlert.is_active.is_(True))) or 0,
        notifications_sent_24h=db.scalar(select(func.count()).select_from(Notification).where(Notification.sent_at >= since)) or 0,
    )


@app.get("/admin/provider-health", response_model=list[ProviderHealthRead])
def admin_provider_health(db: Session = Depends(get_db)):
    providers = [row["provider"] for row in provider_statuses()]
    results: list[ProviderHealthRead] = []
    for provider in providers:
        ok_events = db.scalar(select(func.count()).select_from(ProviderHealthEvent).where(ProviderHealthEvent.provider == provider, ProviderHealthEvent.status == "ok")) or 0
        failed_events = db.scalar(select(func.count()).select_from(ProviderHealthEvent).where(ProviderHealthEvent.provider == provider, ProviderHealthEvent.status == "failed")) or 0
        last = db.scalar(select(ProviderHealthEvent).where(ProviderHealthEvent.provider == provider).order_by(desc(ProviderHealthEvent.created_at)).limit(1))
        avg_latency = db.scalar(select(func.avg(ProviderHealthEvent.latency_ms)).where(ProviderHealthEvent.provider == provider, ProviderHealthEvent.latency_ms.is_not(None)))
        results.append(
            ProviderHealthRead(
                provider=provider,
                ok_events=ok_events,
                failed_events=failed_events,
                last_status=last.status if last else None,
                last_error_message=last.error_message if last else None,
                avg_latency_ms=float(avg_latency) if avg_latency is not None else None,
                last_event_at=last.created_at if last else None,
            )
        )
    return results


@app.get("/admin/scan-jobs", response_model=list[ScanJobRead])
def admin_scan_jobs(limit: int = 50, db: Session = Depends(get_db)):
    return db.scalars(select(ScanJob).order_by(desc(ScanJob.queued_at)).limit(limit)).all()


@app.get("/admin/deals/funnel", response_model=DealFunnelRead)
def admin_deals_funnel(db: Session = Depends(get_db)):
    return DealFunnelRead(
        candidates_total=db.scalar(select(func.count()).select_from(CandidateDeal)) or 0,
        candidates_validated=db.scalar(select(func.count()).select_from(CandidateDeal).where(CandidateDeal.status == DealStatus.validated)) or 0,
        candidates_expired=db.scalar(select(func.count()).select_from(CandidateDeal).where(CandidateDeal.status == DealStatus.expired)) or 0,
        validated_deals_total=db.scalar(select(func.count()).select_from(DetectedDeal)) or 0,
    )
