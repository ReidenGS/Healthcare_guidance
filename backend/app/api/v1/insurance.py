from fastapi import APIRouter, HTTPException

from app.schemas.insurance import InsuranceCheckRequest, InsuranceCheckResponse
from app.services.insurance_service import estimate_insurance_from_mock_db
from app.services.store import store

router = APIRouter(prefix='/insurance', tags=['insurance'])


@router.post('/check', response_model=InsuranceCheckResponse)
def check_insurance(payload: InsuranceCheckRequest) -> InsuranceCheckResponse:
    session = store.sessions.get(payload.session_id)
    if not session:
        raise HTTPException(status_code=404, detail='Session not found')

    triage_result = session.get('recommendation') or {}
    providers = session.get('last_provider_results') or []
    selected_provider = next(
        (p for p in providers if str(p.get('provider_id', '')) == str(payload.provider_id)),
        {},
    )

    result = estimate_insurance_from_mock_db(
        plan=payload.insurance_plan,
        provider_id=str(payload.provider_id),
        provider_name=str(selected_provider.get('name') or ''),
        provider_address=str(selected_provider.get('address') or ''),
        triage_result=triage_result,
    )

    record = {
        'session_id': payload.session_id,
        'status': 'INSURANCE_RESULT',
        'provider_id': payload.provider_id,
        'insurance_plan': payload.insurance_plan,
        **result,
    }
    store.insurance_checks[payload.session_id] = record
    session['status'] = 'INSURANCE_RESULT'
    session['timeline'].append({'event': 'INSURANCE_CHECKED', 'at': store.now_iso()})

    return InsuranceCheckResponse(**record)
