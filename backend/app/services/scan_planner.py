from __future__ import annotations

from calendar import monthrange
from dataclasses import dataclass
from datetime import date, datetime
from sqlalchemy import select, desc
from sqlalchemy.orm import Session
from ..models import CabinClass, RouteBucket, RoutePriceStat, ScanJob
from ..config import settings


POPULAR_DESTINATIONS = {
    "NRT": 1.5,
    "HND": 1.45,
    "FCO": 1.25,
    "BCN": 1.2,
    "CDG": 1.25,
    "BKK": 1.35,
    "LHR": 1.4,
    "LIS": 1.1,
}


@dataclass
class PlannedBucket:
    origin: str
    destination: str
    cabin_class: CabinClass
    departure_month: str
    trip_length_min: int
    trip_length_max: int
    priority_score: float
    demand_score: float
    volatility_score: float
    deal_frequency_score: float
    refresh_interval_minutes: int


def month_string(d: date) -> str:
    return d.strftime("%Y-%m")


def score_bucket(db: Session, origin: str, destination: str, cabin_class: CabinClass) -> tuple[float, float, float, float, int]:
    stat = db.scalar(
        select(RoutePriceStat).where(
            RoutePriceStat.origin == origin,
            RoutePriceStat.destination == destination,
            RoutePriceStat.cabin_class == cabin_class,
        )
    )
    demand_score = POPULAR_DESTINATIONS.get(destination, 1.0)
    volatility_score = 1.0
    deal_frequency_score = 1.0

    if stat and stat.avg_price:
        spread = max(0.05, (stat.max_price - stat.min_price) / max(stat.avg_price, 1))
        volatility_score = round(1 + spread, 2)
        deal_frequency_score = round(1 + min(1.2, stat.sample_size / 50), 2)

    cabin_multiplier = 1.25 if cabin_class == CabinClass.business else 1.0
    priority = round(demand_score * volatility_score * deal_frequency_score * cabin_multiplier * 100, 2)

    if priority >= 220:
        refresh = 15
    elif priority >= 160:
        refresh = 60
    else:
        refresh = 360

    return priority, demand_score, volatility_score, deal_frequency_score, refresh


def build_route_buckets(
    db: Session,
    origins: list[str] | None = None,
    destinations: list[str] | None = None,
    cabins: list[CabinClass] | None = None,
    departure_months: int = 3,
    trip_length_min: int = 5,
    trip_length_max: int = 10,
) -> list[RouteBucket]:
    origins = origins or settings.scanner_origins
    destinations = destinations or settings.scanner_destinations
    cabins = cabins or [CabinClass.economy, CabinClass.business]

    created: list[RouteBucket] = []
    today = date.today()
    months = []
    cursor_year, cursor_month = today.year, today.month
    for _ in range(departure_months):
        months.append(f"{cursor_year:04d}-{cursor_month:02d}")
        cursor_month += 1
        if cursor_month > 12:
            cursor_month = 1
            cursor_year += 1

    for origin in origins:
        for destination in destinations:
            for cabin in cabins:
                for departure_month in months:
                    priority, demand, volatility, freq, refresh = score_bucket(db, origin, destination, cabin)
                    bucket = db.scalar(
                        select(RouteBucket).where(
                            RouteBucket.origin == origin,
                            RouteBucket.destination == destination,
                            RouteBucket.cabin_class == cabin,
                            RouteBucket.departure_month == departure_month,
                            RouteBucket.trip_length_min == trip_length_min,
                            RouteBucket.trip_length_max == trip_length_max,
                        )
                    )
                    if not bucket:
                        bucket = RouteBucket(
                            origin=origin,
                            destination=destination,
                            cabin_class=cabin,
                            departure_month=departure_month,
                            trip_length_min=trip_length_min,
                            trip_length_max=trip_length_max,
                        )
                        db.add(bucket)
                    bucket.priority_score = priority
                    bucket.demand_score = demand
                    bucket.volatility_score = volatility
                    bucket.deal_frequency_score = freq
                    bucket.refresh_interval_minutes = refresh
                    created.append(bucket)

    db.commit()
    for bucket in created:
        db.refresh(bucket)
    return created


def bucket_date_range(bucket: RouteBucket) -> tuple[date, date]:
    year, month = [int(p) for p in bucket.departure_month.split("-")]
    start = date(year, month, 1)
    end = date(year, month, monthrange(year, month)[1])
    return start, end


def create_scan_jobs(db: Session, provider: str, limit: int = 50) -> list[ScanJob]:
    buckets = db.scalars(
        select(RouteBucket).order_by(desc(RouteBucket.priority_score)).limit(limit)
    ).all()
    jobs: list[ScanJob] = []
    for bucket in buckets:
        start, end = bucket_date_range(bucket)
        job = ScanJob(
            provider=provider,
            origin=bucket.origin,
            destination=bucket.destination,
            cabin_class=bucket.cabin_class,
            departure_start=start,
            departure_end=end,
            trip_length_min=bucket.trip_length_min,
            trip_length_max=bucket.trip_length_max,
            priority_score=bucket.priority_score,
        )
        db.add(job)
        bucket.last_scanned_at = datetime.utcnow()
        jobs.append(job)
    db.commit()
    for job in jobs:
        db.refresh(job)
    return jobs
