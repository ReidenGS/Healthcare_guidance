from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.v1 import booking, geo, insurance, providers, triage
from app.core.request_context import (
    gemini_key_override,
    google_maps_key_override,
    openai_key_override,
    tavily_key_override,
)
from app.schemas.common import error_payload

app = FastAPI(title='Healthcare Guidance Backend', version='0.1.0')

app.add_middleware(
    CORSMiddleware,
    allow_origins=['*'],
    allow_credentials=True,
    allow_methods=['*'],
    allow_headers=['*'],
)


@app.middleware('http')
async def extract_api_keys(request: Request, call_next):
    """Read optional per-request API key headers and expose them via context vars."""
    openai_key_override.set(request.headers.get('X-OpenAI-Key', ''))
    google_maps_key_override.set(request.headers.get('X-Google-Maps-Key', ''))
    gemini_key_override.set(request.headers.get('X-Gemini-Key', ''))
    tavily_key_override.set(request.headers.get('X-Tavily-Key', ''))
    return await call_next(request)


@app.exception_handler(Exception)
async def global_exception_handler(_: Request, exc: Exception) -> JSONResponse:
    return JSONResponse(
        status_code=500,
        content=error_payload('INTERNAL_ERROR', str(exc)),
    )


@app.get('/api/health')
def health() -> dict:
    return {'status': 'ok'}


app.include_router(triage.router, prefix='/api/v1')
app.include_router(geo.router, prefix='/api/v1')
app.include_router(providers.router, prefix='/api/v1')
app.include_router(insurance.router, prefix='/api/v1')
app.include_router(booking.router, prefix='/api/v1')
