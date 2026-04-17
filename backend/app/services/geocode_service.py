from __future__ import annotations

import re
from typing import Any

import requests

from app.core.config import get_effective_google_maps_key


GOOGLE_GEOCODE_URL = 'https://maps.googleapis.com/maps/api/geocode/json'


_FALLBACK_CITY_COORDS: dict[str, tuple[float, float, str]] = {
    'jersey city': (40.7178, -74.0431, 'Jersey City, NJ, USA'),
    'new jersey': (40.0583, -74.4057, 'New Jersey, USA'),
    'new york': (40.7128, -74.0060, 'New York, NY, USA'),
    'nyc': (40.7128, -74.0060, 'New York, NY, USA'),
    'san francisco': (37.7749, -122.4194, 'San Francisco, CA, USA'),
    'los angeles': (34.0522, -118.2437, 'Los Angeles, CA, USA'),
    'chicago': (41.8781, -87.6298, 'Chicago, IL, USA'),
    'boston': (42.3601, -71.0589, 'Boston, MA, USA'),
    'seattle': (47.6062, -122.3321, 'Seattle, WA, USA'),
}

ZIP5_RE = re.compile(r'^\d{5}$')


def _extract_zip5(text: str) -> str | None:
    q = (text or '').strip()
    if not q:
        return None
    # exact zip input
    if ZIP5_RE.match(q):
        return q
    # any zip token in free text
    m = re.search(r'\b(\d{5})\b', q)
    return m.group(1) if m else None


def _geocode_zip_with_google(zip5: str, api_key: str) -> dict[str, Any] | None:
    try:
        # Prefer postal-code geocoding instead of free-text interpolation.
        resp = requests.get(
            GOOGLE_GEOCODE_URL,
            params={
                'components': f'postal_code:{zip5}|country:US',
                'key': api_key,
            },
            timeout=8,
        )
        resp.raise_for_status()
        data = resp.json()
        first = (data.get('results') or [None])[0]
        if first and first.get('geometry', {}).get('location'):
            loc = first['geometry']['location']
            return {
                'normalized_address': first.get('formatted_address', f'{zip5}, USA'),
                'lat': float(loc['lat']),
                'lng': float(loc['lng']),
                'source': 'google_zip',
            }
    except Exception:
        return None
    return None


def _geocode_zip_with_zippopotam(zip5: str) -> dict[str, Any] | None:
    try:
        resp = requests.get(f'https://api.zippopotam.us/us/{zip5}', timeout=6)
        if resp.status_code != 200:
            return None
        data = resp.json()
        places = data.get('places') or []
        first = places[0] if places else None
        if not first:
            return None
        lat = float(first.get('latitude'))
        lng = float(first.get('longitude'))
        city = first.get('place name', '')
        state = first.get('state abbreviation', '') or first.get('state', '')
        normalized = f'{zip5}, {city}, {state}, USA'.replace(' ,', ',')
        return {
            'normalized_address': normalized,
            'lat': lat,
            'lng': lng,
            'source': 'zippopotam_zip',
        }
    except Exception:
        return None

def _fallback_match(query: str) -> dict[str, Any] | None:
    q = (query or '').strip().lower()
    if not q:
        return None

    for key, (lat, lng, addr) in _FALLBACK_CITY_COORDS.items():
        if key in q:
            return {
                'normalized_address': addr,
                'lat': lat,
                'lng': lng,
                'source': 'fallback',
            }

    return None


def geocode_query(query: str) -> dict[str, Any]:
    cleaned = (query or '').strip()
    if len(cleaned) < 2:
        raise ValueError('Unable to geocode location from empty input. Please provide address, city, ZIP, or allow GPS.')

    maps_key = get_effective_google_maps_key()

    # ZIP-first path: always try real ZIP geocoding, never guessed mappings.
    zip5 = _extract_zip5(cleaned)
    if zip5:
        if maps_key:
            zip_google = _geocode_zip_with_google(zip5, maps_key)
            if zip_google:
                return zip_google
        zip_public = _geocode_zip_with_zippopotam(zip5)
        if zip_public:
            return zip_public

    if maps_key:
        try:
            resp = requests.get(
                GOOGLE_GEOCODE_URL,
                params={
                    'address': cleaned,
                    'key': maps_key,
                },
                timeout=8,
            )
            resp.raise_for_status()
            data = resp.json()
            first = (data.get('results') or [None])[0]
            if first and first.get('geometry', {}).get('location'):
                location = first['geometry']['location']
                return {
                    'normalized_address': first.get('formatted_address', cleaned),
                    'lat': float(location['lat']),
                    'lng': float(location['lng']),
                    'source': 'google',
                }
        except Exception:
            pass

    fallback = _fallback_match(cleaned)
    if fallback:
        return fallback

    raise ValueError('Unable to geocode location. Please provide a more specific address, city, or ZIP code, or allow GPS.')
