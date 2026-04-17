"""
insurance_service.py — Demo Insurance Network Checker
======================================================
Simulates querying major insurer databases to check whether a selected
provider is covered, and uses AI to estimate REALISTIC cost ranges based
on the patient's actual department, care path, and symptom context.

Demo split rule (deterministic, based on insurer index in the JSON file):
  • Even index  (0, 2, …) → insurer ALWAYS covers any provider (in-network)
  • Odd  index  (1, 3, …) → insurer NEVER covers the provider (out-of-network)

Both paths use AI-generated cost figures that reflect the actual medical
context (department + care_path + risk_level) rather than hardcoded values.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

DATA_PATH = Path(__file__).resolve().parents[1] / 'data' / 'insurance_networks.json'

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _normalize(value: str) -> str:
    return ' '.join((value or '').strip().lower().split())


def _load_network_db() -> list[dict[str, Any]]:
    if not DATA_PATH.exists():
        return []
    try:
        data = json.loads(DATA_PATH.read_text(encoding='utf-8'))
        return data if isinstance(data, list) else []
    except Exception:
        return []


def _find_insurer_entry(plan: str, db: list[dict[str, Any]]) -> tuple[dict[str, Any] | None, int]:
    """Return (entry, index) for the matching insurer, or (None, -1)."""
    p = _normalize(plan)
    if not p:
        return None, -1
    for idx, entry in enumerate(db):
        aliases = [entry.get('insurer', ''), *(entry.get('aliases', []) or [])]
        alias_norm = [_normalize(str(a)) for a in aliases if _normalize(str(a))]
        if any(a in p or p in a for a in alias_norm):
            return entry, idx
    return None, -1


def _to_breakdown_lines(
    items: list[dict[str, Any]] | None,
    default_items: list[dict[str, str]],
) -> list[dict[str, str]]:
    src = items if isinstance(items, list) and items else default_items
    lines: list[dict[str, str]] = []
    for x in src:
        item = str(x.get('item', '')).strip()
        rng  = str(x.get('range', '')).strip()
        if item and rng:
            lines.append({'item': item, 'range': rng})
    return lines if lines else default_items


# ---------------------------------------------------------------------------
# AI cost estimator
# ---------------------------------------------------------------------------

_COST_SYSTEM_PROMPT = (
    'You are a US healthcare cost estimator. '
    'Given the patient triage result and insurance information, estimate '
    'REALISTIC out-of-pocket cost ranges (USD) for this specific visit. '
    'Consider the department specialty, care path urgency, and typical US '
    'billing rates. Apply the insurer coverage ratio to compute the in-network '
    'patient portion. Return ONLY valid JSON, no markdown.'
)

_COST_SCHEMA = (
    'Return JSON with exactly these keys:\n'
    '{\n'
    '  "out_network_min": <int>,   // self-pay, low estimate\n'
    '  "out_network_max": <int>,   // self-pay, high estimate\n'
    '  "in_network_min":  <int>,   // after insurance, low estimate\n'
    '  "in_network_max":  <int>,   // after insurance, high estimate\n'
    '  "cost_breakdown_out_network": [\n'
    '    {"item": "<service>", "range": "$X - $Y"},  // 3 line items\n'
    '    ...\n'
    '  ],\n'
    '  "cost_breakdown_in_network": [\n'
    '    {"item": "<service after insurance>", "range": "$X - $Y"},\n'
    '    ...\n'
    '  ]\n'
    '}'
)


def _ai_estimate_costs(
    triage_result: dict[str, Any],
    insurer_entry: dict[str, Any] | None,
    insurance_plan: str,
) -> dict[str, Any] | None:
    """
    Ask GPT to estimate realistic cost ranges based on medical context.

    Returns a dict with keys: out_network_min/max, in_network_min/max,
    cost_breakdown_out_network, cost_breakdown_in_network.
    Returns None if OpenAI is not configured or the call fails.
    """
    try:
        from langchain_core.messages import HumanMessage, SystemMessage
        from langchain_openai import ChatOpenAI
        from app.core.config import get_settings

        settings = get_settings()
        if not settings.openai_api_key:
            return None

        client = ChatOpenAI(
            model=settings.openai_model,
            api_key=settings.openai_api_key,
            temperature=0,
            timeout=10,
            max_retries=0,
        )

        department  = triage_result.get('department', 'Primary Care')
        care_path   = triage_result.get('care_path', 'PRIMARY_CARE')
        risk_level  = triage_result.get('risk_level', 'MEDIUM')
        reasons     = triage_result.get('reasons', [])

        coverage_ratio = (
            insurer_entry.get('coverage_ratio', 'About 75% - 85%')
            if insurer_entry else 'No coverage'
        )

        user_content = (
            f'Department: {department}\n'
            f'Care path: {care_path}\n'
            f'Risk level: {risk_level}\n'
            f'Clinical reasons: {"; ".join(reasons) if reasons else "N/A"}\n'
            f'Insurance plan: {insurance_plan}\n'
            f'Insurer coverage ratio: {coverage_ratio}\n\n'
            + _COST_SCHEMA
        )

        msg = client.invoke([
            SystemMessage(content=_COST_SYSTEM_PROMPT),
            HumanMessage(content=user_content),
        ])
        raw = msg.content if isinstance(msg.content, str) else str(msg.content)
        raw = raw.strip().removeprefix('```json').removeprefix('```').removesuffix('```').strip()
        parsed = json.loads(raw)

        # Validate required keys exist and are integers
        for key in ('out_network_min', 'out_network_max', 'in_network_min', 'in_network_max'):
            parsed[key] = int(parsed[key])

        return parsed
    except Exception:
        return None


def _fallback_costs(
    triage_result: dict[str, Any],
    insurer_entry: dict[str, Any] | None,
) -> dict[str, Any]:
    """
    Rule-based fallback cost estimates when AI is unavailable.
    Uses department and care_path to pick a realistic price band.
    """
    care_path  = (triage_result.get('care_path') or 'PRIMARY_CARE').upper()
    department = (triage_result.get('department') or '').lower()

    # Out-of-network bands by urgency
    if care_path == 'ER' or 'emergency' in department:
        out_min, out_max = 800, 3500
        breakdown_out = [
            {'item': 'Emergency room facility fee', 'range': '$500 - $2,000'},
            {'item': 'Physician / specialist fee',  'range': '$200 - $1,000'},
            {'item': 'Labs, imaging & medication',  'range': '$100 - $500'},
        ]
    elif care_path == 'URGENT_CARE':
        out_min, out_max = 180, 500
        breakdown_out = [
            {'item': 'Urgent care visit fee',       'range': '$120 - $300'},
            {'item': 'Diagnostics / labs',          'range': '$40 - $150'},
            {'item': 'Medication (self-pay)',        'range': '$20 - $50'},
        ]
    elif care_path == 'SPECIALIST':
        out_min, out_max = 250, 700
        breakdown_out = [
            {'item': 'Specialist consultation fee', 'range': '$150 - $400'},
            {'item': 'Diagnostic tests',            'range': '$80 - $200'},
            {'item': 'Medication (self-pay)',        'range': '$20 - $100'},
        ]
    else:  # PRIMARY_CARE
        out_min, out_max = 100, 280
        breakdown_out = [
            {'item': 'Office visit fee',            'range': '$75 - $180'},
            {'item': 'Basic lab work',              'range': '$20 - $80'},
            {'item': 'Medication (self-pay)',        'range': '$5 - $20'},
        ]

    # In-network: apply rough 75-85% coverage → patient pays ~15-25%
    in_min = max(15, int(out_min * 0.15))
    in_max = max(30, int(out_max * 0.25))

    # Override with JSON values if available
    if insurer_entry:
        json_out = insurer_entry.get('out_network_estimated_cost') or {}
        json_in  = insurer_entry.get('in_network_estimated_cost')  or {}
        if json_out.get('min') and json_out.get('max'):
            out_min, out_max = int(json_out['min']), int(json_out['max'])
        if json_in.get('min') and json_in.get('max'):
            in_min, in_max = int(json_in['min']), int(json_in['max'])

    breakdown_in = [
        {'item': 'Copay after insurance',      'range': f'${in_min} - ${in_min + 20}'},
        {'item': 'Labs / diagnostics covered', 'range': '$0 - $30'},
        {'item': 'Medication copay',           'range': '$5 - $20'},
    ]

    return {
        'out_network_min': out_min,
        'out_network_max': out_max,
        'in_network_min':  in_min,
        'in_network_max':  in_max,
        'cost_breakdown_out_network': breakdown_out,
        'cost_breakdown_in_network':  breakdown_in,
    }


# ---------------------------------------------------------------------------
# Legacy simple estimator (kept for backward-compat)
# ---------------------------------------------------------------------------

def estimate_insurance(plan: str) -> dict:
    unknown = _normalize(plan) in {'self-pay', 'unknown / self-pay', ''}
    if unknown:
        return {
            'in_network': False,
            'estimated_cost': {'currency': 'USD', 'min': 180, 'max': 420},
            'original_cost':  {'currency': 'USD', 'min': 180, 'max': 420},
            'cost_breakdown': [
                {'item': 'Specialist consultation (self-pay)', 'range': '$80 - $150'},
                {'item': 'Lab tests / diagnostics (self-pay)', 'range': '$60 - $180'},
                {'item': 'Medication (self-pay)',               'range': '$40 - $90'},
            ],
            'coverage_ratio': 'No coverage',
            'notice': 'No insurance plan selected. Showing estimated self-pay rates.',
        }
    return {
        'in_network': True,
        'estimated_cost': {'currency': 'USD', 'min': 25, 'max': 90},
        'original_cost':  {'currency': 'USD', 'min': 180, 'max': 420},
        'cost_breakdown': [
            {'item': 'Consultation copay',         'range': '$20 - $40'},
            {'item': 'Lab tests (after coverage)', 'range': '$0 - $35'},
            {'item': 'Medication copay',           'range': '$5 - $15'},
        ],
        'coverage_ratio': 'About 80% - 90%',
        'notice': 'Estimated values only. Final amount depends on your policy deductible.',
    }


# ---------------------------------------------------------------------------
# Main demo estimator
# ---------------------------------------------------------------------------

def estimate_insurance_from_mock_db(
    plan: str,
    provider_id: str = '',
    provider_name: str = '',
    provider_address: str = '',
    triage_result: dict[str, Any] | None = None,
) -> dict:
    """
    Demo insurance check with AI-generated cost estimates.

    Cost figures are produced by GPT based on the actual department, care
    path, and risk level from the triage result — not hardcoded values.

    Split rule (by insurer index in insurance_networks.json):
    • Even index → this insurer covers ANY provider  (in-network path)
    • Odd  index → this insurer covers NO provider   (out-of-network path)
    """
    triage_result = triage_result or {}

    # --- Self-pay / unknown plan ---
    if _normalize(plan) in {'self-pay', 'unknown / self-pay', ''}:
        costs = _fallback_costs(triage_result, None)
        return {
            'in_network': False,
            'estimated_cost': {'currency': 'USD', 'min': costs['out_network_min'], 'max': costs['out_network_max']},
            'original_cost':  {'currency': 'USD', 'min': costs['out_network_min'], 'max': costs['out_network_max']},
            'cost_breakdown': costs['cost_breakdown_out_network'],
            'coverage_ratio': 'No coverage',
            'notice': 'No insurance plan selected. Showing estimated self-pay rates based on your recommended department.',
        }

    db = _load_network_db()
    entry, idx = _find_insurer_entry(plan, db)

    # --- Insurer not found in demo DB ---
    if entry is None:
        costs = _fallback_costs(triage_result, None)
        return {
            'in_network': False,
            'estimated_cost': {'currency': 'USD', 'min': costs['out_network_min'], 'max': costs['out_network_max']},
            'original_cost':  {'currency': 'USD', 'min': costs['out_network_min'], 'max': costs['out_network_max']},
            'cost_breakdown': costs['cost_breakdown_out_network'],
            'coverage_ratio': 'No coverage',
            'notice': (
                f'"{plan}" was not found in the demo insurer database. '
                'Showing estimated self-pay rates for your recommended department. '
                'Contact your insurer directly to verify coverage.'
            ),
        }

    insurer_name = entry.get('insurer', plan)
    coverage_ratio = str(entry.get('coverage_ratio', 'About 75% - 85%'))

    # --- AI cost estimation (falls back to rule-based if AI unavailable) ---
    ai_costs = _ai_estimate_costs(triage_result, entry, plan)
    costs = ai_costs if ai_costs else _fallback_costs(triage_result, entry)

    out_min = costs['out_network_min']
    out_max = costs['out_network_max']
    in_min  = costs['in_network_min']
    in_max  = costs['in_network_max']

    breakdown_in  = _to_breakdown_lines(
        costs.get('cost_breakdown_in_network'),
        [
            {'item': 'Copay after insurance',      'range': f'${in_min} - ${in_min + 25}'},
            {'item': 'Labs / diagnostics covered', 'range': '$0 - $30'},
            {'item': 'Medication copay',           'range': '$5 - $20'},
        ],
    )
    breakdown_out = _to_breakdown_lines(
        costs.get('cost_breakdown_out_network'),
        [
            {'item': 'Visit / consultation fee',   'range': f'${int(out_min * 0.5)} - ${int(out_max * 0.55)}'},
            {'item': 'Diagnostics / labs',         'range': f'${int(out_min * 0.3)} - ${int(out_max * 0.3)}'},
            {'item': 'Medication (self-pay)',       'range': '$20 - $80'},
        ],
    )

    # -----------------------------------------------------------------------
    # Demo split: even index → always in-network, odd → always out-of-network
    # -----------------------------------------------------------------------
    covered = (idx % 2 == 0)

    if covered:
        save_min = out_min - in_min
        save_max = out_max - in_max
        savings_text = (
            f'You save approximately ${save_min}–${save_max} compared to paying out-of-pocket. '
            if save_min > 0 and save_max > 0 else ''
        )
        source = 'AI-estimated' if ai_costs else 'estimated'
        return {
            'in_network': True,
            'estimated_cost': {'currency': 'USD', 'min': in_min,  'max': in_max},
            'original_cost':  {'currency': 'USD', 'min': out_min, 'max': out_max},
            'cost_breakdown': breakdown_in,
            'coverage_ratio': coverage_ratio,
            'notice': (
                f'{insurer_name} covers this provider in-network. '
                f'{savings_text}'
                f'Costs are {source} for your {triage_result.get("department", "visit")} visit. '
                f'Final amount depends on your policy deductible and co-insurance terms.'
            ),
        }

    # Out-of-network: no benefit, estimated_cost == original_cost
    source = 'AI-estimated' if ai_costs else 'estimated'
    return {
        'in_network': False,
        'estimated_cost': {'currency': 'USD', 'min': out_min, 'max': out_max},
        'original_cost':  {'currency': 'USD', 'min': out_min, 'max': out_max},
        'cost_breakdown': breakdown_out,
        'coverage_ratio': 'No coverage',
        'notice': (
            f'{insurer_name} does not cover this provider in its network. '
            f'You would pay the full {source} out-of-pocket rate '
            f'(${out_min}–${out_max}) for your {triage_result.get("department", "visit")} visit. '
            f'Consider switching to an in-network provider or a different insurance plan '
            f'to reduce your costs significantly.'
        ),
    }
