from decimal import Decimal

import pytest
from pydantic import ValidationError

from models import Bill, BillItem, ItemAssignment, confidence_label


def test_bill_item_basic_validation():
    item = BillItem(name="Coke", quantity=1, unit_price=80, total=80, confidence=0.9)
    assert item.name == "Coke"
    assert item.total == Decimal("80")
    assert item.confidence_label == "High"


def test_bill_item_null_price_does_not_crash():
    # AI could not read the unit price -> should become None, not raise.
    item = BillItem(name="Mystery Item", quantity=1, unit_price=None, total=100, confidence=0.4)
    assert item.unit_price is None
    assert item.confidence_label == "Review"


def test_bill_item_unreadable_numeric_string_falls_back():
    item = BillItem(name="Smudged", quantity="???", unit_price="n/a", total=50, confidence=0.3)
    # invalid quantity falls back to 1, invalid unit_price becomes None
    assert item.quantity == Decimal("1")
    assert item.unit_price is None


def test_bill_item_requires_name():
    with pytest.raises(ValidationError):
        BillItem(name="", quantity=1, total=10, confidence=0.5)


def test_bill_fills_missing_subtotal_from_items():
    bill = Bill(
        items=[
            BillItem(name="A", total=100, confidence=0.9),
            BillItem(name="B", total=50, confidence=0.9),
        ]
    )
    assert bill.subtotal == Decimal("150")


def test_bill_missing_tax_and_service_default_to_zero():
    bill = Bill(items=[BillItem(name="A", total=100, confidence=0.9)])
    assert bill.tax == Decimal("0")
    assert bill.discount == Decimal("0")
    assert bill.service_charge == Decimal("0")


def test_bill_computed_total():
    bill = Bill(
        items=[BillItem(name="A", total=100, confidence=0.9)],
        subtotal=Decimal("100"),
        tax=Decimal("10"),
        service_charge=Decimal("5"),
        discount=Decimal("0"),
    )
    assert bill.computed_total() == Decimal("115")


def test_item_assignment_requires_at_least_one_member():
    with pytest.raises(ValidationError):
        ItemAssignment(item_index=0, member_names=[])


def test_confidence_label_thresholds():
    assert confidence_label(0.95) == "High"
    assert confidence_label(0.75) == "Medium"
    assert confidence_label(0.5) == "Review"
    assert confidence_label(None) == "Unknown"
