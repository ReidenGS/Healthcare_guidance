from __future__ import annotations

from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI

from app.core.config import get_settings
from app.services.google_maps_skill import search_nearby_clinics
from app.services.provider_service import list_providers

# ---------------------------------------------------------------------------
# Map specific department names to sensible Google Maps search keywords.
# This ensures searches like "Ophthalmology clinic" instead of just "specialist".
# ---------------------------------------------------------------------------
_DEPARTMENT_QUERY_MAP: dict[str, str] = {
    'Emergency Department': 'emergency room hospital ER',
    'Cardiology': 'cardiology heart specialist clinic',
    'Neurology': 'neurology neurologist clinic',
    'Orthopedics': 'orthopedic orthopedics bone joint clinic',
    'Gastroenterology': 'gastroenterology GI digestive clinic',
    'Pulmonology': 'pulmonology respiratory lung clinic',
    'Ophthalmology': 'ophthalmology eye clinic eye doctor',
    'Dermatology': 'dermatology skin clinic dermatologist',
    'ENT (Ear, Nose & Throat)': 'ENT ear nose throat otolaryngology clinic',
    'Urology': 'urology urologist kidney bladder clinic',
    'Gynecology / OB-GYN': 'gynecology OBGYN women health clinic',
    'Psychiatry / Mental Health': 'psychiatry mental health behavioral clinic',
    'Endocrinology': 'endocrinology diabetes thyroid hormone clinic',
    'Rheumatology': 'rheumatology arthritis autoimmune clinic',
    'Nephrology': 'nephrology kidney disease clinic',
    'Hematology / Oncology': 'oncology cancer hematology center',
    'Infectious Disease': 'infectious disease clinic',
    'Allergy & Immunology': 'allergy immunology clinic',
    'Internal Medicine': 'internal medicine doctor clinic',
    'Primary Care': 'primary care family doctor clinic',
    'Urgent Care': 'urgent care clinic',
    'Pediatrics': 'pediatrics children doctor clinic',
}

_CARE_PATH_FALLBACK: dict[str, str] = {
    'ER': 'emergency room hospital',
    'URGENT_CARE': 'urgent care clinic',
    'PRIMARY_CARE': 'primary care clinic',
    'SPECIALIST': 'specialist clinic',
}


def _build_search_query(triage_result: dict[str, Any]) -> str:
    """Build a specific Google Maps query from department + care_path."""
    department = (triage_result.get('department') or '').strip()
    care_path = (triage_result.get('care_path') or 'PRIMARY_CARE').strip()

    # Prefer department-specific query; fall back to care_path mapping
    if department in _DEPARTMENT_QUERY_MAP:
        return _DEPARTMENT_QUERY_MAP[department]

    # Fuzzy match: department string contains a known key (partial match)
    dept_lower = department.lower()
    for key, query in _DEPARTMENT_QUERY_MAP.items():
        if key.lower() in dept_lower or dept_lower in key.lower():
            return query

    return _CARE_PATH_FALLBACK.get(care_path, 'clinic hospital')


class NavigationAgent:
    def __init__(self) -> None:
        settings = get_settings()
        self.enabled = bool(settings.gemini_api_key)
        self.model = settings.gemini_model
        self.client = (
            ChatGoogleGenerativeAI(
                model=settings.gemini_model,
                google_api_key=settings.gemini_api_key,
                temperature=0,
            )
            if self.enabled
            else None
        )

    def _llm_hint(self, triage_result: dict[str, Any], objective: str) -> str:
        if not self.enabled or self.client is None:
            return 'Gemini fallback mode (GEMINI_API_KEY not configured).'

        try:
            msg = self.client.invoke(
                [
                    SystemMessage(
                        content='You are a healthcare navigation assistant. Return short actionable guidance.'
                    ),
                    HumanMessage(content=f'Objective: {objective}. Triage result: {triage_result}'),
                ]
            )
            return msg.content if isinstance(msg.content, str) else str(msg.content)
        except Exception:
            return 'Gemini fallback mode due to model call error.'

    def find_providers(
        self,
        triage_result: dict[str, Any],
        city: str = '',
        lat: float | None = None,
        lng: float | None = None,
        radius_km: float = 10,
    ) -> list[dict[str, Any]]:
        # Build a department-specific query string
        base_query = _build_search_query(triage_result)

        # Append city to query so Maps returns results in the right area
        location_suffix = f'in {city}' if city else ''
        full_query = f'{base_query} {location_suffix}'.strip()

        # Optionally let Gemini refine the query
        hint = self._llm_hint(
            triage_result,
            f'Suggest a concise Google Maps search query for "{full_query}"',
        )
        search_query = (
            full_query
            if hint.startswith('Gemini fallback')
            else f'{full_query} {hint[:60]}'.strip()
        )

        gm_providers = search_nearby_clinics(
            query=search_query,
            lat=lat,
            lng=lng,
            city=city,
            radius_km=radius_km,
        )
        if gm_providers:
            return gm_providers

        # Fallback to local directory
        return list_providers()

navigation_agent = NavigationAgent()
