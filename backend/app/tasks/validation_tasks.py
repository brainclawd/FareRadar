
from __future__ import annotations

from datetime import datetime

from celery.utils.log import get_task_logger

from ..celery_app import celery_app
from ..db import Base, SessionLocal, engine
from ..models import CandidateDeal, DealStatus, DetectedDeal, FlightPrice
from ..services.alert_matching import create_pending_alerts_for_deal
from ..services.provider import FlightSearchParams
from ..services.provider_runtime import search_with_resilience
from ..services.queue import publisher
from ..services.ranking import apply_feed_score

logger = get_task_logger(__name__)
Base.metadata.create_all(bind=engine)


@celery_app.task(name="app.tasks.validation_tasks.validate_candidate_deal_task")
def validate_candidate_deal_task(candidate_deal_id: int) -> dict:
    db = SessionLocal()
    try:
        candidate = db.get(CandidateDeal, candidate_deal_id)
        if not candidate:
            raise ValueError(f"Candidate deal {candidate_deal_id} not found")

        current_price = db.get(FlightPrice, candidate.flight_price_id)
        if not current_price:
            candidate.status = DealStatus.expired
            db.commit()
            return {"candidate_deal_id": candidate_deal_id, "status": "expired", "reason": "missing_flight_price"}

        offers, used_provider = search_with_resilience(
            db,
            provider_name=current_price.provider,
            params=FlightSearchParams(
                origin=candidate.origin,
                destination=candidate.destination,
                departure_date=candidate.departure_date,
                return_date=candidate.return_date,
                cabin_class=candidate.cabin_class,
                adults=1,
                max_results=1,
            ),
            operation="validate",
        )
        if not offers:
            candidate.status = DealStatus.expired
            db.commit()
            return {"candidate_deal_id": candidate_deal_id, "status": "expired", "reason": "no_offers"}

        best = min(offers, key=lambda x: x.price)
        if best.price > int(candidate.price * 1.08):
            candidate.status = DealStatus.expired
            db.commit()
            return {"candidate_deal_id": candidate_deal_id, "status": "expired", "reason": "price_moved"}

        existing = db.query(DetectedDeal).filter(DetectedDeal.candidate_deal_id == candidate.id).first()
        if existing:
            deal = existing
            deal.price = best.price
            deal.provider = used_provider
        else:
            deal = DetectedDeal(
                candidate_deal_id=candidate.id,
                origin=candidate.origin,
                destination=candidate.destination,
                price=best.price,
                normal_price=candidate.expected_price,
                discount_percent=round(((candidate.expected_price - best.price) / max(candidate.expected_price, 1)) * 100, 2),
                airline=best.airline,
                departure_date=best.departure_date,
                return_date=best.return_date or candidate.return_date,
                cabin_class=best.cabin_class,
                provider=used_provider,
                deep_link=best.deep_link,
                deal_score=candidate.score,
                status=DealStatus.validated,
                created_at=datetime.utcnow(),
            )
            db.add(deal)

        candidate.status = DealStatus.validated
        apply_feed_score(deal)
        db.commit()
        db.refresh(deal)

        pending = create_pending_alerts_for_deal(db, deal)
        for item in pending:
            publisher.publish_alert(item.id)

        return {"candidate_deal_id": candidate_deal_id, "status": "validated", "deal_id": deal.id, "queued_alerts": len(pending)}
    finally:
        db.close()
