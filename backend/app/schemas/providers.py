from __future__ import annotations

from typing import Optional
from pydantic import BaseModel


class LocationInput(BaseModel):
    # City-based search (preferred when GPS is unavailable)
    city: str = ''
    # Optional lat/lng for precise GPS-based search
    lat: Optional[float] = None
    lng: Optional[float] = None
    radius_km: float = 10


class SearchProvidersRequest(BaseModel):
    session_id: str
    care_path: str
    location: LocationInput


class ProviderItem(BaseModel):
    provider_id: str
    name: str
    provider_type: str
    distance_km: float
    next_available_slot: Optional[str] = None
    address: Optional[str] = None


class SearchProvidersResponse(BaseModel):
    session_id: str
    status: str
    providers: list[ProviderItem]
