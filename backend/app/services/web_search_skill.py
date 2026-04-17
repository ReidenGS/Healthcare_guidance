from __future__ import annotations

import requests

from app.core.config import get_effective_tavily_key

TAVILY_SEARCH_URL = 'https://api.tavily.com/search'


def _tavily_search(query: str, max_results: int = 3) -> str:
    """Internal helper: run a Tavily query and return joined snippets."""
    tavily_key = get_effective_tavily_key()
    if not tavily_key:
        return ''
    try:
        resp = requests.post(
            TAVILY_SEARCH_URL,
            json={
                'api_key': tavily_key,
                'query': query,
                'search_depth': 'basic',
                'max_results': max_results,
                'include_answer': False,
            },
            timeout=6,
        )
        resp.raise_for_status()
        data = resp.json()
        snippets = [
            item.get('content', '').replace('\n', ' ').strip()
            for item in data.get('results', [])[:max_results]
            if item.get('content', '').strip()
        ]
        return ' | '.join(snippets)
    except Exception:
        return ''


def search_symptom_reference(symptoms: str) -> str:
    """Query Tavily for symptom-to-department reference snippets.

    Used to enrich the GPT triage prompt with external routing context.
    Returns empty string when TAVILY_API_KEY is not configured or the
    request fails; callers can safely treat it as optional context.
    """
    query = f'{symptoms} which medical specialist department or specialty to visit'
    return _tavily_search(query)


def search_redflag_online(symptoms: str) -> str:
    """Query Tavily specifically for red-flag / emergency warning signs.

    Focuses on: "are these symptoms dangerous / requiring immediate ER care?"
    Separate from ``search_symptom_reference`` which targets department routing.
    Returns empty string when Tavily is not configured or the request fails.
    """
    query = (
        f'{symptoms} red flag symptoms emergency warning signs '
        'when to go to emergency room immediately life threatening'
    )
    return _tavily_search(query)
