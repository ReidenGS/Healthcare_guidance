from __future__ import annotations

from typing import Any
import requests

from app.core.config import get_effective_google_maps_key


GOOGLE_TEXT_SEARCH_URL = 'https://maps.googleapis.com/maps/api/place/textsearch/json'


def search_nearby_clinics(
    query: str,
    lat: float | None = None,
    lng: float | None = None,
    city: str = '',
    radius_km: float = 10,
) -> list[dict[str, Any]]:
    maps_key = get_effective_google_maps_key()
    if not maps_key:
        return []

    # Build params — use lat/lng when available, otherwise rely on the city
    # already embedded in the query string (e.g. "eye clinic in San Francisco")
    params: dict[str, Any] = {
        'query': query,
        'radius': int(radius_km * 1000),
        'key': maps_key,
    }
    if lat is not None and lng is not None:
        params['location'] = f'{lat},{lng}'

    try:
        resp = requests.get(GOOGLE_TEXT_SEARCH_URL, params=params, timeout=8)
        resp.raise_for_status()
        data = resp.json()
    except Exception:
        return []

    providers: list[dict[str, Any]] = []
    for idx, item in enumerate(data.get('results', [])[:5], start=1):
        providers.append(
            {
                'provider_id': f'gm_{idx}_{item.get("place_id", "unknown")[:8]}',
                'name': item.get('name', 'Nearby provider'),
                'provider_type': 'clinic',
                'distance_km': round(idx * 1.7, 1),
                'next_available_slot': None,
                'address': item.get('formatted_address', ''),
            }
        )
    return providers
