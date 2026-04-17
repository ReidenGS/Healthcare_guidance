from __future__ import annotations

import json
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from app.core.config import get_effective_openai_key, get_settings
from app.services.followup_memory import canonicalize_symptom_label
from app.services.redflag_rag import redflag_rag

SYSTEM_PROMPT = (
    'You are a medical triage routing assistant. '
    'Your job is NAVIGATION, not diagnosis. '
    'Given the patient symptoms and any follow-up answers, determine the most appropriate '
    'medical department or specialty to route the patient to. '
    'The "department" field MUST be a specific clinical specialty '
    '(e.g. Cardiology, Pulmonology, Orthopedics, Neurology, Gastroenterology, Dermatology, ENT, etc.). '
    'NEVER use care-setting labels such as "Urgent Care", "Primary Care", "Emergency Room", or "ER" '
    'as the department value — those belong only in the care_path field. '
    'Even when care_path is URGENT_CARE or ER, you must still identify the most likely specialty '
    'the patient will be seen by (e.g. chest pain → Cardiology, breathing difficulty → Pulmonology). '
    '\n\nSEVERITY & ESCALATION RULES (strictly follow these):\n'
    '- care_path=ER and red_flags_detected non-empty ONLY when ALL of the following are true:\n'
    '  (a) severity_0_10 >= 7, OR patient reports sudden onset / rapidly worsening symptoms\n'
    '  (b) AND at least one TRUE alarm feature is present: crushing/pressure chest pain, '
    'radiation to arm/jaw, loss of consciousness, severe difficulty breathing, stroke signs, '
    'uncontrolled heavy bleeding, or anaphylaxis\n'
    '- For chest discomfort / chest pain with severity_0_10 <= 6 and NO alarm features: '
    'use care_path=URGENT_CARE, risk_level=MEDIUM, red_flags_detected=[]\n'
    '- For chest discomfort / chest pain with severity_0_10 4-6 and uncertain alarm features: '
    'use care_path=URGENT_CARE, risk_level=MEDIUM, and ask follow-up questions\n'
    '- LOW risk: severity <= 3, no red flags → PRIMARY_CARE or SPECIALIST\n'
    '- MEDIUM risk: severity 4-6 or mild alarm features → URGENT_CARE\n'
    '- HIGH risk: severity >= 7 with confirmed alarm features → ER\n'
    '- Do NOT add items to red_flags_detected for vague or mild symptoms\n'
    '\n\nconfidence_percent represents how certain you are that you have identified '
    'the correct department or specialty for this patient. '
    'Rate it purely based on how clearly the available information points to one specific department.\n'
    '\nReturn ONLY valid JSON with these exact keys:\n'
    '  department        - string, a specific clinical specialty (e.g. Cardiology, Pulmonology, Neurology); NEVER "Urgent Care", "Primary Care", or "Emergency Room"\n'
    '  care_path         - string, one of: ER, URGENT_CARE, PRIMARY_CARE, SPECIALIST\n'
    '  confidence_percent - integer 1-100, your honest assessment of routing certainty\n'
    '  risk_level        - string, one of: LOW, MEDIUM, HIGH\n'
    '  visit_needed      - boolean, true if patient should visit a clinic/hospital now; '
    'false only when home/self-care is sufficient\n'
    '  reasons           - list of 1-3 short strings explaining the routing decision\n'
    '  red_flags_detected - list of strings, empty list [] if none\n'
    '  likely_symptoms   - list of exactly 4 plausible additional symptoms to ask '
    'when confidence is low; each MUST be a first-person declarative statement '
    '(e.g. "I have nausea", "My pain worsens after meals"), NOT a question\n'
    'No markdown, no extra text outside the JSON object.'
)


class TriageAgent:
    """GPT-based triage agent with optional Tavily web-search support.

    Flow:
    1) First run GPT routing with symptom/follow-up context only.
    2) If confidence is low, optionally query Tavily for supplemental routing context.
    2) Evaluate whether current symptom information is sufficient for department routing.
    3) Output confidence_percent (1-100) for routing certainty.
    4) If certainty is low, generate 4 likely additional symptoms for guided selection.
    """

    def __init__(self) -> None:
        settings = get_settings()
        self.enabled = bool(settings.openai_api_key)
        self.model = settings.openai_model
        self.client = (
            ChatOpenAI(model=settings.openai_model, api_key=settings.openai_api_key, temperature=0)
            if self.enabled
            else None
        )

    def _get_client(self) -> 'ChatOpenAI | None':
        """Return a ChatOpenAI client using the per-request key override when present."""
        override_key = get_effective_openai_key()
        if override_key and override_key != get_settings().openai_api_key:
            return ChatOpenAI(model=self.model, api_key=override_key, temperature=0)
        return self.client

    def _is_enabled(self) -> bool:
        """True when an OpenAI key is available (env default or per-request override)."""
        return bool(get_effective_openai_key())

    # ------------------------------------------------------------------
    # Static helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _safe_percent(value: Any, default: int = 55) -> int:
        try:
            v = int(round(float(value)))
            return max(1, min(100, v))
        except Exception:
            return default

    @staticmethod
    def _safe_care_path(value: str) -> str:
        allowed = {'ER', 'URGENT_CARE', 'PRIMARY_CARE', 'SPECIALIST'}
        return value if value in allowed else 'PRIMARY_CARE'

    @staticmethod
    def _safe_bool(value: Any, default: bool = True) -> bool:
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            s = value.strip().lower()
            if s in {'true', 'yes', '1'}:
                return True
            if s in {'false', 'no', '0'}:
                return False
        if isinstance(value, (int, float)):
            return bool(value)
        return default

    @staticmethod
    def _safe_department(value: str) -> str:
        """Return value if it is in the known department list, else keep as-is
        (GPT may occasionally return a close variant; we trust it over a hard override)."""
        cleaned = (value or '').strip()
        return cleaned if cleaned else 'Primary Care'

    @staticmethod
    def _to_first_person_statement(label: str) -> str:
        text = (label or '').strip()
        if not text:
            return ''

        lowered = text.lower().strip(' ?.')
        question_prefixes = [
            'do you have ',
            'are you ',
            'have you ',
            'is there ',
            'did you ',
            'can you ',
            'does the pain ',
            'do symptoms ',
            'are your ',
        ]
        for p in question_prefixes:
            if lowered.startswith(p):
                lowered = lowered[len(p):]
                break

        if lowered.startswith('i '):
            sentence = lowered
        elif lowered.startswith('my '):
            # Already possessive first-person — keep as-is (e.g. "My pain worsens after meals")
            sentence = lowered
        elif lowered.startswith('pain worsens') or lowered.startswith('pain radiates'):
            sentence = f'my {lowered}'
        elif lowered.startswith('symptoms'):
            sentence = f'my {lowered}'
        else:
            sentence = f'i have {lowered}'

        sentence = sentence.strip()
        if not sentence.endswith('.'):
            sentence += '.'
        return sentence[0].upper() + sentence[1:]

    def _invoke_gpt_routing(
        self,
        symptom_input: dict[str, Any],
        answers: list[dict[str, Any]],
        context_block: str = '',
    ) -> dict[str, Any]:
        client = self._get_client()
        if client is None:
            raise RuntimeError('OpenAI client is not initialized')

        prompt = [
            SystemMessage(content=SYSTEM_PROMPT),
            HumanMessage(
                content=(
                    f'Symptom input: {symptom_input}\n'
                    f'Selected follow-up answers: {answers or []}'
                    f'{context_block}'
                )
            ),
        ]
        msg = client.invoke(prompt)
        raw = msg.content if isinstance(msg.content, str) else str(msg.content)
        raw = raw.strip().removeprefix('```json').removeprefix('```').removesuffix('```').strip()
        parsed = json.loads(raw)

        return {
            'parsed': parsed,
            'percent': self._safe_percent(parsed.get('confidence_percent'), default=55),
            'care_path': self._safe_care_path(parsed.get('care_path', 'PRIMARY_CARE')),
            'department': self._safe_department(parsed.get('department', 'Primary Care')),
            'visit_needed': self._safe_bool(parsed.get('visit_needed'), default=True),
            'likely_symptoms': (
                parsed.get('likely_symptoms')
                if isinstance(parsed.get('likely_symptoms'), list)
                else []
            ),
        }

    # ------------------------------------------------------------------
    # Fallback (no OpenAI key)
    # ------------------------------------------------------------------

    def _fallback_assess(
        self, symptom_input: dict[str, Any], answers: list[dict[str, Any]] | None = None
    ) -> dict[str, Any]:
        text = (symptom_input.get('chief_complaint') or '').lower()
        severity = int(symptom_input.get('severity_0_10', 0) or 0)
        answers = answers or []
        positive_count = len([a for a in answers if a.get('value') is True])
        answered_count = len([a for a in answers if a.get('question_id') != 'additional_note'])

        red_flags: list[str] = []
        # Only flag as emergency red flag if severity is high enough (>=7) or
        # the symptom is unambiguously life-threatening (e.g. loss of consciousness)
        hard_emergency_keywords = [
            'loss of consciousness', 'stroke', 'heart attack', 'severe allergic',
            'heavy bleeding',
        ]
        soft_emergency_keywords = [
            'chest pain', 'shortness of breath',
        ]
        if any(k in text for k in hard_emergency_keywords):
            red_flags.append('Potential emergency symptom detected')
        elif any(k in text for k in soft_emergency_keywords) and severity >= 7:
            red_flags.append('High-severity chest/respiratory symptom detected')

        # Base heuristic certainty
        confidence_percent = 35 + severity * 3 + answered_count * 5 + positive_count * 2

        # Department routing by symptom keyword
        if any(k in text for k in ['chest pain', 'palpitation', 'heart', 'cardiac', 'chest hurt', 'chest discomfort']):
            department = 'Cardiology'
            care_path = 'ER' if severity >= 7 else 'URGENT_CARE'
            confidence_percent += 20
            likely = [
                'I have chest tightness or pressure.',
                'I have shortness of breath at rest.',
                'I have palpitations or irregular heartbeat.',
                'I have pain radiating to my left arm or jaw.',
            ]
        elif any(k in text for k in ['eye', 'vision', 'blurry', 'sight', 'blind']):
            department = 'Ophthalmology'
            care_path = 'URGENT_CARE' if severity >= 6 else 'SPECIALIST'
            confidence_percent += 20
            likely = [
                'I have sudden loss of vision in one or both eyes.',
                'I see floaters or flashes of light.',
                'I have eye pain or redness.',
                'I have double vision.',
            ]
        elif any(k in text for k in ['ear', 'hearing', 'throat', 'tonsil', 'nose', 'sinus', 'sneezing']):
            department = 'ENT (Ear, Nose & Throat)'
            care_path = 'URGENT_CARE' if severity >= 6 else 'PRIMARY_CARE'
            confidence_percent += 18
            likely = [
                'I have ear pain or discharge.',
                'I have difficulty swallowing.',
                'I have ringing in my ears (tinnitus).',
                'I have nasal congestion lasting more than 2 weeks.',
            ]
        elif any(k in text for k in ['skin', 'rash', 'itching', 'acne', 'lesion', 'hive']):
            department = 'Dermatology'
            care_path = 'SPECIALIST'
            confidence_percent += 18
            likely = [
                'I have a spreading rash or skin discoloration.',
                'I have itching that worsens at night.',
                'I have open sores or ulcers on my skin.',
                'I noticed a changing mole or new growth.',
            ]
        elif any(k in text for k in ['joint', 'bone', 'fracture', 'knee', 'back', 'spine', 'shoulder', 'ankle', 'wrist', 'orthopedic']):
            department = 'Orthopedics'
            care_path = 'URGENT_CARE' if severity >= 6 else 'SPECIALIST'
            confidence_percent += 18
            likely = [
                'I have swelling or deformity at the injury site.',
                'I cannot bear weight on the affected limb.',
                'My pain is worse with movement.',
                'I have numbness or tingling in the affected area.',
            ]
        elif any(k in text for k in ['headache', 'dizzy', 'vertigo', 'migraine', 'seizure', 'numbness', 'tingling', 'stroke']):
            department = 'Neurology'
            care_path = 'ER' if severity >= 8 else ('URGENT_CARE' if severity >= 5 else 'SPECIALIST')
            confidence_percent += 15
            likely = [
                'I have blurred or double vision.',
                'I have one-sided weakness or numbness.',
                'I have a sudden severe headache.',
                'I have difficulty speaking or understanding speech.',
            ]
        elif any(k in text for k in ['abdominal', 'stomach', 'nausea', 'vomit', 'diarrhea', 'bowel', 'constipation', 'acid reflux']):
            department = 'Gastroenterology'
            care_path = 'URGENT_CARE' if severity >= 6 else 'PRIMARY_CARE'
            confidence_percent += 18
            likely = [
                'I have nausea or vomiting.',
                'I have a fever above 38C (100.4F).',
                'My pain worsens after meals.',
                'I have black stool or blood in stool.',
            ]
        elif any(k in text for k in ['cough', 'breathing', 'lung', 'asthma', 'wheezing', 'respiratory']):
            department = 'Pulmonology'
            care_path = 'URGENT_CARE' if severity >= 6 else 'PRIMARY_CARE'
            confidence_percent += 15
            likely = [
                'I have shortness of breath at rest or during light activity.',
                'I cough up blood or brown mucus.',
                'I have wheezing when I breathe.',
                'My breathing difficulty worsens when lying down.',
            ]
        elif any(k in text for k in ['urination', 'urine', 'kidney', 'bladder', 'prostate', 'urinary']):
            department = 'Urology'
            care_path = 'URGENT_CARE' if severity >= 6 else 'SPECIALIST'
            confidence_percent += 18
            likely = [
                'I have pain or burning during urination.',
                'I see blood in my urine.',
                'I have frequent urges to urinate but little output.',
                'I have flank or lower back pain on one side.',
            ]
        elif any(k in text for k in ['menstrual', 'vaginal', 'pregnancy', 'ovarian', 'pelvic', 'period', 'gynecology']):
            department = 'Gynecology / OB-GYN'
            care_path = 'URGENT_CARE' if severity >= 6 else 'SPECIALIST'
            confidence_percent += 18
            likely = [
                'I have abnormal vaginal discharge.',
                'My periods have been irregular or very heavy.',
                'I have pelvic pain that is getting worse.',
                'I may be pregnant.',
            ]
        elif any(k in text for k in ['anxiety', 'depression', 'panic', 'mental', 'mood', 'suicidal', 'hallucin']):
            department = 'Psychiatry / Mental Health'
            care_path = 'URGENT_CARE' if severity >= 8 else 'SPECIALIST'
            confidence_percent += 18
            likely = [
                'I have persistent low mood lasting more than 2 weeks.',
                'I have panic attacks.',
                'I have difficulty sleeping.',
                'I have thoughts of harming myself or others.',
            ]
        elif any(k in text for k in ['diabetes', 'thyroid', 'hormone', 'sugar', 'insulin', 'weight gain']):
            department = 'Endocrinology'
            care_path = 'SPECIALIST'
            confidence_percent += 15
            likely = [
                'I have extreme thirst and frequent urination.',
                'I have unexplained weight changes.',
                'I feel very fatigued despite adequate sleep.',
                'I have cold intolerance or excessive sweating.',
            ]
        else:
            department = 'Primary Care'
            care_path = 'PRIMARY_CARE'
            likely = [
                'I have a fever above 38C (100.4F).',
                'I have shortness of breath.',
                'My symptoms keep worsening over the last 12 hours.',
                'I have severe fatigue or dehydration signs.',
            ]

        # Escalate to ER only when red flags are present AND severity is serious (>=7),
        # OR severity is extreme (>=9) regardless of keywords
        if (red_flags and severity >= 7) or severity >= 9:
            department = 'Emergency Department'
            care_path = 'ER'
            confidence_percent = max(confidence_percent, 92)

        confidence_percent = max(1, min(100, confidence_percent))
        visit_needed = not (
            department == 'Primary Care'
            and care_path == 'PRIMARY_CARE'
            and severity <= 3
            and len(red_flags) == 0
        )
        return {
            'department': department,
            'care_path': care_path,
            'confidence_percent': confidence_percent,
            'confidence': round(confidence_percent / 100, 2),
            'risk_level': 'HIGH' if ((red_flags and severity >= 7) or severity >= 9) else ('MEDIUM' if severity >= 4 else 'LOW'),
            'visit_needed': visit_needed,
            'reasons': [
                'Routing based on symptom keywords, severity score, and follow-up selections.',
                'This is AI care navigation guidance, not a medical diagnosis.',
            ],
            'red_flags_detected': red_flags,
            'likely_symptoms': likely,
        }

    # ------------------------------------------------------------------
    # Main assessment (calls GPT with optional web-search context)
    # ------------------------------------------------------------------

    def assess(
        self, symptom_input: dict[str, Any], answers: list[dict[str, Any]] | None = None
    ) -> dict[str, Any]:
        answers = answers or []
        chief_complaint = (symptom_input.get('chief_complaint') or symptom_input.get('free_text') or '').strip()
        severity = int(symptom_input.get('severity_0_10', 0) or 0)

        # ------------------------------------------------------------------
        # Step 1: Offline RAG red-flag retrieval (always runs, zero API cost)
        #   Only checks the local vector store — does NOT call Tavily here.
        #   Online red-flag search is a separate, gated step (Step 2b).
        # ------------------------------------------------------------------
        rag_offline_hits = redflag_rag.search(chief_complaint) if chief_complaint else []
        rag_confirmed_redflag: bool = len(rag_offline_hits) > 0
        rag_conditions: list[str] = list({h['condition'] for h in rag_offline_hits})

        if not self._is_enabled():
            result = self._fallback_assess(symptom_input, answers)
            # Merge RAG-confirmed red flags into fallback result
            if rag_confirmed_redflag and rag_conditions:
                rag_flag = f'Matches known red-flag pattern: {", ".join(rag_conditions)}'
                if rag_flag not in result['red_flags_detected']:
                    result['red_flags_detected'].append(rag_flag)
                # Only escalate to ER if severity also justifies it
                if severity >= 7 and result['care_path'] != 'ER':
                    result['care_path'] = 'ER'
                    result['department'] = 'Emergency Department'
                    result['risk_level'] = 'HIGH'
            return result

        # ------------------------------------------------------------------
        # Step 2: First-pass GPT routing (no Tavily by default)
        # ------------------------------------------------------------------
        context_block = ''

        if rag_confirmed_redflag:
            top_phrases = [h['phrase'] for h in rag_offline_hits[:3]]
            rag_context = (
                f'RED FLAG MATCH (offline vector store): patient description matches '
                f'known red-flag patterns for {", ".join(rag_conditions)}. '
                f'Matched phrases: {"; ".join(top_phrases)}.'
            )
            context_block = f'\n\nRed-flag retrieval context:\n{rag_context}'

        try:
            gpt_result = self._invoke_gpt_routing(symptom_input, answers, context_block=context_block)
            parsed = gpt_result['parsed']
            percent = gpt_result['percent']
            care_path = gpt_result['care_path']
            department = gpt_result['department']
            visit_needed = gpt_result['visit_needed']

            likely = gpt_result['likely_symptoms']
            likely = [x.strip() for x in likely if isinstance(x, str) and x.strip()][:4]
            if len(likely) < 4:
                fallback = self._fallback_assess(symptom_input, answers)
                likely = fallback['likely_symptoms']
            likely = [self._to_first_person_statement(x) for x in likely][:4]

            # Confidence is entirely determined by GPT — no formula adjustments.
            calibrated_percent = percent

            # ------------------------------------------------------------------
            # Step 4: Merge RAG-confirmed red flags into GPT output
            #   If RAG offline match confirmed a red-flag condition, ensure it
            #   appears in red_flags_detected regardless of GPT's output.
            # ------------------------------------------------------------------
            gpt_red_flags: list[str] = (
                parsed.get('red_flags_detected')
                if isinstance(parsed.get('red_flags_detected'), list)
                else []
            )
            if rag_confirmed_redflag and rag_conditions:
                rag_flag = f'Matches known red-flag pattern: {", ".join(rag_conditions)}'
                if rag_flag not in gpt_red_flags:
                    gpt_red_flags.append(rag_flag)
                # Upgrade care_path only when severity warrants it
                if severity >= 7 and care_path != 'ER':
                    care_path = 'ER'
                    department = 'Emergency Department'

            risk_level = str(
                parsed.get('risk_level') or ('HIGH' if care_path == 'ER' else 'MEDIUM')
            )

            return {
                'department': department,
                'care_path': care_path,
                'confidence_percent': calibrated_percent,
                'confidence': round(calibrated_percent / 100, 2),
                'risk_level': risk_level,
                'visit_needed': visit_needed,
                'reasons': (
                    parsed.get('reasons')
                    if isinstance(parsed.get('reasons'), list)
                    else ['AI-generated routing rationale.']
                ),
                'red_flags_detected': gpt_red_flags,
                'likely_symptoms': likely,
            }
        except Exception:
            return self._fallback_assess(symptom_input, answers)

    # ------------------------------------------------------------------
    # Follow-up question generation
    # ------------------------------------------------------------------

    def generate_follow_up_questions(
        self,
        symptom_input: dict[str, Any],
        answers: list[dict[str, Any]] | None = None,
        round_index: int = 1,
        asked_question_ids: list[str] | None = None,
        banned_symptoms: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        assessment = self.assess(symptom_input, answers)
        likely_symptoms = assessment.get('likely_symptoms', [])
        asked_ids = set(asked_question_ids or [])
        banned = set(x for x in (banned_symptoms or []) if x)

        generic_backfill = [
            'I have a fever above 38C (100.4F).',
            'I have shortness of breath.',
            'My symptoms are getting worse in the last 12 hours.',
            'I have dehydration signs (dry mouth or reduced urination).',
            'I have severe fatigue.',
            'I have persistent vomiting.',
            'I feel faint when standing up.',
            'I have chest discomfort.',
        ]
        pool: list[str] = []
        for label in [self._to_first_person_statement(x) for x in likely_symptoms] + generic_backfill:
            normalized = canonicalize_symptom_label(label)
            if not normalized:
                continue
            if normalized in banned:
                continue
            if any(canonicalize_symptom_label(x) == normalized for x in pool):
                continue
            pool.append(label)

        questions: list[dict[str, Any]] = []
        for idx, symptom in enumerate(pool[:4], start=1):
            question_id = f'r{round_index}_q{idx}'
            if question_id in asked_ids:
                continue
            questions.append(
                {
                    'question_id': question_id,
                    'label': symptom,
                    'input_type': 'boolean',
                    'required': True,
                }
            )

        return questions


triage_agent = TriageAgent()
