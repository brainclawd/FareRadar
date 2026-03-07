
import enum
import uuid
from datetime import datetime, date
from sqlalchemy import (
    String,
    Integer,
    DateTime,
    Date,
    Float,
    ForeignKey,
    Enum,
    JSON,
    UniqueConstraint,
    Boolean,
    Text,
)
from sqlalchemy.dialects.postgresql import UUID, ARRAY
from sqlalchemy.orm import Mapped, mapped_column
from .db import Base


class CabinClass(str, enum.Enum):
    economy = "economy"
    premium_economy = "premium_economy"
    business = "business"
    first = "first"


class DestinationType(str, enum.Enum):
    anywhere = "anywhere"
    region = "region"
    city = "city"


class AlertChannel(str, enum.Enum):
    email = "email"
    push = "push"
    sms = "sms"


class DealStatus(str, enum.Enum):
    candidate = "candidate"
    validated = "validated"
    expired = "expired"
    dismissed = "dismissed"


class JobStatus(str, enum.Enum):
    queued = "queued"
    running = "running"
    completed = "completed"
    failed = "failed"


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    plan: Mapped[str] = mapped_column(String(50), default="free")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class UserSearchPreference(Base):
    __tablename__ = "user_search_preferences"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"))
    origin_airports: Mapped[list[str]] = mapped_column(ARRAY(String(8)))
    destination_type: Mapped[DestinationType] = mapped_column(Enum(DestinationType))
    destinations: Mapped[list[str]] = mapped_column(ARRAY(String(64)))
    max_price: Mapped[int] = mapped_column(Integer)
    cabin_class: Mapped[CabinClass] = mapped_column(Enum(CabinClass))
    date_flexibility: Mapped[str] = mapped_column(String(32), default="exact")
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class UserAlert(Base):
    __tablename__ = "user_alerts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    origin_airports: Mapped[list[str]] = mapped_column(ARRAY(String(8)))
    destination_type: Mapped[DestinationType] = mapped_column(Enum(DestinationType))
    destinations: Mapped[list[str]] = mapped_column(ARRAY(String(64)))
    max_price: Mapped[int | None] = mapped_column(Integer, nullable=True)
    cabin_class: Mapped[CabinClass] = mapped_column(Enum(CabinClass))
    date_flexibility: Mapped[str] = mapped_column(String(32), default="exact")
    min_discount_percent: Mapped[float] = mapped_column(Float, default=35.0)
    channels: Mapped[list[str]] = mapped_column(ARRAY(String(16)), default=list)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class RouteBucket(Base):
    __tablename__ = "route_buckets"
    __table_args__ = (
        UniqueConstraint(
            "origin", "destination", "cabin_class", "departure_month", "trip_length_min", "trip_length_max",
            name="uq_route_bucket"
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    origin: Mapped[str] = mapped_column(String(8), index=True)
    destination: Mapped[str] = mapped_column(String(8), index=True)
    cabin_class: Mapped[CabinClass] = mapped_column(Enum(CabinClass), index=True)
    departure_month: Mapped[str] = mapped_column(String(7), index=True)  # YYYY-MM
    trip_length_min: Mapped[int] = mapped_column(Integer, default=5)
    trip_length_max: Mapped[int] = mapped_column(Integer, default=10)
    priority_score: Mapped[float] = mapped_column(Float, default=0, index=True)
    demand_score: Mapped[float] = mapped_column(Float, default=1)
    volatility_score: Mapped[float] = mapped_column(Float, default=1)
    deal_frequency_score: Mapped[float] = mapped_column(Float, default=1)
    refresh_interval_minutes: Mapped[int] = mapped_column(Integer, default=60)
    last_scanned_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    next_scan_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class ScanJob(Base):
    __tablename__ = "scan_jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    provider: Mapped[str] = mapped_column(String(32))
    origin: Mapped[str] = mapped_column(String(8), index=True)
    destination: Mapped[str] = mapped_column(String(8), index=True)
    cabin_class: Mapped[CabinClass] = mapped_column(Enum(CabinClass))
    departure_start: Mapped[date] = mapped_column(Date)
    departure_end: Mapped[date] = mapped_column(Date)
    trip_length_min: Mapped[int] = mapped_column(Integer)
    trip_length_max: Mapped[int] = mapped_column(Integer)
    priority_score: Mapped[float] = mapped_column(Float, default=0)
    status: Mapped[JobStatus] = mapped_column(Enum(JobStatus), default=JobStatus.queued)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    queued_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class FlightPrice(Base):
    __tablename__ = "flight_prices"
    __table_args__ = (
        UniqueConstraint(
            "origin", "destination", "departure_date", "return_date", "airline", "cabin_class", "observed_at",
            name="uq_price_observation"
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    provider: Mapped[str] = mapped_column(String(32), default="mock")
    origin: Mapped[str] = mapped_column(String(8), index=True)
    destination: Mapped[str] = mapped_column(String(8), index=True)
    departure_date: Mapped[date] = mapped_column(Date, index=True)
    return_date: Mapped[date] = mapped_column(Date, index=True)
    airline: Mapped[str] = mapped_column(String(64))
    cabin_class: Mapped[CabinClass] = mapped_column(Enum(CabinClass), index=True)
    stops: Mapped[int] = mapped_column(Integer, default=0)
    price: Mapped[int] = mapped_column(Integer, index=True)
    currency_code: Mapped[str] = mapped_column(String(3), default="USD")
    deep_link: Mapped[str | None] = mapped_column(Text, nullable=True)
    fidelity_score: Mapped[float] = mapped_column(Float, default=0.9)
    raw_json: Mapped[dict] = mapped_column(JSON, default=dict)
    observed_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)


class RoutePriceStat(Base):
    __tablename__ = "route_price_stats"
    __table_args__ = (
        UniqueConstraint("origin", "destination", "cabin_class", name="uq_route_stat"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    origin: Mapped[str] = mapped_column(String(8), index=True)
    destination: Mapped[str] = mapped_column(String(8), index=True)
    cabin_class: Mapped[CabinClass] = mapped_column(Enum(CabinClass))
    avg_price: Mapped[float] = mapped_column(Float)
    median_price: Mapped[float] = mapped_column(Float)
    min_price: Mapped[int] = mapped_column(Integer)
    max_price: Mapped[int] = mapped_column(Integer)
    sample_size: Mapped[int] = mapped_column(Integer, default=0)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class CandidateDeal(Base):
    __tablename__ = "candidate_deals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    flight_price_id: Mapped[int] = mapped_column(Integer, ForeignKey("flight_prices.id", ondelete="CASCADE"), unique=True)
    origin: Mapped[str] = mapped_column(String(8), index=True)
    destination: Mapped[str] = mapped_column(String(8), index=True)
    departure_date: Mapped[date] = mapped_column(Date)
    return_date: Mapped[date] = mapped_column(Date)
    airline: Mapped[str] = mapped_column(String(64))
    cabin_class: Mapped[CabinClass] = mapped_column(Enum(CabinClass))
    price: Mapped[int] = mapped_column(Integer)
    expected_price: Mapped[int] = mapped_column(Integer)
    discount_percent: Mapped[float] = mapped_column(Float)
    z_score: Mapped[float] = mapped_column(Float, default=0)
    sudden_drop_amount: Mapped[int] = mapped_column(Integer, default=0)
    rarity_score: Mapped[float] = mapped_column(Float, default=0)
    score: Mapped[float] = mapped_column(Float, default=0, index=True)
    status: Mapped[DealStatus] = mapped_column(Enum(DealStatus), default=DealStatus.candidate, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class DetectedDeal(Base):
    __tablename__ = "detected_deals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    candidate_deal_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("candidate_deals.id", ondelete="SET NULL"), nullable=True)
    origin: Mapped[str] = mapped_column(String(8), index=True)
    destination: Mapped[str] = mapped_column(String(8), index=True)
    price: Mapped[int] = mapped_column(Integer)
    normal_price: Mapped[int] = mapped_column(Integer)
    discount_percent: Mapped[float] = mapped_column(Float)
    airline: Mapped[str] = mapped_column(String(64))
    departure_date: Mapped[date] = mapped_column(Date)
    return_date: Mapped[date] = mapped_column(Date)
    cabin_class: Mapped[CabinClass] = mapped_column(Enum(CabinClass))
    provider: Mapped[str] = mapped_column(String(32), default="mock")
    deep_link: Mapped[str | None] = mapped_column(Text, nullable=True)
    deal_score: Mapped[float] = mapped_column(Float, default=0, index=True)
    feed_score: Mapped[float] = mapped_column(Float, default=0, index=True)
    quality_factors_json: Mapped[dict] = mapped_column(JSON, default=dict)
    status: Mapped[DealStatus] = mapped_column(Enum(DealStatus), default=DealStatus.validated)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class DealAlert(Base):
    __tablename__ = "deal_alerts"
    __table_args__ = (
        UniqueConstraint("user_alert_id", "deal_id", name="uq_alert_deal_send"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_alert_id: Mapped[int] = mapped_column(Integer, ForeignKey("user_alerts.id", ondelete="CASCADE"), index=True)
    deal_id: Mapped[int] = mapped_column(Integer, ForeignKey("detected_deals.id", ondelete="CASCADE"), index=True)
    channel: Mapped[str] = mapped_column(String(16), default=AlertChannel.email.value)
    status: Mapped[str] = mapped_column(String(32), default="pending")
    payload_json: Mapped[dict] = mapped_column(JSON, default=dict)
    queued_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"))
    deal_id: Mapped[int] = mapped_column(Integer, ForeignKey("detected_deals.id", ondelete="CASCADE"))
    channel: Mapped[str] = mapped_column(String(32), default="email")
    sent_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class ProviderHealthEvent(Base):
    __tablename__ = "provider_health_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    provider: Mapped[str] = mapped_column(String(32), index=True)
    status: Mapped[str] = mapped_column(String(16), index=True)
    operation: Mapped[str] = mapped_column(String(32), default="search")
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    context_json: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
