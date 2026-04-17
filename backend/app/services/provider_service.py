import json
from pathlib import Path

DATA_PATH = Path(__file__).resolve().parents[1] / 'data' / 'providers.json'


def list_providers() -> list[dict]:
    if not DATA_PATH.exists():
        return []
    return json.loads(DATA_PATH.read_text(encoding='utf-8'))


def get_provider(provider_id: str) -> dict | None:
    for p in list_providers():
        if p['provider_id'] == provider_id:
            return p
    return None
