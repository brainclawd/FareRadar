from __future__ import annotations

import random
from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass
from datetime import date, datetime, timedelta
from typing import Any

import httpx

from ..config import settings
from ..models import CabinClass


@dataclass
class FlightSearchParams:
    origin: str
    destination: str
    departure_date: date
    return_date: date | None = None
    adults: int = 1
    cabin_class: CabinClass = CabinClass.economy
    max_price: int | None = None
    currency_code: str = "USD"
    max_results: int = 20
    non_stop: bool = False


@dataclass
class FlightResult:
    provider: str
    origin: str
    destination: str
    departure_date: date
    return_date: date | None
    airline: str
    cabin_class: CabinClass
    price: int
    currency_code: str = "USD"
    deep_link: str | None = None
    raw: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["raw"] = payload["raw"] or {}
        return payload


class FlightProviderError(RuntimeError):
    pass


class ProviderNotConfiguredError(FlightProviderError):
    pass


class FlightProvider(ABC):
    name: str = "base"

    @abstractmethod
    def is_configured(self) -> bool:
        raise NotImplementedError

    @abstractmethod
    def search(self, params: FlightSearchParams) -> list[FlightResult]:
        raise NotImplementedError

    def status(self) -> dict[str, Any]:
        return {
            "provider": self.name,
            "configured": self.is_configured(),
        }


class MockFlightProvider(FlightProvider):
    name = "mock"
    AIRLINES = ["Delta", "United", "ANA", "Lufthansa", "Iberia", "Air France"]

    def is_configured(self) -> bool:
        return True

    def search(self, params: FlightSearchParams) -> list[FlightResult]:
        dep = params.departure_date
        ret = params.return_date or (dep + timedelta(days=random.randint(5, 12)))

        baseline = {
            "NRT": 1050,
            "FCO": 880,
            "BCN": 780,
            "CDG": 840,
            "BKK": 1150,
        }.get(params.destination, 700)

        cabin_multiplier = {
            CabinClass.economy: 1.0,
            CabinClass.premium_economy: 1.35,
            CabinClass.business: 2.8,
            CabinClass.first: 4.5,
        }[params.cabin_class]

        normal_price = int(baseline * cabin_multiplier)
        anomaly = random.random() < 0.15
        price = int(normal_price * (random.uniform(0.32, 0.58) if anomaly else random.uniform(0.80, 1.15)))

        return [
            FlightResult(
                provider=self.name,
                origin=params.origin,
                destination=params.destination,
                departure_date=dep,
                return_date=ret,
                airline=random.choice(self.AIRLINES),
                cabin_class=params.cabin_class,
                price=price,
                currency_code=params.currency_code,
                raw={"simulated": True},
            )
        ]


class AmadeusProvider(FlightProvider):
    name = "amadeus"

    def __init__(self) -> None:
        self.base_url = settings.amadeus_base_url.rstrip("/")
        self.client_id = settings.amadeus_client_id
        self.client_secret = settings.amadeus_client_secret
        self._access_token: str | None = None
        self._access_token_expires_at: datetime | None = None

    def is_configured(self) -> bool:
        return bool(self.client_id and self.client_secret)

    def status(self) -> dict[str, Any]:
        return {
            "provider": self.name,
            "configured": self.is_configured(),
            "base_url": self.base_url,
        }

    def _ensure_configured(self) -> None:
        if not self.is_configured():
            raise ProviderNotConfiguredError("Amadeus credentials are not configured")

    def _token_is_valid(self) -> bool:
        if not self._access_token or not self._access_token_expires_at:
            return False
        return datetime.utcnow() < (self._access_token_expires_at - timedelta(seconds=60))

    def _authenticate(self) -> str:
        self._ensure_configured()
        if self._token_is_valid():
            return self._access_token  # type: ignore[return-value]

        response = httpx.post(
            f"{self.base_url}/v1/security/oauth2/token",
            data={
                "grant_type": "client_credentials",
                "client_id": self.client_id,
                "client_secret": self.client_secret,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=30.0,
        )
        if response.status_code >= 400:
            raise FlightProviderError(f"Amadeus auth failed: {response.status_code} {response.text}")

        payload = response.json()
        self._access_token = payload["access_token"]
        expires_in = int(payload.get("expires_in", 1800))
        self._access_token_expires_at = datetime.utcnow() + timedelta(seconds=expires_in)
        return self._access_token

    @staticmethod
    def _travel_class(cabin_class: CabinClass) -> str:
        return {
            CabinClass.economy: "ECONOMY",
            CabinClass.premium_economy: "PREMIUM_ECONOMY",
            CabinClass.business: "BUSINESS",
            CabinClass.first: "FIRST",
        }[cabin_class]

    def search(self, params: FlightSearchParams) -> list[FlightResult]:
        token = self._authenticate()
        query: dict[str, Any] = {
            "originLocationCode": params.origin,
            "destinationLocationCode": params.destination,
            "departureDate": params.departure_date.isoformat(),
            "adults": params.adults,
            "max": params.max_results,
            "travelClass": self._travel_class(params.cabin_class),
            "currencyCode": params.currency_code,
            "nonStop": str(params.non_stop).lower(),
        }
        if params.return_date:
            query["returnDate"] = params.return_date.isoformat()
        if params.max_price is not None:
            query["maxPrice"] = params.max_price

        response = httpx.get(
            f"{self.base_url}/v2/shopping/flight-offers",
            params=query,
            headers={"Authorization": f"Bearer {token}"},
            timeout=45.0,
        )
        if response.status_code >= 400:
            raise FlightProviderError(f"Amadeus search failed: {response.status_code} {response.text}")

        payload = response.json()
        offers = payload.get("data", [])
        dictionaries = payload.get("dictionaries", {})
        carriers = dictionaries.get("carriers", {})
        return [self._parse_offer(offer, carriers, params.cabin_class) for offer in offers]

    def _parse_offer(self, offer: dict[str, Any], carriers: dict[str, str], requested_cabin: CabinClass) -> FlightResult:
        itineraries = offer.get("itineraries", [])
        if not itineraries:
            raise FlightProviderError("Amadeus response missing itineraries")

        outbound = itineraries[0]
        outbound_segments = outbound.get("segments", [])
        if not outbound_segments:
            raise FlightProviderError("Amadeus response missing outbound segments")

        first_segment = outbound_segments[0]
        last_outbound_segment = outbound_segments[-1]

        return_itinerary = itineraries[1] if len(itineraries) > 1 else None
        return_date = None
        if return_itinerary:
            return_segments = return_itinerary.get("segments", [])
            if return_segments:
                return_date = datetime.fromisoformat(return_segments[0]["departure"]["at"]).date()

        validating_carrier = offer.get("validatingAirlineCodes", [first_segment.get("carrierCode", "")])[0]
        airline = carriers.get(validating_carrier, validating_carrier or "Unknown")

        departure_date = datetime.fromisoformat(first_segment["departure"]["at"]).date()
        destination = last_outbound_segment["arrival"]["iataCode"]
        origin = first_segment["departure"]["iataCode"]

        deep_link = None
        if isinstance(offer.get("self"), str):
            deep_link = offer["self"]

        return FlightResult(
            provider=self.name,
            origin=origin,
            destination=destination,
            departure_date=departure_date,
            return_date=return_date,
            airline=airline,
            cabin_class=requested_cabin,
            price=int(round(float(offer["price"]["grandTotal"]))),
            currency_code=offer["price"].get("currency", "USD"),
            deep_link=deep_link,
            raw=offer,
        )


class KiwiTequilaProvider(FlightProvider):
    name = "kiwi"

    def __init__(self) -> None:
        self.base_url = settings.kiwi_base_url.rstrip("/")
        self.api_key = settings.kiwi_api_key

    def is_configured(self) -> bool:
        return bool(self.api_key)

    def status(self) -> dict[str, Any]:
        return {
            "provider": self.name,
            "configured": self.is_configured(),
            "base_url": self.base_url,
        }

    def _ensure_configured(self) -> None:
        if not self.is_configured():
            raise ProviderNotConfiguredError("Kiwi API key is not configured")

    @staticmethod
    def _cabin_value(cabin_class: CabinClass) -> str:
        return {
            CabinClass.economy: "M",
            CabinClass.premium_economy: "W",
            CabinClass.business: "C",
            CabinClass.first: "F",
        }[cabin_class]

    def search(self, params: FlightSearchParams) -> list[FlightResult]:
        self._ensure_configured()
        query: dict[str, Any] = {
            "fly_from": params.origin,
            "fly_to": params.destination,
            "date_from": params.departure_date.strftime("%d/%m/%Y"),
            "date_to": params.departure_date.strftime("%d/%m/%Y"),
            "curr": params.currency_code,
            "adults": params.adults,
            "limit": params.max_results,
            "selected_cabins": self._cabin_value(params.cabin_class),
            "max_stopovers": 0 if params.non_stop else 2,
            "sort": "price",
        }
        if params.return_date:
            query["return_from"] = params.return_date.strftime("%d/%m/%Y")
            query["return_to"] = params.return_date.strftime("%d/%m/%Y")
        if params.max_price is not None:
            query["price_to"] = params.max_price

        response = httpx.get(
            f"{self.base_url}/v2/search",
            params=query,
            headers={"apikey": self.api_key},
            timeout=45.0,
        )
        if response.status_code >= 400:
            raise FlightProviderError(f"Kiwi search failed: {response.status_code} {response.text}")

        payload = response.json()
        data = payload.get("data", [])
        return [self._parse_offer(offer, params.cabin_class) for offer in data]

    def _parse_offer(self, offer: dict[str, Any], requested_cabin: CabinClass) -> FlightResult:
        route = offer.get("route") or []
        if not route:
            raise FlightProviderError("Kiwi response missing route information")

        outbound_first = route[0]
        departure_date = datetime.utcfromtimestamp(outbound_first["dTimeUTC"]).date()
        return_date = None
        if offer.get("return_duration") and len(route) > 1:
            inbound_segments = [seg for seg in route if seg.get("return") == 1]
            if inbound_segments:
                return_date = datetime.utcfromtimestamp(inbound_segments[0]["dTimeUTC"]).date()

        return FlightResult(
            provider=self.name,
            origin=offer.get("flyFrom", outbound_first.get("flyFrom")),
            destination=offer.get("flyTo", route[-1].get("flyTo")),
            departure_date=departure_date,
            return_date=return_date,
            airline=offer.get("airlines", ["Unknown"])[0],
            cabin_class=requested_cabin,
            price=int(offer["price"]),
            currency_code=offer.get("conversion", {}).keys().__iter__().__next__() if offer.get("conversion") else "USD",
            deep_link=offer.get("deep_link") or offer.get("booking_token"),
            raw=offer,
        )


def get_provider(provider_name: str | None = None) -> FlightProvider:
    selected = (provider_name or settings.flight_provider or "mock").strip().lower()
    providers: dict[str, FlightProvider] = {
        "mock": MockFlightProvider(),
        "amadeus": AmadeusProvider(),
        "kiwi": KiwiTequilaProvider(),
    }
    if selected not in providers:
        raise FlightProviderError(f"Unknown provider '{selected}'")
    return providers[selected]


def provider_statuses() -> list[dict[str, Any]]:
    return [
        get_provider("mock").status(),
        get_provider("amadeus").status(),
        get_provider("kiwi").status(),
    ]
