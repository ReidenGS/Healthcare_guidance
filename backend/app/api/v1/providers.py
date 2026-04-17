from fastapi import APIRouter, HTTPException

from app.agents.navigation_agent import navigation_agent
from app.schemas.providers import SearchProvidersRequest, SearchProvidersResponse
from app.services.store import store

router = APIRouter(prefix='/providers', tags=['providers'])


@router.post('/search', response_model=SearchProvidersResponse)
def search(payload: SearchProvidersRequest) -> SearchProvidersResponse:
    session = store.sessions.get(payload.session_id)
    if not session:
        raise HTTPException(status_code=404, detail='Session not found')

    triage_result = session.get('recommendation') or {}
    providers = navigation_agent.find_providers(
        triage_result=triage_result,
        city=payload.location.city or '',
        lat=payload.location.lat,
        lng=payload.location.lng,
        radius_km=payload.location.radius_km,
    )
    session['last_provider_results'] = providers
    session['status'] = 'PROVIDER_MATCHED'
    session['timeline'].append({'event': 'PROVIDERS_SEARCHED', 'at': store.now_iso()})

    return SearchProvidersResponse(
        session_id=payload.session_id,
        status='PROVIDER_MATCHED',
        providers=providers,
    )
