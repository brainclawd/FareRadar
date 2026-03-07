from __future__ import annotations

from dataclasses import dataclass
from statistics import median, pstdev
from sqlalchemy import select, desc
from sqlalchemy.orm import Session
from ..models import FlightPrice, RoutePriceStat, CandidateDeal, DetectedDeal, DealStatus


@dataclass
class DetectionResult:
    is_deal: bool
    normal_price: int
    discount_percent: float
    score: float
    z_score: float
    sudden_drop_amount: int
    rarity_score: float


def compute_score(
    discount_percent: float,
    current_price: int,
    normal_price: int,
    z_score: float,
    sudden_drop_amount: int,
    rarity_score: float,
) -> float:
    raw = (
        (discount_percent * 100)
        + max(0, (normal_price - current_price) / 12)
        + max(0, z_score * 8)
        + max(0, sudden_drop_amount / 50)
        + (rarity_score * 10)
    )
    return round(raw, 2)


def update_route_stats(db: Session, origin: str, destination: str, cabin_class: str) -> RoutePriceStat:
    rows = db.scalars(
        select(FlightPrice).where(
            FlightPrice.origin == origin,
            FlightPrice.destination == destination,
            FlightPrice.cabin_class == cabin_class,
        )
    ).all()

    prices = [r.price for r in rows]
    if not prices:
        raise ValueError("No prices to aggregate")

    avg_price = sum(prices) / len(prices)
    median_price = median(prices)
    min_price = min(prices)
    max_price = max(prices)

    stat = db.scalar(
        select(RoutePriceStat).where(
            RoutePriceStat.origin == origin,
            RoutePriceStat.destination == destination,
            RoutePriceStat.cabin_class == cabin_class,
        )
    )

    if not stat:
        stat = RoutePriceStat(
            origin=origin,
            destination=destination,
            cabin_class=cabin_class,
            avg_price=avg_price,
            median_price=median_price,
            min_price=min_price,
            max_price=max_price,
            sample_size=len(prices),
        )
        db.add(stat)
    else:
        stat.avg_price = avg_price
        stat.median_price = median_price
        stat.min_price = min_price
        stat.max_price = max_price
        stat.sample_size = len(prices)

    db.commit()
    db.refresh(stat)
    return stat


def latest_previous_price(db: Session, current_price: FlightPrice) -> FlightPrice | None:
    return db.scalar(
        select(FlightPrice)
        .where(
            FlightPrice.origin == current_price.origin,
            FlightPrice.destination == current_price.destination,
            FlightPrice.cabin_class == current_price.cabin_class,
            FlightPrice.id != current_price.id,
        )
        .order_by(desc(FlightPrice.observed_at))
        .limit(1)
    )


def detect_deal(db: Session, current_price: FlightPrice, stat: RoutePriceStat) -> DetectionResult:
    normal_price = int(round(stat.median_price or stat.avg_price))
    if normal_price <= 0:
        return DetectionResult(False, 0, 0, 0, 0, 0, 0)

    route_prices = db.scalars(
        select(FlightPrice.price).where(
            FlightPrice.origin == current_price.origin,
            FlightPrice.destination == current_price.destination,
            FlightPrice.cabin_class == current_price.cabin_class,
        )
    ).all()
    sigma = pstdev(route_prices) if len(route_prices) > 1 else 0
    z_score = ((normal_price - current_price.price) / sigma) if sigma else 0
    discount_percent = round((normal_price - current_price.price) / normal_price, 4)

    previous = latest_previous_price(db, current_price)
    sudden_drop_amount = max(0, (previous.price - current_price.price) if previous else 0)
    rarity_score = 1.0 if current_price.price <= stat.min_price else 0.0

    is_deal = (
        discount_percent >= 0.35
        or sudden_drop_amount >= 250
        or current_price.price <= stat.min_price
        or z_score >= 1.8
    )

    score = compute_score(
        discount_percent=discount_percent,
        current_price=current_price.price,
        normal_price=normal_price,
        z_score=z_score,
        sudden_drop_amount=sudden_drop_amount,
        rarity_score=rarity_score,
    ) if is_deal else 0.0

    return DetectionResult(is_deal, normal_price, discount_percent, score, z_score, sudden_drop_amount, rarity_score)


def create_candidate_deal(db: Session, current_price: FlightPrice, result: DetectionResult) -> CandidateDeal:
    existing = db.scalar(
        select(CandidateDeal).where(CandidateDeal.flight_price_id == current_price.id)
    )
    if existing:
        return existing

    candidate = CandidateDeal(
        flight_price_id=current_price.id,
        origin=current_price.origin,
        destination=current_price.destination,
        departure_date=current_price.departure_date,
        return_date=current_price.return_date,
        airline=current_price.airline,
        cabin_class=current_price.cabin_class,
        price=current_price.price,
        expected_price=result.normal_price,
        discount_percent=round(result.discount_percent * 100, 2),
        z_score=round(result.z_score, 2),
        sudden_drop_amount=result.sudden_drop_amount,
        rarity_score=result.rarity_score,
        score=result.score,
        status=DealStatus.candidate,
    )
    db.add(candidate)
    db.commit()
    db.refresh(candidate)
    return candidate


def validate_candidate(db: Session, current_price: FlightPrice, candidate: CandidateDeal, result: DetectionResult) -> DetectedDeal:
    existing = db.scalar(
        select(DetectedDeal).where(
            DetectedDeal.origin == current_price.origin,
            DetectedDeal.destination == current_price.destination,
            DetectedDeal.departure_date == current_price.departure_date,
            DetectedDeal.return_date == current_price.return_date,
            DetectedDeal.price == current_price.price,
            DetectedDeal.cabin_class == current_price.cabin_class,
        )
    )
    if existing:
        return existing

    deal = DetectedDeal(
        candidate_deal_id=candidate.id,
        origin=current_price.origin,
        destination=current_price.destination,
        price=current_price.price,
        normal_price=result.normal_price,
        discount_percent=round(result.discount_percent * 100, 2),
        airline=current_price.airline,
        departure_date=current_price.departure_date,
        return_date=current_price.return_date,
        cabin_class=current_price.cabin_class,
        provider=current_price.provider,
        deep_link=current_price.deep_link,
        deal_score=result.score,
        status=DealStatus.validated,
    )
    candidate.status = DealStatus.validated
    db.add(deal)
    db.commit()
    db.refresh(deal)
    return deal


def maybe_create_deal(db: Session, current_price: FlightPrice) -> DetectedDeal | None:
    stat = update_route_stats(db, current_price.origin, current_price.destination, current_price.cabin_class)
    result = detect_deal(db, current_price, stat)

    if not result.is_deal:
        return None

    candidate = create_candidate_deal(db, current_price, result)
    # MVP validation strategy: trust provider fidelity >= 0.85 or strong score
    if current_price.fidelity_score < 0.85 and result.score < 65:
        return None

    return validate_candidate(db, current_price, candidate, result)
