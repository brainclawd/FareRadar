from __future__ import annotations

from datetime import datetime

from celery.utils.log import get_task_logger

from ..celery_app import celery_app
from ..config import settings
from ..db import Base, SessionLocal, engine
from ..models import DealAlert, Notification, UserAlert, User

logger = get_task_logger(__name__)
Base.metadata.create_all(bind=engine)


def _render_email(to_email: str, subject: str, body: str) -> None:
    # SMTP/provider wiring belongs here later. For now we log the final payload so the flow is testable.
    logger.info("sending email from=%s to=%s subject=%s body=%s", settings.notifications_from_email, to_email, subject, body)


@celery_app.task(name="app.tasks.alert_tasks.send_deal_alert_task")
def send_deal_alert_task(deal_alert_id: int) -> dict:
    db = SessionLocal()
    try:
        deal_alert = db.get(DealAlert, deal_alert_id)
        if not deal_alert:
            raise ValueError(f"Deal alert {deal_alert_id} not found")

        alert = db.get(UserAlert, deal_alert.user_alert_id)
        if not alert:
            deal_alert.status = "failed"
            db.commit()
            return {"deal_alert_id": deal_alert_id, "status": "failed", "reason": "missing_alert"}

        deal = db.get(__import__("app.models", fromlist=["DetectedDeal"]).DetectedDeal, deal_alert.deal_id)
        user = db.get(User, alert.user_id)
        if not deal or not user:
            deal_alert.status = "failed"
            db.commit()
            return {"deal_alert_id": deal_alert_id, "status": "failed", "reason": "missing_deal_or_user"}

        subject = f"🔥 Rare flight deal: {deal.origin} → {deal.destination} for ${deal.price}"
        body = (
            f"{deal.origin} → {deal.destination}\n"
            f"${deal.price} roundtrip (normally ${deal.normal_price})\n"
            f"{deal.airline} | {deal.departure_date} - {deal.return_date}\n"
            f"{deal.discount_percent}% cheaper than normal\n"
        )

        if deal_alert.channel == "email":
            _render_email(user.email, subject, body)

        notification = Notification(
            user_id=user.id,
            deal_id=deal.id,
            channel=deal_alert.channel,
            sent_at=datetime.utcnow(),
        )
        db.add(notification)
        deal_alert.status = "sent"
        deal_alert.sent_at = datetime.utcnow()
        db.commit()

        return {"deal_alert_id": deal_alert_id, "status": "sent", "channel": deal_alert.channel}
    finally:
        db.close()
