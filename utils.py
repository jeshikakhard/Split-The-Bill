"""
utils.py - formatting, validation and small UI helpers used across the app.
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Optional

from models import CONFIDENCE_HIGH, CONFIDENCE_MEDIUM


def format_money(value: Optional[Decimal], currency: str = "\u20b9") -> str:
    """Format a Decimal (or None) as a currency string, never crashing."""
    if value is None:
        return "N/A"
    try:
        return f"{currency}{Decimal(value):.2f}"
    except (InvalidOperation, TypeError):
        return "N/A"


def safe_decimal(value, default: Optional[Decimal] = None) -> Optional[Decimal]:
    """Parse a user-editable string/number into a Decimal, stripping symbols and commas, never raising."""
    if value is None:
        return default
    if isinstance(value, Decimal):
        return value
    s = str(value).strip().replace("₹", "").replace("$", "").replace("€", "").replace("£", "").replace(",", "")
    if not s:
        return default
    try:
        return Decimal(s)
    except (InvalidOperation, ValueError):
        return default


def confidence_badge(score: Optional[float]) -> str:
    """Return an emoji + label badge for a confidence score, for Streamlit captions."""
    if score is None:
        return "\u26aa Unknown"
    if score >= CONFIDENCE_HIGH:
        return f"\U0001f7e2 High ({score:.0%})"
    if score >= CONFIDENCE_MEDIUM:
        return f"\U0001f7e1 Medium ({score:.0%})"
    return f"\U0001f534 Review ({score:.0%})"


def confidence_color(score: Optional[float]) -> str:
    """CSS-ish color name for a confidence score, for styling widgets."""
    if score is None:
        return "gray"
    if score >= CONFIDENCE_HIGH:
        return "green"
    if score >= CONFIDENCE_MEDIUM:
        return "orange"
    return "red"


def validate_member_names(names: list[str]) -> tuple[bool, str]:
    """Validate the 2-3 member name inputs. Returns (is_valid, error_message)."""
    cleaned = [n.strip() for n in names if n and n.strip()]
    if len(cleaned) < 2:
        return False, "Please enter at least 2 members."
    if len(cleaned) > 3:
        return False, "Please enter at most 3 members."
    if len(set(cleaned)) != len(cleaned):
        return False, "Member names must be unique."
    return True, ""


def all_items_assigned(assignments: dict[int, list[str]], num_items: int) -> tuple[bool, list[int]]:
    """Check every item index [0, num_items) has at least one assignee."""
    missing = [i for i in range(num_items) if not assignments.get(i)]
    return len(missing) == 0, missing
