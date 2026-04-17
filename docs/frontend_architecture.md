# Healthcare Guidance — Frontend Architecture

## 1. Goals
1. Full English UI covering the complete flow: profile intake → symptom triage → provider matching → insurance estimation → booking intent.
2. Aligned with the dual-agent backend: GPT handles triage; Gemini handles provider and insurance guidance.
3. Strict field-level contract alignment with backend API to prevent schema drift.

## 2. Views & State Machine

Main flow:
`PROFILE → INTAKE → FOLLOW_UP → TRIAGE_READY → PROVIDER_MATCHED → INSURANCE → INSURANCE_RESULT → BOOKING → COMPLETED`

Branch states:
- `ESCALATED` — High-risk red-flag symptoms; shows emergency guidance, blocks normal flow.
- `TRIAGE_READY` self-care branch:
  - Condition: `department='Primary Care' && care_path='PRIMARY_CARE' && visit_needed=false`
  - Behavior: Skip provider/insurance/booking flow; offer "Back to home" or "Rewrite symptoms" only.

## 3. Profile Stage

`PROFILE` page input fields:
- `detailAddress`
- `city`
- `zipCode`
- `age` (required)
- `sex` (required)
- `insurancePlan` (optional)

Rules:
1. At least one of the three location fields must be filled; frontend blocks submission otherwise.
2. On submit, first calls `/geo/geocode`; falls back to browser GPS if geocode fails.
3. If both geocode and GPS fail, prompts the user to enable location or provide more detail.

## 4. API Mapping (actual frontend calls)

### 4.1 Location geocoding
- Function: `geocodeLocation(payload)`
- Endpoint: `POST /api/v1/geo/geocode`

Request:
```json
{ "query": "36 journal square, New Jersey, 07306" }
```

Response:
```json
{
  "query": "36 journal square, New Jersey, 07306",
  "normalized_address": "...",
  "lat": 40.7,
  "lng": -74.0,
  "source": "google|fallback|zip_fallback"
}
```

### 4.2 Create triage session
- `POST /api/v1/triage/sessions`

Request:
```json
{
  "user_profile": {
    "age": 32,
    "sex": "female",
    "city": "normalized address or city/zip",
    "insurance_plan": "Aetna PPO"
  },
  "symptom_input": {
    "chief_complaint": "...",
    "duration_hours": 0,
    "severity_0_10": 6,
    "free_text": "..."
  },
  "consent": { "hipaa_ack": true, "ai_guidance_ack": true }
}
```

### 4.3 Submit follow-up answers
- `POST /api/v1/triage/sessions/{session_id}/answers`

### 4.4 Get recommendation
- `GET /api/v1/triage/sessions/{session_id}/recommendation`

Key response fields:
```json
{
  "department": "Ophthalmology",
  "care_path": "SPECIALIST",
  "confidence_percent": 86,
  "visit_needed": true,
  "reasons": ["..."],
  "red_flags_detected": []
}
```

### 4.5 Recommendation feedback
- `POST /api/v1/triage/sessions/{session_id}/recommendation-feedback`

### 4.6 Provider search
- `POST /api/v1/providers/search`

Request (frontend guarantees `city + lat + lng`):
```json
{
  "session_id": "sess_xxx",
  "care_path": "URGENT_CARE",
  "location": {
    "city": "Jersey City, NJ",
    "lat": 40.7,
    "lng": -74.0,
    "radius_km": 10
  }
}
```

### 4.7 Insurance & booking
- `POST /api/v1/insurance/check`
- `POST /api/v1/booking/intents`
- `GET /api/v1/triage/sessions/{session_id}/summary`

## 5. Key Interaction Constraints
1. The "Agree" button on the recommendation page only proceeds to provider search when `visit_needed=true`.
2. The `visit_needed=false` Primary Care branch must terminate the provider flow immediately.
3. The progress bar starts at "Profile" — cannot be skipped.
4. Error messages always display the backend `detail` string or joined validation errors.

## 6. API Key Settings (added 2026-04-17)

### 6.1 Entry point
The **"API Keys"** button (Settings icon) is fixed in the top-right corner of the header, visible at all flow stages.

### 6.2 `ApiKeyModal` component
- Four input fields: OpenAI API Key / Google Maps API Key / Gemini API Key / Tavily API Key.
- Each field has a show/hide toggle (password mode).
- **Save**: writes non-empty values to `localStorage`; removes keys with empty values.
- **Clear all**: wipes all stored keys.
- Clicking the backdrop or "Cancel" closes without saving.

### 6.3 Key injection in `api.js`
- `getStoredApiKeys()` — reads the four keys from `localStorage`.
- `saveApiKeys()` — write / remove from `localStorage`.
- `getApiKeyHeaders()` — assembles headers for non-empty keys (`X-OpenAI-Key` / `X-Google-Maps-Key` / `X-Gemini-Key` / `X-Tavily-Key`).
- `request()` automatically appends these headers to every API call.

### 6.4 Priority rule
- Keys entered by the user → used first (passed to backend via headers).
- Empty fields → backend uses the `.env` defaults; frontend is unaware.
