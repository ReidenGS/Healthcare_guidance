# Healthcare Guidance — Business Logic (Current Implementation)

## 1. Goals
1. Determine with high confidence which medical department best fits the patient's described symptoms.
2. When uncertain, guide the patient through AI-generated follow-up questions rather than providing vague advice immediately.
3. When in-person care is needed, continue to provider matching, insurance estimation, and booking intent.
4. When self-care is sufficient, allow the patient to exit the flow without entering the provider/insurance/booking stages.

## 2. End-to-End Flow

1. **`PROFILE`** — Patient fills in basic info and location (any one of: address / city / ZIP code).
2. **Location resolution**:
   - First tries `/geo/geocode`
   - Falls back to browser GPS if geocode fails
   - If GPS also fails, prompts the user to enable location access or provide more detail
3. **`INTAKE`** — Patient submits chief complaint + severity score.
4. **GPT triage (first pass)**:
   - `confidence_percent > 80` → `TRIAGE_READY`
   - Otherwise → `FOLLOW_UP`
5. **`FOLLOW_UP`**:
   - Each round presents 4 first-person symptom candidates
   - Patient selections are injected into the next GPT prompt
   - Already-asked symptoms are deduplicated to avoid repetition
6. **`TRIAGE_READY` recommendation judgment**:
   - Standard path: patient agrees → enter provider search
   - Self-care branch: `Primary Care + visit_needed=false` → end flow (back home or rewrite symptoms)
7. **Needs-care branch**: Provider matching → insurance estimation → booking intent → completion.

## 3. Key Decision Rules

### 3.1 Confidence gate
- Only `confidence_percent > 80` allows advancing to the recommendation stage.

### 3.2 Follow-up rules
- 4 candidate symptoms per round.
- All candidates must be first-person declarative statements (patient's perspective).
- A temporary file tracks previously asked symptoms for deduplication.

### 3.3 Visit-needed judgment
- Field: `visit_needed` (from the recommendation endpoint).
- Meaning:
  - `true` — Recommend continuing the care-seeking flow.
  - `false` — Self-care is more appropriate; skip the provider stage entirely.

## 4. Key Data Objects

1. **Recommendation result**
   - `department`
   - `care_path`
   - `confidence_percent`
   - `visit_needed`
   - `reasons`

2. **Location result**
   - `normalized_address`
   - `lat` / `lng`
   - `source`

3. **Care fulfillment result**
   - `providers[]`
   - `insurance result`
   - `booking_intent_id`
   - `timeline`

## 5. Consistency Constraints
1. Frontend must not call the provider search endpoint when `visit_needed=false`.
2. Frontend must render follow-up questions exactly as returned in `questions[]` from the backend.
3. Backend must not assume the frontend provides a precise address — it must support both geocode and GPS paths.
4. All user-facing text must include the disclaimer: *"This is AI navigation guidance, not a medical diagnosis."*

## 6. Business Value
1. Improves explainability and actionability of department recommendations.
2. Reduces misleading over-triage through follow-up questioning and the `visit_needed` branch.
3. Connects triage → provider → cost → booking into a closed-loop flow suitable for real-world deployment.
