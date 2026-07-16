from pydantic import BaseModel, Field


class BlockRequest(BaseModel):
    blocked: bool


class PremiumGrantRequest(BaseModel):
    days: int = Field(ge=1, le=365)
