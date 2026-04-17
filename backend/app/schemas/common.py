from typing import Any

from pydantic import BaseModel, Field


class ErrorDetail(BaseModel):
    field: str
    issue: str


class ApiError(BaseModel):
    code: str
    message: str
    details: list[ErrorDetail] = Field(default_factory=list)
    trace_id: str


class ErrorResponse(BaseModel):
    error: ApiError


def error_payload(code: str, message: str, details: list[dict[str, Any]] | None = None, trace_id: str = 'trc_local') -> dict[str, Any]:
    return {
        'error': {
            'code': code,
            'message': message,
            'details': details or [],
            'trace_id': trace_id,
        }
    }
