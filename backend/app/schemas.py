
from datetime import date, datetime
from pydantic import BaseModel, Field, EmailStr, field_validator
from .models import CabinClass, DestinationType, DealStatus, JobStatus


class HealthResponse(BaseModel):
    status: str


class UserCreate(BaseModel):
    email: EmailStr
    plan: str = "free"


class PreferenceCreate(BaseModel):
    user_id: str
    origin_airports: list[str] = Field(min_length=1)
    destination_type: DestinationType
    destinations: list[str] = Field(default_factory=list)
    max_price: int = Field(gt=0)
    cabin_class: CabinClass
    date_flexibility: str = "exact"
    metadata_json: dict = Field(default_factory=dict)


class PreferenceRead(PreferenceCreate):
    id: int
    created_at: datetime

    model_config = {"from_attributes": True}


class AlertCreate(BaseModel):
    user_id: str
    name: str = Field(min_length=1, max_length=120)
    origin_airports: list[str] = Field(min_length=1)
    destination_type: DestinationType
    destinations: list[str] = Field(default_factory=list)
    max_price: int | None = Field(default=None, gt=0)
    cabin_class: CabinClass
    date_flexibility: str = "exact"
    min_discount_percent: float = Field(default=35.0, ge=0, le=100)
    channels: list[str] = Field(default_factory=lambda: ["email"])
    is_active: bool = True
    metadata_json: dict = Field(default_factory=dict)


class AlertRead(AlertCreate):
    id: int
    created_at: datetime

    model_config = {"from_attributes": True}


class DealRead(BaseModel):
    id: int
    origin: str
    destination: str
    price: int
    normal_price: int
    discount_percent: float
    airline: str
    departure_date: date
    return_date: date
    cabin_class: CabinClass
    provider: str = "mock"
    deep_link: str | None = None
    deal_score: float
    feed_score: float = 0
    quality_factors_json: dict = Field(default_factory=dict)
    status: DealStatus = DealStatus.validated
    created_at: datetime

    model_config = {"from_attributes": True}


class CandidateDealRead(BaseModel):
    id: int
    flight_price_id: int
    origin: str
    destination: str
    departure_date: date
    return_date: date
    airline: str
    cabin_class: CabinClass
    price: int
    expected_price: int
    discount_percent: float
    z_score: float
    sudden_drop_amount: int
    rarity_score: float
    score: float
    status: DealStatus
    created_at: datetime

    model_config = {"from_attributes": True}


class FlightSearchRequest(BaseModel):
    origin: str = Field(min_length=3, max_length=8)
    destination: str = Field(min_length=3, max_length=8)
    departure_date: date
    return_date: date | None = None
    adults: int = Field(default=1, ge=1, le=9)
    cabin_class: CabinClass = CabinClass.economy
    max_price: int | None = Field(default=None, gt=0)
    currency_code: str = Field(default="USD", min_length=3, max_length=3)
    max_results: int = Field(default=20, ge=1, le=50)
    non_stop: bool = False

    @field_validator("origin", "destination", "currency_code")
    @classmethod
    def normalize_code(cls, value: str) -> str:
        return value.strip().upper()

    @field_validator("return_date")
    @classmethod
    def validate_return_date(cls, value: date | None, info):
        departure = info.data.get("departure_date")
        if value is not None and departure is not None and value < departure:
            raise ValueError("return_date must be on or after departure_date")
        return value


class FlightOfferRead(BaseModel):
    provider: str
    origin: str
    destination: str
    departure_date: date
    return_date: date | None = None
    airline: str
    cabin_class: CabinClass
    price: int
    currency_code: str = "USD"
    deep_link: str | None = None
    raw: dict = Field(default_factory=dict)


class ProviderStatus(BaseModel):
    provider: str
    configured: bool
    base_url: str | None = None


class RouteBucketRead(BaseModel):
    id: int
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
    last_scanned_at: datetime | None = None
    next_scan_at: datetime | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class ScanPlanRequest(BaseModel):
    origins: list[str] = Field(default_factory=list)
    destinations: list[str] = Field(default_factory=list)
    cabins: list[CabinClass] = Field(default_factory=lambda: [CabinClass.economy, CabinClass.business])
    departure_months: int = Field(default=3, ge=1, le=12)
    trip_length_min: int = Field(default=5, ge=1, le=30)
    trip_length_max: int = Field(default=10, ge=1, le=60)


class ScanRunRequest(BaseModel):
    origins: list[str] = Field(default_factory=list)
    destinations: list[str] = Field(default_factory=list)
    cabins: list[CabinClass] = Field(default_factory=lambda: [CabinClass.economy])
    departure_start: date | None = None
    departure_end: date | None = None
    trip_length_min: int = Field(default=5, ge=1, le=30)
    trip_length_max: int = Field(default=10, ge=1, le=60)
    max_results: int = Field(default=3, ge=1, le=20)


class ScanJobRead(BaseModel):
    id: int
    provider: str
    origin: str
    destination: str
    cabin_class: CabinClass
    departure_start: date
    departure_end: date
    trip_length_min: int
    trip_length_max: int
    priority_score: float
    status: JobStatus
    error_message: str | None = None
    queued_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None

    model_config = {"from_attributes": True}


class QueuePublishResponse(BaseModel):
    queued: int
    detail: str


class AlertMatchPreview(BaseModel):
    alert_id: int
    alert_name: str
    matched: bool
    reasons: list[str]
    channels: list[str] = Field(default_factory=list)


class ProviderHealthRead(BaseModel):
    provider: str
    ok_events: int
    failed_events: int
    last_status: str | None = None
    last_error_message: str | None = None
    avg_latency_ms: float | None = None
    last_event_at: datetime | None = None


class AdminOverview(BaseModel):
    queued_jobs: int
    running_jobs: int
    failed_jobs_24h: int
    candidate_deals: int
    validated_deals: int
    active_alerts: int
    notifications_sent_24h: int


class DealFunnelRead(BaseModel):
    candidates_total: int
    candidates_validated: int
    candidates_expired: int
    validated_deals_total: int
