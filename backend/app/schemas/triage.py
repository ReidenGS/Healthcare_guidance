from typing import Any, Literal

from pydantic import BaseModel, Field


class UserProfile(BaseModel):
    age: int
    sex: str
    city: str
    insurance_plan: str | None = None


class SymptomInput(BaseModel):
    chief_complaint: str
    duration_hours: int = 12
    severity_0_10: int = Field(ge=0, le=10)
    free_text: str | None = None


class ConsentInput(BaseModel):
    hipaa_ack: bool
    ai_guidance_ack: bool


class CreateSessionRequest(BaseModel):
    user_profile: UserProfile
    symptom_input: SymptomInput
    consent: ConsentInput


class FollowUpQuestion(BaseModel):
    question_id: str
    label: str
    input_type: Literal['boolean', 'single_select', 'multi_select', 'text', 'number'] = 'boolean'
    required: bool = True
    options: list[dict[str, str]] | None = None
    confidence_boost: int = 1  # 1-4: selecting this symptom raises confidence by this many percent


class CreateSessionResponse(BaseModel):
    session_id: str
    status: str
    risk_level: str
    confidence: float
    confidence_percent: int
    questions: list[FollowUpQuestion]
    disclaimer: str


class AnswerItem(BaseModel):
    question_id: str
    value: Any


class SubmitAnswersRequest(BaseModel):
    answers: list[AnswerItem]
    additional_note: str | None = None
    none_of_above: bool = False
    force_recommend: bool = False  # skip confidence gate; generate recommendation immediately


class SubmitAnswersResponse(BaseModel):
    session_id: str
    status: str
    confidence: float
    confidence_percent: int
    risk_level: str
    questions: list[FollowUpQuestion] = Field(default_factory=list)


class RecommendationResponse(BaseModel):
    session_id: str
    status: str
    department: str
    care_path: str
    confidence: float
    confidence_percent: int
    visit_needed: bool = True
    reasons: list[str]
    red_flags_detected: list[str]
    disclaimer: str


class RecommendationFeedbackRequest(BaseModel):
    decision: Literal['AGREE', 'DISAGREE']
    comment: str | None = None


class RecommendationFeedbackResponse(BaseModel):
    session_id: str
    next_status: str
