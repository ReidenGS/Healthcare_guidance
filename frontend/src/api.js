const API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000';

const API_KEY_STORAGE = {
  openai:    'hg_openai_key',
  googleMaps: 'hg_google_maps_key',
  gemini:    'hg_gemini_key',
  tavily:    'hg_tavily_key',
};

export function getStoredApiKeys() {
  return {
    openai:    localStorage.getItem(API_KEY_STORAGE.openai)    || '',
    googleMaps: localStorage.getItem(API_KEY_STORAGE.googleMaps) || '',
    gemini:    localStorage.getItem(API_KEY_STORAGE.gemini)    || '',
    tavily:    localStorage.getItem(API_KEY_STORAGE.tavily)    || '',
  };
}

export function saveApiKeys({ openai, googleMaps, gemini, tavily }) {
  const set = (k, v) => v ? localStorage.setItem(k, v) : localStorage.removeItem(k);
  set(API_KEY_STORAGE.openai,    openai);
  set(API_KEY_STORAGE.googleMaps, googleMaps);
  set(API_KEY_STORAGE.gemini,    gemini);
  set(API_KEY_STORAGE.tavily,    tavily);
}

function getApiKeyHeaders() {
  const keys = getStoredApiKeys();
  const headers = {};
  if (keys.openai)    headers['X-OpenAI-Key']       = keys.openai;
  if (keys.googleMaps) headers['X-Google-Maps-Key']  = keys.googleMaps;
  if (keys.gemini)    headers['X-Gemini-Key']        = keys.gemini;
  if (keys.tavily)    headers['X-Tavily-Key']        = keys.tavily;
  return headers;
}

async function request(path, options = {}) {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: { 'Content-Type': 'application/json', ...getApiKeyHeaders(), ...(options.headers || {}) },
    ...options
  });

  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    // FastAPI returns errors as { detail: "..." } or { detail: [{msg, loc, type},...] }
    let message = 'Request failed';
    if (typeof data.detail === 'string') {
      message = data.detail;
    } else if (Array.isArray(data.detail) && data.detail.length > 0) {
      message = data.detail.map(e => `${e.loc?.join('.')}: ${e.msg}`).join(' | ');
    } else if (data.error?.message) {
      message = data.error.message;
    }
    throw new Error(`[${response.status}] ${message}`);
  }

  return data;
}

export function createSession(payload) {
  return request('/api/v1/triage/sessions', {
    method: 'POST',
    body: JSON.stringify(payload)
  });
}

export function submitAnswers(sessionId, payload) {
  return request(`/api/v1/triage/sessions/${sessionId}/answers`, {
    method: 'POST',
    body: JSON.stringify(payload)
  });
}

export function getRecommendation(sessionId) {
  return request(`/api/v1/triage/sessions/${sessionId}/recommendation`);
}

export function sendRecommendationFeedback(sessionId, payload) {
  return request(`/api/v1/triage/sessions/${sessionId}/recommendation-feedback`, {
    method: 'POST',
    body: JSON.stringify(payload)
  });
}

export function searchProviders(payload) {
  return request('/api/v1/providers/search', {
    method: 'POST',
    body: JSON.stringify(payload)
  });
}

export function geocodeLocation(payload) {
  return request('/api/v1/geo/geocode', {
    method: 'POST',
    body: JSON.stringify(payload)
  });
}

export function checkInsurance(payload) {
  return request('/api/v1/insurance/check', {
    method: 'POST',
    body: JSON.stringify(payload)
  });
}

export function createBookingIntent(payload) {
  return request('/api/v1/booking/intents', {
    method: 'POST',
    body: JSON.stringify(payload)
  });
}

export function getSummary(sessionId) {
  return request(`/api/v1/triage/sessions/${sessionId}/summary`);
}

export function getBookingRecords(phone) {
  const encoded = encodeURIComponent(phone.trim());
  return request(`/api/v1/booking/records?phone=${encoded}`);
}

export function getProviderSlots(providerId) {
  const encoded = encodeURIComponent(providerId);
  return request(`/api/v1/booking/slots?provider_id=${encoded}`);
}
