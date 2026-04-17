from pydantic import BaseModel


class PatientContact(BaseModel):
    full_name: str
    phone: str
    email: str | None = None


class BookingConfirmation(BaseModel):
    user_confirmed_details: bool
    ai_not_diagnosis_ack: bool


class BookingIntentRequest(BaseModel):
    session_id: str
    provider_id: str
    preferred_time: str
    patient_contact: PatientContact
    confirmation: BookingConfirmation


class BookingIntentResponse(BaseModel):
    booking_intent_id: str
    session_id: str
    status: str
    instructions: list[str]


class SessionSummaryResponse(BaseModel):
    session_id: str
    status: str
    symptom_input: dict
    recommendation: dict
    selected_provider: dict | None
    insurance: dict | None
    booking_intent_id: str | None
    instructions: list[str]
    timeline: list[dict]
