
from __future__ import annotations

from datetime import datetime

from ..config import settings
from ..models import CabinClass, DetectedDeal


def compute_feed_score(deal: DetectedDeal) -> tuple[float, dict]:
    age_hours = max((datetime.utcnow() - deal.created_at).total_seconds() / 3600, 0.0)
    freshness = max(0.0, 1.0 - (age_hours / max(settings.deals_freshness_half_life_hours, 1)))
    business_bonus = settings.deals_business_class_bonus if deal.cabin_class == CabinClass.business else 0.0
    first_bonus = settings.deals_business_class_bonus * 0.8 if deal.cabin_class == CabinClass.first else 0.0
    destination_bonus = 6.0 if deal.destination in settings.deals_popular_destinations else 0.0
    discount_bonus = float(deal.discount_percent)
    raw = float(deal.deal_score) + discount_bonus + business_bonus + first_bonus + destination_bonus + (freshness * 15.0)
    score = round(raw, 2)
    factors = {
        "freshness_bonus": round(freshness * 15.0, 2),
        "business_bonus": round(business_bonus, 2),
        "first_bonus": round(first_bonus, 2),
        "destination_bonus": round(destination_bonus, 2),
        "discount_bonus": round(discount_bonus, 2),
        "base_deal_score": round(float(deal.deal_score), 2),
        "age_hours": round(age_hours, 2),
    }
    return score, factors


def apply_feed_score(deal: DetectedDeal) -> DetectedDeal:
    score, factors = compute_feed_score(deal)
    deal.feed_score = score
    deal.quality_factors_json = factors
    return deal
