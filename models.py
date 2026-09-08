"""
Pydantic models for SplitBill AI.

These models define the structured, validated shape of a restaurant bill
after AI extraction. They are intentionally decoupled from any AI provider:
extractor.py is responsible for turning raw AI output into these models,
and calculator.py consumes them (or the plain values inside them) to do
all financial math with Decimal.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, Field, field_validator, model_validator

# ---------------------------------------------------------------------------
# Confidence handling
# ---------------------------------------------------------------------------

CONFIDENCE_HIGH = 0.90
CONFIDENCE_MEDIUM = 0.70


def _to_decimal_or_none(v) -> Optional[Decimal]:
    """Best-effort coercion to Decimal; unreadable/None values become None."""
    if v is None or v == "":
        return None
    if isinstance(v, Decimal):
        return v
    try:
        s = str(v).strip().replace("₹", "").replace("$", "").replace("€", "").replace("£", "").replace(",", "")
        return Decimal(s) if s else None
    except Exception:
        return None


def confidence_label(score: Optional[float]) -> str:
    """Map a 0.0-1.0 confidence score to a human label."""
    if score is None:
        return "Unknown"
    if score >= CONFIDENCE_HIGH:
        return "High"
    if score >= CONFIDENCE_MEDIUM:
        return "Medium"
    return "Review"


# ---------------------------------------------------------------------------
# Core models
# ---------------------------------------------------------------------------


class BillItem(BaseModel):
    """A single line item on the bill."""

    name: str = Field(..., min_length=1, description="Item name as printed on the bill")
    quantity: Decimal = Field(default=Decimal("1"), description="Quantity purchased")
    unit_price: Optional[Decimal] = Field(default=None, description="Price per unit")
    total: Decimal = Field(..., description="Line item total (quantity * unit_price)")
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)

    @field_validator("unit_price", mode="before")
    @classmethod
    def _coerce_unit_price(cls, v):
        return _to_decimal_or_none(v)

    @field_validator("quantity", mode="before")
    @classmethod
    def _coerce_quantity(cls, v):
        parsed = _to_decimal_or_none(v)
        if parsed is None or parsed <= 0:
            return Decimal("1")
        return parsed

    @field_validator("total", mode="before")
    @classmethod
    def _coerce_total(cls, v):
        # total is required but AI may return null/unreadable -> default 0
        # rather than crash; the human-review step lets the user fix it.
        parsed = _to_decimal_or_none(v)
        return parsed if parsed is not None else Decimal("0")

    @property
    def confidence_label(self) -> str:
        return confidence_label(self.confidence)


class FieldConfidence(BaseModel):
    """Confidence scores for the top-level scalar fields of a bill."""

    restaurant_name: float = Field(default=0.5, ge=0.0, le=1.0)
    date: float = Field(default=0.5, ge=0.0, le=1.0)
    subtotal: float = Field(default=0.5, ge=0.0, le=1.0)
    discount: float = Field(default=0.5, ge=0.0, le=1.0)
    tax: float = Field(default=0.5, ge=0.0, le=1.0)
    service_charge: float = Field(default=0.5, ge=0.0, le=1.0)
    total: float = Field(default=0.5, ge=0.0, le=1.0)


class Bill(BaseModel):
    """The full structured bill, after extraction and (optionally) human edits."""

    restaurant_name: Optional[str] = None
    date: Optional[str] = None
    items: list[BillItem] = Field(default_factory=list)

    subtotal: Optional[Decimal] = None
    discount: Optional[Decimal] = Decimal("0")
    tax: Optional[Decimal] = Decimal("0")
    service_charge: Optional[Decimal] = Decimal("0")
    total: Optional[Decimal] = None

    field_confidence: FieldConfidence = Field(default_factory=FieldConfidence)
    is_demo: bool = False
    raw_notes: Optional[str] = Field(
        default=None, description="Free-text notes from the AI, e.g. unreadable areas"
    )

    @field_validator("subtotal", "total", mode="before")
    @classmethod
    def _coerce_optional_decimal(cls, v):
        return _to_decimal_or_none(v)

    @field_validator("discount", "tax", "service_charge", mode="before")
    @classmethod
    def _coerce_defaulted_decimal(cls, v):
        parsed = _to_decimal_or_none(v)
        return parsed if parsed is not None else Decimal("0")

    @field_validator("field_confidence", mode="before")
    @classmethod
    def _coerce_field_confidence(cls, v):
        if hasattr(v, "model_dump"):
            return v.model_dump()
        if hasattr(v, "dict"):
            return v.dict()
        if isinstance(v, dict):
            return v
        return FieldConfidence()

    @model_validator(mode="after")
    def _fill_subtotal(self):
        # If subtotal missing, derive it from the line items so downstream
        # math never has to special-case a None subtotal.
        if self.subtotal is None:
            self.subtotal = sum((i.total for i in self.items), Decimal("0"))
        return self

    def items_sum(self) -> Decimal:
        return sum((i.total for i in self.items), Decimal("0"))

    def computed_total(self) -> Decimal:
        """Subtotal - discount + tax + service_charge."""
        subtotal = self.subtotal if self.subtotal is not None else self.items_sum()
        return subtotal - self.discount + self.tax + self.service_charge


# ---------------------------------------------------------------------------
# Member / assignment models
# ---------------------------------------------------------------------------


class Member(BaseModel):
    name: str = Field(..., min_length=1)


class ItemAssignment(BaseModel):
    """Which members share a given bill item (by index into Bill.items)."""

    item_index: int
    member_names: list[str] = Field(default_factory=list)

    @field_validator("member_names")
    @classmethod
    def _at_least_one(cls, v):
        if not v:
            raise ValueError("Each item must be assigned to at least one member")
        return v


class PersonBreakdown(BaseModel):
    """Final computed breakdown for a single person."""

    name: str
    items: list[dict] = Field(default_factory=list)  # [{name, share, is_shared}]
    gross_consumption: Decimal
    discount_share: Decimal
    net_consumption: Decimal
    tax_share: Decimal
    service_charge_share: Decimal
    final_amount: Decimal


class SplitResult(BaseModel):
    """Full result of the calculation for all people."""

    people: list[PersonBreakdown]
    bill_total: Decimal
    allocated_total: Decimal
    difference: Decimal
    is_reconciled: bool
    warnings: list[str] = Field(default_factory=list)

    model_config = {"arbitrary_types_allowed": True}
