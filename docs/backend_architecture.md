# Healthcare Guidance — Backend Architecture (Python + FastAPI + LangChain)

## 1. Overview

The backend is a dual-agent system with supporting skills:

1. **GPT Triage Agent** (OpenAI)
   - Symptom analysis, confidence scoring, department routing, follow-up question generation.
2. **Gemini Navigation Agent** (Google)
   - Provider search query generation and insurance cost explanation.
3. **Skills**
   - Google Maps Places: nearby provider search
   - Tavily Search: optional symptom-to-department reference lookup
   - Follow-up Memory: deduplication of already-asked symptoms
   - Geocode Service: location string → lat/lng

## 2. Triage Rules

1. Confidence threshold: `confidence_percent > 80` advances to `TRIAGE_READY`.
2. Below threshold enters `FOLLOW_UP`; each round presents exactly 4 first-person symptom statements.
3. Follow-up candidates are deduplicated via `/tmp/healthcare_guidance_asked_symptoms.json`.
4. Recommendation response includes:
   - `visit_needed: bool` — distinguishes "needs in-person care" from "self-care sufficient".

## 3. State Machine

Main states:
`PROFILE (frontend) → INTAKE → FOLLOW_UP → TRIAGE_READY → PROVIDER_MATCHED → INSURANCE → INSURANCE_RESULT → BOOKING → COMPLETED`

Branches:
- `ESCALATED` — Red-flag symptom branch.
- `TRIAGE_READY` + `department=Primary Care && care_path=PRIMARY_CARE && visit_needed=false`:
  Frontend skips provider flow and returns home or allows symptom rewrite.

## 4. API Contract (current implementation)

### 4.1 Geocoding
- `POST /api/v1/geo/geocode`
- Request: `{ "query": "..." }`
- Response: `query, normalized_address, lat, lng, source`
- On failure: returns `422` (frontend falls back to GPS)

### 4.2 Triage session
- `POST /api/v1/triage/sessions`
- Returns: `status, confidence_percent, questions[]`

### 4.3 Submit follow-up
- `POST /api/v1/triage/sessions/{session_id}/answers`

### 4.4 Get recommendation
- `GET /api/v1/triage/sessions/{session_id}/recommendation`
- Key fields:
  - `department`
  - `care_path`
  - `confidence_percent`
  - `visit_needed`
  - `reasons`
  - `red_flags_detected`

### 4.5 Recommendation feedback
- `POST /api/v1/triage/sessions/{session_id}/recommendation-feedback`
- `AGREE → PROVIDER_MATCHED`
- `DISAGREE → FOLLOW_UP`

### 4.6 Providers / Insurance / Booking
- `POST /api/v1/providers/search`
- `POST /api/v1/insurance/check`
- `POST /api/v1/booking/intents`
- `GET /api/v1/triage/sessions/{session_id}/summary`

## 5. Models & Configuration

Key `.env` variables:
- `OPENAI_API_KEY`, `OPENAI_MODEL`
- `GEMINI_API_KEY`, `GEMINI_MODEL`
- `GOOGLE_MAPS_API_KEY`
- `TAVILY_API_KEY`

## 6. Per-Request API Key Override (added 2026-04-17)

### 6.1 Overview
The frontend can pass API keys as custom request headers. The backend uses those keys in preference to the `.env` defaults, with no restart required.

### 6.2 New file
- `app/core/request_context.py` — Four `ContextVar`s:
  `openai_key_override` / `google_maps_key_override` / `gemini_key_override` / `tavily_key_override`

### 6.3 Middleware (`app/main.py`)
```python
@app.middleware('http')
async def extract_api_keys(request, call_next):
    openai_key_override.set(request.headers.get('X-OpenAI-Key', ''))
    google_maps_key_override.set(request.headers.get('X-Google-Maps-Key', ''))
    gemini_key_override.set(request.headers.get('X-Gemini-Key', ''))
    tavily_key_override.set(request.headers.get('X-Tavily-Key', ''))
    return await call_next(request)
```

### 6.4 Helper functions (`app/core/config.py`)
- `get_effective_openai_key()` / `get_effective_google_maps_key()` / `get_effective_gemini_key()` / `get_effective_tavily_key()`
- Logic: `ContextVar override value  or  .env default`

### 6.5 Per-service changes

| File | Change |
|------|--------|
| `agents/triage_agent.py` | Added `_get_client()` / `_is_enabled()` — uses per-request OpenAI key dynamically |
| `services/google_maps_skill.py` | Uses `get_effective_google_maps_key()` |
| `services/web_search_skill.py` | Uses `get_effective_tavily_key()` |
| `services/geocode_service.py` | Uses `get_effective_google_maps_key()` |

### 6.6 Header convention

| Header | Service |
|--------|---------|
| `X-OpenAI-Key` | OpenAI GPT Triage Agent |
| `X-Google-Maps-Key` | Google Maps provider search & geocoding |
| `X-Gemini-Key` | Gemini Navigation Agent (reserved) |
| `X-Tavily-Key` | Tavily symptom reference search |

## 7. Delivered Guarantees
1. Triage outputs specific clinical specialties (Ophthalmology, Cardiology, etc.) or Primary Care.
2. Follow-up questions are dynamically generated and deduplicated each round.
3. Recommendation response includes `visit_needed` to support the self-care branch.
4. Location supports text geocoding with frontend GPS fallback.
5. Frontend-provided API keys override server defaults per-request without restart.
