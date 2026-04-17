# Healthcare Guidance

An AI-powered full-stack healthcare navigation app that helps patients identify the right medical department, find nearby providers, estimate insurance costs, and submit booking intents.

- **Frontend**: React + Vite + Tailwind CSS
- **Backend**: FastAPI + LangChain multi-agent
  - Agent 1 (GPT / OpenAI): Symptom triage, confidence scoring, follow-up question generation
  - Agent 2 (Gemini): Provider search guidance and insurance cost explanation
  - Google Maps skill: Nearby clinic/hospital search via Google Places API

---

## Project Structure

```text
Healthcare-guidance/
├── frontend/
│   ├── src/
│   │   ├── App.jsx        # Main React component (all views & state machine)
│   │   └── api.js         # API client (fetch wrapper + API key headers)
│   ├── index.html
│   └── package.json
├── backend/
│   ├── app/
│   │   ├── main.py        # FastAPI app + CORS + API key middleware
│   │   ├── agents/
│   │   │   ├── triage_agent.py       # GPT triage & follow-up logic
│   │   │   └── navigation_agent.py   # Gemini provider search
│   │   ├── api/v1/        # Route handlers (triage, providers, insurance, booking, geo)
│   │   ├── core/
│   │   │   ├── config.py             # Settings from .env + effective key helpers
│   │   │   └── request_context.py    # Per-request API key context vars
│   │   └── services/      # Google Maps, Tavily, geocoding, insurance, etc.
│   ├── .env.example
│   └── requirements.txt
├── docs/
│   ├── frontend_architecture.md
│   ├── backend_architecture.md
│   └── business_logic.md
└── modify/                # Date-based changelogs
```

---

## Patient Flow

| Step | View | Description |
|------|------|-------------|
| 1 | `PROFILE` | Collect age, sex, insurance plan, and location |
| 2 | `INTAKE` | Submit chief complaint and severity score |
| 3 | `FOLLOW_UP` | AI-guided symptom selection (up to 8 rounds) |
| 4 | `TRIAGE_READY` | Review AI department recommendation |
| 5 | `PROVIDER_MATCHED` | Browse matched providers near you |
| 6 | `INSURANCE` | Select insurance plan for cost estimation |
| 7 | `INSURANCE_RESULT` | View in-network status and cost breakdown |
| 8 | `BOOKING` | Submit booking intent |
| 9 | `COMPLETED` | Confirmation and post-visit instructions |

Special branches:
- `ESCALATED` — High-risk red-flag symptoms detected; emergency guidance shown immediately.
- `TRIAGE_READY` self-care branch — If `Primary Care + visit_needed=false`, skip provider flow and return home.

---

## Getting Started

### Backend

```bash
cd Healthcare-guidance/backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Fill in your API keys in .env (see below)
python run.py
```

Backend runs at `http://127.0.0.1:8000`

### Frontend

```bash
cd Healthcare-guidance/frontend
npm install
npm run dev
```

Frontend runs at `http://127.0.0.1:5173`

Optional env variable: `VITE_API_BASE_URL` (default: `http://127.0.0.1:8000`)

---

## Environment Variables (`.env`)

```env
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4o-mini

GEMINI_API_KEY=AIzaSy...
GEMINI_MODEL=gemini-1.5-flash

GOOGLE_MAPS_API_KEY=AIzaSy...
TAVILY_API_KEY=tvly-...
```

> Keys set in `.env` are the server defaults. Users can override them at runtime via the **API Keys** button in the app UI — no restart required.

---

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/v1/triage/sessions` | Create a new triage session |
| `POST` | `/api/v1/triage/sessions/{id}/answers` | Submit follow-up answers |
| `GET`  | `/api/v1/triage/sessions/{id}/recommendation` | Get department recommendation |
| `POST` | `/api/v1/triage/sessions/{id}/recommendation-feedback` | Agree / Disagree with recommendation |
| `POST` | `/api/v1/providers/search` | Search nearby providers |
| `POST` | `/api/v1/insurance/check` | Check insurance coverage and estimate costs |
| `POST` | `/api/v1/booking/intents` | Submit a booking intent |
| `GET`  | `/api/v1/triage/sessions/{id}/summary` | Get full session summary |
| `POST` | `/api/v1/geo/geocode` | Geocode a location string to lat/lng |
| `GET`  | `/api/health` | Health check |

---

## Multi-Agent Architecture

| Agent | Model | Responsibility |
|-------|-------|----------------|
| Triage Agent | GPT (OpenAI) | Symptom analysis, department routing, confidence scoring, follow-up question generation |
| Navigation Agent | Gemini (Google) | Provider search query generation, insurance cost explanation |

Supporting skills:
- **Google Maps skill** (`google_maps_skill.py`) — Searches nearby clinics via Google Places; falls back to local provider data if no API key.
- **Tavily search skill** (`web_search_skill.py`) — Optional symptom-to-department reference lookup.
- **Geocode service** (`geocode_service.py`) — Converts address / city / ZIP to lat/lng; falls back to public API or city lookup table.
- **Red-flag RAG** (`redflag_rag.py`) — Offline vector store for emergency symptom detection.

---

## Runtime API Key Override

Users can provide their own API keys through the **API Keys** button in the top-right corner of the app. Keys are stored in `localStorage` and sent as custom request headers (`X-OpenAI-Key`, `X-Google-Maps-Key`, `X-Gemini-Key`, `X-Tavily-Key`). The backend middleware reads these headers and overrides the `.env` defaults for that request only.

---

## Notes

1. Provider data and insurance cost estimates are mock/demo data structured to match the frontend UI.
2. This service is for AI-assisted care navigation only — **not a medical diagnosis**.
3. If high-risk symptoms (red flags) are detected, the app immediately shows emergency guidance (`ESCALATED` view).
