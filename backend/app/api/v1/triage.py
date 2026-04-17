from uuid import uuid4

from fastapi import APIRouter, HTTPException

from app.agents.triage_agent import triage_agent
from app.schemas.triage import (
    CreateSessionRequest,
    CreateSessionResponse,
    RecommendationFeedbackRequest,
    RecommendationFeedbackResponse,
    RecommendationResponse,
    SubmitAnswersRequest,
    SubmitAnswersResponse,
)
from app.schemas.booking import SessionSummaryResponse
from app.services.followup_memory import add_asked_symptoms, get_asked_symptoms, init_session
from app.services.store import store

DISCLAIMER = 'This is AI guidance, not a medical diagnosis.'
CONFIDENCE_TARGET_PERCENT = 80
MAX_FOLLOW_UP_ROUNDS = 8

router = APIRouter(prefix='/triage', tags=['triage'])


@router.post('/sessions', response_model=CreateSessionResponse)
def create_session(payload: CreateSessionRequest) -> CreateSessionResponse:
    session_id = f"sess_{uuid4().hex[:8]}"
    init_session(session_id)
    initial_analysis = triage_agent.assess(payload.symptom_input.model_dump(), answers=[])
    can_recommend_now = initial_analysis['confidence_percent'] > CONFIDENCE_TARGET_PERCENT
    questions = []
    if not can_recommend_now:
        questions = triage_agent.generate_follow_up_questions(
            payload.symptom_input.model_dump(),
            answers=[],
            round_index=1,
            asked_question_ids=[],
            banned_symptoms=get_asked_symptoms(session_id),
        )
        add_asked_symptoms(session_id, [q['label'] for q in questions])

    store.sessions[session_id] = {
        'session_id': session_id,
        'status': 'TRIAGE_READY' if can_recommend_now else 'FOLLOW_UP',
        'risk_level': initial_analysis['risk_level'],
        'confidence': initial_analysis['confidence'],
        'confidence_percent': initial_analysis['confidence_percent'],
        'user_profile': payload.user_profile.model_dump(),
        'symptom_input': payload.symptom_input.model_dump(),
        'questions': questions,
        'follow_up_target_percent': CONFIDENCE_TARGET_PERCENT,
        'follow_up_round': 1,
        'asked_question_ids': [q['question_id'] for q in questions],
        'recommendation': initial_analysis if can_recommend_now else None,
        'selected_provider': None,
        'timeline': [{'event': 'SESSION_CREATED', 'at': store.now_iso()}],
        'disclaimer': DISCLAIMER,
    }
    store.answers[session_id] = []
    return CreateSessionResponse(
        session_id=session_id,
        status='TRIAGE_READY' if can_recommend_now else 'FOLLOW_UP',
        risk_level=initial_analysis['risk_level'],
        confidence=initial_analysis['confidence'],
        confidence_percent=initial_analysis['confidence_percent'],
        questions=questions,
        disclaimer=DISCLAIMER,
    )


@router.post('/sessions/{session_id}/answers', response_model=SubmitAnswersResponse)
def submit_session_answers(session_id: str, payload: SubmitAnswersRequest) -> SubmitAnswersResponse:
    session = store.sessions.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail='Session not found')

    current_round = int(session.get('follow_up_round', 1))

    # ── "None of the above" branch ──────────────────────────────────────────
    # Patient said none of the listed symptoms apply → freeze confidence and
    # regenerate a fresh batch of non-overlapping questions immediately.
    if payload.none_of_above:
        # Freeze confidence at the value already stored for this session.
        frozen_confidence_percent = int(session.get('confidence_percent', 50))
        frozen_confidence = round(frozen_confidence_percent / 100, 2)
        frozen_risk = session.get('risk_level', 'LOW')

        if current_round < MAX_FOLLOW_UP_ROUNDS:
            next_round = current_round + 1
            asked_question_ids = list(session.get('asked_question_ids', []))
            questions = triage_agent.generate_follow_up_questions(
                session['symptom_input'],
                answers=store.answers.get(session_id, []),
                round_index=next_round,
                asked_question_ids=asked_question_ids,
                banned_symptoms=get_asked_symptoms(session_id),
            )
            if questions:
                add_asked_symptoms(session_id, [q['label'] for q in questions])
                session['status'] = 'FOLLOW_UP'
                session['follow_up_round'] = next_round
                session['questions'] = questions
                session['asked_question_ids'] = asked_question_ids + [q['question_id'] for q in questions]
                session['timeline'].append({'event': f'FOLLOW_UP_ROUND_{current_round}_NONE_OF_ABOVE', 'at': store.now_iso()})
                session['timeline'].append({'event': f'FOLLOW_UP_ROUND_{next_round}_GENERATED', 'at': store.now_iso()})
                return SubmitAnswersResponse(
                    session_id=session_id,
                    status='FOLLOW_UP',
                    confidence=frozen_confidence,
                    confidence_percent=frozen_confidence_percent,
                    risk_level=frozen_risk,
                    questions=questions,
                )

        # No more rounds available — proceed to recommendation with frozen confidence.
        rec = triage_agent.assess(session['symptom_input'], store.answers.get(session_id, []))
        # Override confidence so it doesn't jump upward.
        rec['confidence_percent'] = frozen_confidence_percent
        rec['confidence'] = frozen_confidence
        session['recommendation'] = rec
        session['status'] = 'TRIAGE_READY'
        session['timeline'].append({'event': 'TRIAGE_READY_NONE_OF_ABOVE', 'at': store.now_iso()})
        return SubmitAnswersResponse(
            session_id=session_id,
            status='TRIAGE_READY',
            confidence=frozen_confidence,
            confidence_percent=frozen_confidence_percent,
            risk_level=frozen_risk,
            questions=[],
        )

    # ── "Force recommend" branch ────────────────────────────────────────────
    # Patient clicked "I've described all my symptoms — get recommendation now".
    # Skip the confidence gate and produce the recommendation immediately.
    if payload.force_recommend:
        existing_answers = store.answers.get(session_id, [])
        current_answers = [a.model_dump() for a in payload.answers]
        if payload.additional_note:
            current_answers.append({'question_id': 'additional_note', 'value': payload.additional_note})
        store.answers[session_id] = existing_answers + current_answers
        recommendation = triage_agent.assess(session['symptom_input'], store.answers[session_id])
        session['recommendation'] = recommendation
        session['status'] = 'TRIAGE_READY'
        session['confidence'] = recommendation['confidence']
        session['confidence_percent'] = recommendation['confidence_percent']
        session['risk_level'] = recommendation['risk_level']
        session['timeline'].append({'event': 'FORCE_RECOMMEND_REQUESTED', 'at': store.now_iso()})
        session['timeline'].append({'event': 'TRIAGE_READY', 'at': store.now_iso()})
        return SubmitAnswersResponse(
            session_id=session_id,
            status='TRIAGE_READY',
            confidence=recommendation['confidence'],
            confidence_percent=recommendation['confidence_percent'],
            risk_level=recommendation['risk_level'],
            questions=[],
        )

    # ── Normal answer submission ─────────────────────────────────────────────
    existing_answers = store.answers.get(session_id, [])
    current_answers = [a.model_dump() for a in payload.answers]
    if payload.additional_note:
        current_answers.append({'question_id': 'additional_note', 'value': payload.additional_note})
    store.answers[session_id] = existing_answers + current_answers

    recommendation = triage_agent.assess(session['symptom_input'], store.answers[session_id])
    if (
        recommendation['confidence_percent'] <= CONFIDENCE_TARGET_PERCENT
        and current_round < MAX_FOLLOW_UP_ROUNDS
        and len(recommendation['red_flags_detected']) == 0
    ):
        next_round = current_round + 1
        asked_question_ids = list(session.get('asked_question_ids', []))
        questions = triage_agent.generate_follow_up_questions(
            session['symptom_input'],
            answers=store.answers[session_id],
            round_index=next_round,
            asked_question_ids=asked_question_ids,
            banned_symptoms=get_asked_symptoms(session_id),
        )
        if questions:
            add_asked_symptoms(session_id, [q['label'] for q in questions])
            session['status'] = 'FOLLOW_UP'
            session['follow_up_round'] = next_round
            session['questions'] = questions
            session['asked_question_ids'] = asked_question_ids + [q['question_id'] for q in questions]
            session['confidence'] = recommendation['confidence']
            session['confidence_percent'] = recommendation['confidence_percent']
            session['risk_level'] = recommendation['risk_level']
            session['timeline'].append({'event': f'FOLLOW_UP_ROUND_{current_round}_SUBMITTED', 'at': store.now_iso()})
            session['timeline'].append({'event': f'FOLLOW_UP_ROUND_{next_round}_GENERATED', 'at': store.now_iso()})
            return SubmitAnswersResponse(
                session_id=session_id,
                status='FOLLOW_UP',
                confidence=recommendation['confidence'],
                confidence_percent=recommendation['confidence_percent'],
                risk_level=recommendation['risk_level'],
                questions=questions,
            )

    session['recommendation'] = recommendation
    session['status'] = 'TRIAGE_READY'
    session['confidence'] = recommendation['confidence']
    session['confidence_percent'] = recommendation['confidence_percent']
    session['risk_level'] = recommendation['risk_level']
    session['timeline'].append({'event': f'FOLLOW_UP_ROUND_{current_round}_SUBMITTED', 'at': store.now_iso()})
    session['timeline'].append({'event': 'TRIAGE_READY', 'at': store.now_iso()})

    return SubmitAnswersResponse(
        session_id=session_id,
        status='TRIAGE_READY',
        confidence=recommendation['confidence'],
        confidence_percent=recommendation['confidence_percent'],
        risk_level=recommendation['risk_level'],
        questions=[],
    )


@router.get('/sessions/{session_id}/recommendation', response_model=RecommendationResponse)
def get_session_recommendation(session_id: str) -> RecommendationResponse:
    session = store.sessions.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail='Session not found')

    if session.get('status') != 'TRIAGE_READY':
        raise HTTPException(status_code=409, detail='Session not ready for recommendation. Continue follow-up first.')

    rec = session.get('recommendation')
    if not rec:
        rec = triage_agent.assess(session['symptom_input'], store.answers.get(session_id, []))
        session['recommendation'] = rec

    session['timeline'].append({'event': 'TRIAGE_RECOMMENDATION_VIEWED', 'at': store.now_iso()})

    return RecommendationResponse(
        session_id=session_id,
        status='TRIAGE_READY' if len(rec['red_flags_detected']) == 0 else 'ESCALATED',
        department=rec['department'],
        care_path=rec['care_path'],
        confidence=rec['confidence'],
        confidence_percent=rec['confidence_percent'],
        visit_needed=bool(rec.get('visit_needed', True)),
        reasons=rec['reasons'],
        red_flags_detected=rec['red_flags_detected'],
        disclaimer=DISCLAIMER,
    )


@router.post('/sessions/{session_id}/recommendation-feedback', response_model=RecommendationFeedbackResponse)
def recommendation_feedback(session_id: str, payload: RecommendationFeedbackRequest) -> RecommendationFeedbackResponse:
    session = store.sessions.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail='Session not found')

    store.feedback.setdefault(session_id, []).append(payload.model_dump())
    next_status = 'PROVIDER_MATCHED' if payload.decision == 'AGREE' else 'FOLLOW_UP'
    if payload.decision == 'DISAGREE':
        current_round = int(session.get('follow_up_round', 1)) + 1
        asked_question_ids = list(session.get('asked_question_ids', []))
        questions = triage_agent.generate_follow_up_questions(
            session['symptom_input'],
            answers=store.answers.get(session_id, []),
            round_index=current_round,
            asked_question_ids=asked_question_ids,
            banned_symptoms=get_asked_symptoms(session_id),
        )
        add_asked_symptoms(session_id, [q['label'] for q in questions])
        session['questions'] = questions
        session['follow_up_round'] = current_round
        session['asked_question_ids'] = asked_question_ids + [q['question_id'] for q in questions]
    session['status'] = next_status
    session['timeline'].append({'event': f'RECOMMENDATION_{payload.decision}', 'at': store.now_iso()})
    return RecommendationFeedbackResponse(session_id=session_id, next_status=next_status)


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
