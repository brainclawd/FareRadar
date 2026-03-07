
from __future__ import annotations

from datetime import datetime, timedelta

from celery.utils.log import get_task_logger
from sqlalchemy.orm import Session

from ..celery_app import celery_app
from ..db import Base, SessionLocal, engine
from ..models import FlightPrice, JobStatus, ScanJob
from ..services.alert_matching import create_pending_alerts_for_deal
from ..services.deal_detection import maybe_create_deal
from ..services.provider import FlightSearchParams, FlightProviderError
from ..services.provider_runtime import search_with_resilience
from ..services.queue import publisher
from ..services.scan_planner import build_route_buckets, create_scan_jobs

logger = get_task_logger(__name__)
Base.metadata.create_all(bind=engine)


def _process_scan_job(db: Session, job: ScanJob) -> dict:
    job.status = JobStatus.running
    job.started_at = datetime.utcnow()
    db.commit()

    prices_created = 0
    deals_created = 0
    alerts_queued = 0
    used_providers: set[str] = set()

    departure_date = job.departure_start
    while departure_date <= job.departure_end:
        return_date = departure_date + timedelta(days=job.trip_length_min)
        params = FlightSearchParams(
            origin=job.origin,
            destination=job.destination,
            departure_date=departure_date,
            return_date=return_date,
            cabin_class=job.cabin_class,
            adults=1,
            max_results=3,
        )
        offers, used_provider = search_with_resilience(db, provider_name=job.provider, params=params, operation="scan")
        used_providers.add(used_provider)
        for offer in offers:
            row = FlightPrice(
                provider=offer.provider,
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
            prices_created += 1

            deal = maybe_create_deal(db, row)
            if deal:
                deals_created += 1
                pending = create_pending_alerts_for_deal(db, deal)
                alerts_queued += len(pending)
                for item in pending:
                    publisher.publish_alert(item.id)

        departure_date += timedelta(days=7)

    job.status = JobStatus.completed
    job.completed_at = datetime.utcnow()
    db.commit()
    return {
        "job_id": job.id,
        "prices_created": prices_created,
        "deals_created": deals_created,
        "alerts_queued": alerts_queued,
        "providers_used": sorted(used_providers),
    }


@celery_app.task(name="app.tasks.scan_tasks.scan_job_task")
def scan_job_task(job_id: int) -> dict:
    db = SessionLocal()
    try:
        job = db.get(ScanJob, job_id)
        if not job:
            raise ValueError(f"Scan job {job_id} not found")
        return _process_scan_job(db, job)
    except FlightProviderError as exc:
        job = db.get(ScanJob, job_id)
        if job:
            job.status = JobStatus.failed
            job.error_message = str(exc)
            job.completed_at = datetime.utcnow()
            db.commit()
        logger.exception("scan job failed")
        raise
    finally:
        db.close()


@celery_app.task(name="app.tasks.scan_tasks.plan_and_dispatch_scans_task")
def plan_and_dispatch_scans_task(provider: str | None = None, limit: int = 25) -> dict:
    db = SessionLocal()
    try:
        build_route_buckets(db)
        jobs = create_scan_jobs(db, provider=(provider or "mock"), limit=limit)
        for job in jobs:
            publisher.publish_scan_job(job.id)
        return {"planned_jobs": len(jobs)}
    finally:
        db.close()
