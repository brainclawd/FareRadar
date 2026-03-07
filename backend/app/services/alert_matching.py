from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session
from ..models import DetectedDeal, UserAlert, DealAlert, DestinationType


def match_reasons(alert: UserAlert, deal: DetectedDeal) -> list[str]:
    reasons: list[str] = []
    if deal.origin in (alert.origin_airports or []):
        reasons.append(f"origin {deal.origin} is tracked")

    if alert.destination_type == DestinationType.anywhere:
        reasons.append("destination mode is anywhere")
    elif deal.destination in (alert.destinations or []):
        reasons.append(f"destination {deal.destination} is tracked")

    if alert.max_price is None or deal.price <= alert.max_price:
        reasons.append(f"price {deal.price} is within threshold")

    if deal.discount_percent >= alert.min_discount_percent:
        reasons.append(f"discount {deal.discount_percent}% meets threshold")

    if deal.cabin_class == alert.cabin_class:
        reasons.append(f"cabin {deal.cabin_class.value} matches")

    return reasons


def alert_matches_deal(alert: UserAlert, deal: DetectedDeal) -> tuple[bool, list[str]]:
    reasons = match_reasons(alert, deal)
    required_checks = [
        deal.origin in (alert.origin_airports or []),
        alert.destination_type == DestinationType.anywhere or deal.destination in (alert.destinations or []),
        alert.max_price is None or deal.price <= alert.max_price,
        deal.discount_percent >= alert.min_discount_percent,
        deal.cabin_class == alert.cabin_class,
        alert.is_active,
    ]
    return all(required_checks), reasons


def create_pending_alerts_for_deal(db: Session, deal: DetectedDeal) -> list[DealAlert]:
    alerts = db.scalars(select(UserAlert).where(UserAlert.is_active.is_(True))).all()
    created: list[DealAlert] = []

    for alert in alerts:
        matched, reasons = alert_matches_deal(alert, deal)
        if not matched:
            continue

        for channel in (alert.channels or ["email"]):
            existing = db.scalar(
                select(DealAlert).where(DealAlert.user_alert_id == alert.id, DealAlert.deal_id == deal.id)
            )
            if existing:
                continue
            row = DealAlert(
                user_alert_id=alert.id,
                deal_id=deal.id,
                channel=channel,
                status="pending",
                payload_json={"reasons": reasons},
            )
            db.add(row)
            created.append(row)

    db.commit()
    for row in created:
        db.refresh(row)
    return created
