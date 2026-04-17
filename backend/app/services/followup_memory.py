from __future__ import annotations

import json
from pathlib import Path
from threading import Lock


MEMORY_FILE = Path('/tmp/healthcare_guidance_asked_symptoms.json')
_FILE_LOCK = Lock()


def _load() -> dict[str, list[str]]:
    if not MEMORY_FILE.exists():
        return {}
    try:
        return json.loads(MEMORY_FILE.read_text(encoding='utf-8'))
    except Exception:
        return {}


def _save(data: dict[str, list[str]]) -> None:
    MEMORY_FILE.parent.mkdir(parents=True, exist_ok=True)
    MEMORY_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')


def canonicalize_symptom_label(label: str) -> str:
    norm = ' '.join((label or '').strip().lower().split())
    if not norm:
        return ''

    fever_tokens = ['fever', '38c', '100.4f']
    breath_tokens = ['shortness of breath', 'breath', 'breathing']
    worsen_tokens = ['worsen', 'worse', 'getting worse', 'last 12 hours']
    dehydration_tokens = ['dehydration', 'dry mouth', 'reduced urination', 'very low urine']
    nausea_tokens = ['nausea', 'vomit', 'vomiting']
    blood_stool_tokens = ['black stool', 'blood in stool']
    meal_pain_tokens = ['after meals', 'after eating']
    vision_tokens = ['blurred', 'double vision']
    weakness_tokens = ['one-sided weakness', 'numbness']
    headache_tokens = ['sudden headache', 'severe headache']
    balance_tokens = ['balance', 'walking']
    chest_tokens = ['chest discomfort', 'chest pain']
    fatigue_tokens = ['severe fatigue', 'tired']

    if any(t in norm for t in fever_tokens):
        return 'symptom_fever'
    if any(t in norm for t in breath_tokens):
        return 'symptom_shortness_of_breath'
    if any(t in norm for t in worsen_tokens):
        return 'symptom_worsening'
    if any(t in norm for t in dehydration_tokens):
        return 'symptom_dehydration'
    if any(t in norm for t in nausea_tokens):
        return 'symptom_nausea_vomiting'
    if any(t in norm for t in blood_stool_tokens):
        return 'symptom_blood_stool'
    if any(t in norm for t in meal_pain_tokens):
        return 'symptom_post_meal_pain'
    if any(t in norm for t in vision_tokens):
        return 'symptom_vision_change'
    if any(t in norm for t in weakness_tokens):
        return 'symptom_one_sided_weakness'
    if any(t in norm for t in headache_tokens):
        return 'symptom_severe_headache'
    if any(t in norm for t in balance_tokens):
        return 'symptom_balance_issue'
    if any(t in norm for t in chest_tokens):
        return 'symptom_chest_discomfort'
    if any(t in norm for t in fatigue_tokens):
        return 'symptom_severe_fatigue'
    return norm


def init_session(session_id: str) -> None:
    with _FILE_LOCK:
        data = _load()
        data[session_id] = []
        _save(data)


def get_asked_symptoms(session_id: str) -> list[str]:
    with _FILE_LOCK:
        data = _load()
        raw = list(data.get(session_id, []))
        return sorted({canonicalize_symptom_label(x) for x in raw if canonicalize_symptom_label(x)})


def add_asked_symptoms(session_id: str, labels: list[str]) -> None:
    if not labels:
        return
    with _FILE_LOCK:
        data = _load()
        existing = set(data.get(session_id, []))
        for label in labels:
            norm = canonicalize_symptom_label(label)
            if norm:
                existing.add(norm)
        data[session_id] = sorted(existing)
        _save(data)
