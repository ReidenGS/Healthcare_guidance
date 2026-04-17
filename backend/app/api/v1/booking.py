from uuid import uuid4

from fastapi import APIRouter, HTTPException

from app.schemas.booking import BookingIntentRequest, BookingIntentResponse, SessionSummaryResponse
from app.services.provider_service import get_provider
from app.services.slot_service import get_or_init_slots, mark_slot_booked
from app.services.store import store

router = APIRouter(prefix='/booking', tags=['booking'])


def _resolve_provider(provider_id: str, session: dict) -> dict:
    """Find provider info from local DB first, then session cache, then stub."""
    # 1. Try local static DB
    local = get_provider(provider_id)
    if local:
        return local
    # 2. Try Google Maps results stored in session
    for p in session.get('last_provider_results') or []:
        if str(p.get('provider_id', '')) == str(provider_id):
            return p
    # 3. Stub — booking still succeeds for any real-world provider
    return {'provider_id': provider_id, 'name': 'Selected Provider', 'address': ''}


@router.get('/slots')
def get_provider_slots(provider_id: str = '') -> list[dict]:
    """Return all time slots for a provider from the simulated hospital DB.

    Slots are initialized on first access (stable per provider_id via deterministic seed)
    and updated in real-time as bookings are confirmed.
    """
    if not provider_id:
        raise HTTPException(status_code=422, detail='provider_id is required')
    return get_or_init_slots(provider_id, store)


@router.post('/intents', response_model=BookingIntentResponse)
def create_booking_intent(payload: BookingIntentRequest) -> BookingIntentResponse:
    session = store.sessions.get(payload.session_id)
    if not session:
        raise HTTPException(status_code=404, detail='Session not found')

    provider = _resolve_provider(payload.provider_id, session)

    # Mark the chosen slot as booked in the simulated hospital DB
    if payload.slot_id:
        success = mark_slot_booked(payload.provider_id, payload.slot_id, store)
        if not success:
            raise HTTPException(
                status_code=409,
                detail='This time slot has just been booked by someone else. Please go back and select another slot.',
            )

    booking_intent_id = f"book_int_{uuid4().hex[:8]}"
    instructions = [
        'Watch for SMS updates or call the clinic front desk to confirm the final slot.',
        'Bring your insurance card and a valid photo ID for your visit.',
    ]

    # Gather triage context for the booking record
    rec = session.get('recommendation') or {}
    booked_at = store.now_iso()

    record = {
        'booking_intent_id': booking_intent_id,
        'session_id': payload.session_id,
        'status': 'CONFIRMED',
        'provider_id': payload.provider_id,
        'provider_name': provider.get('name', ''),
        'provider_address': provider.get('address', ''),
        'preferred_time': payload.preferred_time,
        'patient_contact': payload.patient_contact.model_dump(),
        'department': rec.get('department', ''),
        'care_path': rec.get('care_path', ''),
        'instructions': instructions,
        'booked_at': booked_at,
    }

    store.booking_intents[payload.session_id] = record
    # Also push into global bookings list (mock provider DB)
    store.all_bookings.append(record)

    session['status'] = 'COMPLETED'
    session['selected_provider'] = provider
    session['timeline'].append({'event': 'BOOKING_INTENT_CREATED', 'at': booked_at})

    return BookingIntentResponse(
        booking_intent_id=booking_intent_id,
        session_id=payload.session_id,
        status='CONFIRMED',
        instructions=instructions,
    )


@router.get('/records')
def get_booking_records(phone: str = '') -> list[dict]:
    """Return all bookings for a given phone number (mock provider DB lookup)."""
    if not phone:
        return []
    normalized = phone.strip().replace('-', '').replace(' ', '')
    results = []
    for b in store.all_bookings:
        contact_phone = str(b.get('patient_contact', {}).get('phone', ''))
        if contact_phone.replace('-', '').replace(' ', '') == normalized:
            results.append(b)
    return results


@router.get('/sessions/{session_id}/summary', response_model=SessionSummaryResponse)
def session_summary(session_id: str) -> SessionSummaryResponse:
    session = store.sessions.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail='Session not found')

    booking = store.booking_intents.get(session_id)
    insurance = store.insurance_checks.get(session_id)

    return SessionSummaryResponse(
        session_id=session_id,
        status=session.get('status', 'INTAKE'),
        symptom_input=session.get('symptom_input', {}),
        recommendation=session.get('recommendation') or {},
        selected_provider=session.get('selected_provider'),
        insurance=insurance,
        booking_intent_id=booking['booking_intent_id'] if booking else None,
        instructions=booking['instructions'] if booking else [],
        timeline=session.get('timeline', []),
    )
