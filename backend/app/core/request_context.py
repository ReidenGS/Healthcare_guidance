"""Per-request API key overrides via Python contextvars.

The API key middleware sets these before the route handler runs.
Services read them and prefer the override over the .env default.
"""
from contextvars import ContextVar

openai_key_override: ContextVar[str] = ContextVar('openai_key_override', default='')
google_maps_key_override: ContextVar[str] = ContextVar('google_maps_key_override', default='')
gemini_key_override: ContextVar[str] = ContextVar('gemini_key_override', default='')
tavily_key_override: ContextVar[str] = ContextVar('tavily_key_override', default='')
