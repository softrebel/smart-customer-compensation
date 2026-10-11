from typing import Annotated, Literal, TypedDict

from pydantic import BaseModel, ConfigDict, Field, field_validator

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


class Proposal(BaseModel):
    model_config = ConfigDict(strict=True, extra="ignore", allow_inf_nan=False)

    issue: Literal["delivery", "damage", "service", "other"] = Field(
        description="Issue category: 'delivery' (late or wrong delivery/courier), 'damage' (damaged item), 'service' (poor service), or 'other'."
    )
    discount_percent: int = Field(
        ge=0, le=100,
        description="Integer discount percentage between 0 and 100.",
    )
    rationale: str = Field(
        min_length=1, max_length=2000,
        description="Short rationale for the proposed compensation.",
    )

    @field_validator("issue", mode="before")
    @classmethod
    def _normalize_issue(cls, value: object) -> object:
        if isinstance(value, str):
            clean = value.strip().lower()
            if clean in {"delivery", "damage", "service", "other"}:
                return clean
            if any(k in clean for k in ("deliver", "courier", "pik", "پیک", "تحویل", "ارسال", "post", "ship", "wrong", "item", "order")):
                return "delivery"
            if any(k in clean for k in ("damag", "broken", "خراب", "شکست", "معیوب")):
                return "damage"
            if any(k in clean for k in ("servic", "سرویس", "پشتیبان", "support")):
                return "service"
            return "other"
        return value

    @field_validator("discount_percent", mode="before")
    @classmethod
    def _normalize_int(cls, value: object) -> object:
        if isinstance(value, float) and value.is_integer():
            return int(value)
        return value


class AuditResult(BaseModel):
    model_config = ConfigDict(strict=True, extra="ignore", allow_inf_nan=False)

    is_verified: bool = Field(description="True if compensation complies with policy, False otherwise.")
    reviewed_discount_percent: int = Field(
        ge=0, le=100,
        description="Exact integer discount percentage reviewed.",
    )
    feedback: str = Field(
        min_length=1, max_length=2000,
        description="Compliance audit feedback explaining approval or required adjustments.",
    )

    @field_validator("reviewed_discount_percent", mode="before")
    @classmethod
    def _normalize_int(cls, value: object) -> object:
        if isinstance(value, float) and value.is_integer():
            return int(value)
        return value


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
