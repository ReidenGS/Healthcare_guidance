from functools import lru_cache
import os
from pathlib import Path

from dotenv import load_dotenv


# Always load backend/.env so both `python run.py` and direct `uvicorn ...` work.
load_dotenv(Path(__file__).resolve().parents[2] / '.env')


class Settings:
    openai_api_key: str = os.getenv('OPENAI_API_KEY', '')
    openai_model: str = os.getenv('OPENAI_MODEL', 'gpt-4o-mini')
    gemini_api_key: str = os.getenv('GEMINI_API_KEY', '')
    gemini_model: str = os.getenv('GEMINI_MODEL', 'gemini-1.5-flash')
    google_maps_api_key: str = os.getenv('GOOGLE_MAPS_API_KEY', '')
    # Tavily Search — used by web_search_skill for symptom reference lookup
    tavily_api_key: str = os.getenv('TAVILY_API_KEY', '')
    api_host: str = os.getenv('API_HOST', '127.0.0.1')
    api_port: int = int(os.getenv('API_PORT', '8000'))


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


def get_effective_openai_key() -> str:
    from app.core.request_context import openai_key_override
    return openai_key_override.get() or get_settings().openai_api_key


def get_effective_google_maps_key() -> str:
    from app.core.request_context import google_maps_key_override
    return google_maps_key_override.get() or get_settings().google_maps_api_key


def get_effective_gemini_key() -> str:
    from app.core.request_context import gemini_key_override
    return gemini_key_override.get() or get_settings().gemini_api_key


def get_effective_tavily_key() -> str:
    from app.core.request_context import tavily_key_override
    return tavily_key_override.get() or get_settings().tavily_api_key
