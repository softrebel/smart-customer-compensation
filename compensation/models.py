from typing import Annotated, Literal, TypedDict

from pydantic import BaseModel, ConfigDict, Field

Identifier = Annotated[str, Field(min_length=1, max_length=128, pattern=r"^[^\s\x00-\x1f\x7f]+$")]


class StrictModel(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid", allow_inf_nan=False)


class Customer(StrictModel):
    customer_id: Identifier
    name: str = Field(min_length=1, max_length=200)
    registration_months: int = Field(ge=0)
    ltv_usd: float = Field(ge=0)
    total_orders: int = Field(ge=0)


class Ticket(StrictModel):
    ticket_id: Identifier
    customer_id: Identifier
    message: str = Field(min_length=1, max_length=16000)
    status: str = Field(min_length=1, max_length=100)


class Proposal(StrictModel):
    issue: Literal["delivery", "damage", "service", "other"]
    discount_percent: int = Field(ge=0, le=100)
    rationale: str = Field(min_length=1, max_length=2000)


class AuditResult(StrictModel):
    is_verified: bool
    reviewed_discount_percent: int = Field(ge=0, le=100)
    feedback: str = Field(min_length=1, max_length=2000)


class State(TypedDict, total=False):
    ticket: Ticket
    profile: Customer
    proposal: Proposal | None
    draft: str
    attempt: int
    audit_feedback: str
    is_verified: bool
    status: Literal["pending", "approved", "manual_review"]
    final_response: str
