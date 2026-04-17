from pydantic import BaseModel


class InsuranceCheckRequest(BaseModel):
    session_id: str
    provider_id: str
    insurance_plan: str


class CostRange(BaseModel):
    currency: str = 'CNY'
    min: int
    max: int


class CostBreakdownItem(BaseModel):
    item: str
    range: str


class InsuranceCheckResponse(BaseModel):
    session_id: str
    status: str
    provider_id: str
    insurance_plan: str
    in_network: bool
    estimated_cost: CostRange
    original_cost: CostRange
    cost_breakdown: list[CostBreakdownItem]
    coverage_ratio: str
    notice: str
