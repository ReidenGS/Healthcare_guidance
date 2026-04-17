from pydantic import BaseModel


class GeocodeRequest(BaseModel):
    query: str = ''


class GeocodeResponse(BaseModel):
    query: str
    normalized_address: str
    lat: float
    lng: float
    source: str
