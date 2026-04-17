from fastapi import APIRouter, HTTPException

from app.schemas.geo import GeocodeRequest, GeocodeResponse
from app.services.geocode_service import geocode_query


router = APIRouter(prefix='/geo', tags=['geo'])


@router.post('/geocode', response_model=GeocodeResponse)
def geocode(payload: GeocodeRequest) -> GeocodeResponse:
    try:
        result = geocode_query(payload.query)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    return GeocodeResponse(
        query=payload.query,
        normalized_address=result['normalized_address'],
        lat=result['lat'],
        lng=result['lng'],
        source=result['source'],
    )
