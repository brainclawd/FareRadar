
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "postgresql+psycopg://postgres:postgres@localhost:5432/fareradar"
    redis_url: str = "redis://localhost:6379/0"

    flight_provider: str = "mock"

    amadeus_base_url: str = "https://test.api.amadeus.com"
    amadeus_client_id: str | None = None
    amadeus_client_secret: str | None = None

    kiwi_base_url: str = "https://tequila-api.kiwi.com"
    kiwi_api_key: str | None = None

    # Celery
    celery_broker_url: str | None = None
    celery_result_backend: str | None = None
    celery_task_always_eager: bool = False
    celery_task_eager_propagates: bool = True

    # Notifications
    notifications_from_email: str = "deals@fareradar.local"
    cors_allowed_origins: list[str] = Field(default_factory=lambda: ["http://localhost:3000", "http://127.0.0.1:3000"])
    app_env: str = "development"

    # Provider hardening
    provider_request_timeout_seconds: float = 20.0
    provider_max_retries: int = 2
    provider_backoff_seconds: float = 0.5
    provider_failure_cooldown_minutes: int = 15
    provider_fallback_order: list[str] = Field(default_factory=lambda: ["amadeus", "kiwi", "mock"])

    # Feed quality
    deals_featured_cache_ttl_seconds: int = 120
    deals_business_class_bonus: float = 8.0
    deals_freshness_half_life_hours: int = 12
    deals_popular_destinations: list[str] = Field(default_factory=lambda: ["NRT", "HND", "FCO", "BCN", "CDG", "BKK"])

    default_adults: int = 1
    default_max_results: int = 20
    scanner_origins: list[str] = Field(default_factory=lambda: ["SLC", "LAX", "LAS", "DEN"])
    scanner_destinations: list[str] = Field(default_factory=lambda: ["NRT", "FCO", "BCN", "CDG", "BKK"])
    scanner_window_start_days: int = 30
    scanner_window_end_days: int = 180
    scanner_trip_length_min: int = 5
    scanner_trip_length_max: int = 10

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
