
from __future__ import annotations

import time
from datetime import datetime, timedelta
from typing import Iterable

from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from ..config import settings
from ..models import ProviderHealthEvent
from .provider import FlightProviderError, FlightSearchParams, FlightResult, get_provider


def log_provider_event(
    db: Session,
    provider: str,
    status: str,
    *,
    operation: str = "search",
    latency_ms: int | None = None,
    error_message: str | None = None,
    context: dict | None = None,
) -> ProviderHealthEvent:
    event = ProviderHealthEvent(
        provider=provider,
        status=status,
        operation=operation,
        latency_ms=latency_ms,
        error_message=error_message,
        context_json=context or {},
    )
    db.add(event)
    db.commit()
    return event


def provider_on_cooldown(db: Session, provider: str) -> bool:
    cutoff = datetime.utcnow() - timedelta(minutes=settings.provider_failure_cooldown_minutes)
    failed_recent = db.scalar(
        select(func.count())
        .select_from(ProviderHealthEvent)
        .where(
            ProviderHealthEvent.provider == provider,
            ProviderHealthEvent.status == "failed",
            ProviderHealthEvent.created_at >= cutoff,
        )
    ) or 0
    ok_recent = db.scalar(
        select(func.count())
        .select_from(ProviderHealthEvent)
        .where(
            ProviderHealthEvent.provider == provider,
            ProviderHealthEvent.status == "ok",
            ProviderHealthEvent.created_at >= cutoff,
        )
    ) or 0
    return failed_recent >= 3 and ok_recent == 0


def _fallback_candidates(primary_provider: str | None) -> list[str]:
    ordered: list[str] = []
    if primary_provider:
        ordered.append(primary_provider)
    for name in settings.provider_fallback_order:
        if name not in ordered:
            ordered.append(name)
    return ordered


def search_with_resilience(
    db: Session,
    *,
    provider_name: str | None,
    params: FlightSearchParams,
    operation: str = "search",
) -> tuple[list[FlightResult], str]:
    providers = _fallback_candidates(provider_name)
    last_error: Exception | None = None

    for provider_name in providers:
        provider = get_provider(provider_name)
        if not provider.is_configured():
            continue
        if provider_on_cooldown(db, provider.name):
            continue

        for attempt in range(settings.provider_max_retries + 1):
            started = time.monotonic()
            try:
                offers = provider.search(params)
                latency_ms = int((time.monotonic() - started) * 1000)
                log_provider_event(
                    db,
                    provider.name,
                    "ok",
                    operation=operation,
                    latency_ms=latency_ms,
                    context={
                        "origin": params.origin,
                        "destination": params.destination,
                        "attempt": attempt + 1,
                        "offers": len(offers),
                    },
                )
                return offers, provider.name
            except FlightProviderError as exc:
                latency_ms = int((time.monotonic() - started) * 1000)
                last_error = exc
                log_provider_event(
                    db,
                    provider.name,
                    "failed",
                    operation=operation,
                    latency_ms=latency_ms,
                    error_message=str(exc),
                    context={
                        "origin": params.origin,
                        "destination": params.destination,
                        "attempt": attempt + 1,
                    },
                )
                if attempt < settings.provider_max_retries:
                    time.sleep(settings.provider_backoff_seconds * (attempt + 1))
                else:
                    break

    raise FlightProviderError(str(last_error or "No configured providers available"))
