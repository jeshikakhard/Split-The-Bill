from decimal import Decimal
import pytest

from extractor import _parse_ai_json, load_demo_bill, ExtractionError
from models import _to_decimal_or_none, Bill, BillItem
from utils import (
    all_items_assigned,
    confidence_badge,
    format_money,
    safe_decimal,
    validate_member_names,
)


def test_safe_decimal_handles_currency_and_commas():
    assert safe_decimal("₹500") == Decimal("500")
    assert safe_decimal("₹ 1,180.50") == Decimal("1180.50")
    assert safe_decimal("$50.25") == Decimal("50.25")
    assert safe_decimal("  300  ") == Decimal("300")
    assert safe_decimal("", Decimal("0")) == Decimal("0")
    assert safe_decimal(None, Decimal("10")) == Decimal("10")
    assert safe_decimal("not_a_number", Decimal("5")) == Decimal("5")


def test_to_decimal_or_none_handles_currencies():
    assert _to_decimal_or_none("₹600") == Decimal("600")
    assert _to_decimal_or_none("1,357.00") == Decimal("1357.00")
    assert _to_decimal_or_none(None) is None
    assert _to_decimal_or_none("unreadable") is None


def test_validate_member_names():
    # Less than 2
    valid, err = validate_member_names(["OnlyOne"])
    assert not valid
    assert "at least 2" in err

    # Exactly 2
    valid, err = validate_member_names(["Alice", "Bob"])
    assert valid
    assert err == ""

    # Exactly 3
    valid, err = validate_member_names(["Alice", "Bob", "Charlie"])
    assert valid

    # More than 3
    valid, err = validate_member_names(["A", "B", "C", "D"])
    assert not valid
    assert "at most 3" in err

    # Duplicates
    valid, err = validate_member_names(["Alice", "alice"])
    # Distinct case
    valid2, err2 = validate_member_names(["Alice", "Alice"])
    assert not valid2
    assert "unique" in err2


def test_all_items_assigned():
    # 3 items, only 2 assigned
    assignments = {0: ["Alice"], 1: ["Bob"]}
    ok, missing = all_items_assigned(assignments, 3)
    assert not ok
    assert missing == [2]

    # All 3 assigned
    assignments[2] = ["Alice", "Bob"]
    ok, missing = all_items_assigned(assignments, 3)
    assert ok
    assert missing == []


def test_format_money():
    assert format_money(Decimal("1357.00")) == "₹1357.00"
    assert format_money(Decimal("0")) == "₹0.00"
    assert format_money(None) == "N/A"


def test_parse_ai_json_variations():
    # Plain JSON
    raw = '{"restaurant_name": "Test Cafe", "total": 100}'
    assert _parse_ai_json(raw)["restaurant_name"] == "Test Cafe"

    # Markdown code fence ```json ... ```
    wrapped = "```json\n" + raw + "\n```"
    assert _parse_ai_json(wrapped)["restaurant_name"] == "Test Cafe"

    # Preamble text before and after
    with_preamble = "Here is the extracted bill:\n```json\n" + raw + "\n```\nHope this helps!"
    assert _parse_ai_json(with_preamble)["restaurant_name"] == "Test Cafe"

    # Invalid JSON raises ExtractionError
    with pytest.raises(ExtractionError):
        _parse_ai_json("This is not JSON at all.")


def test_load_demo_bill_integrity():
    bill = load_demo_bill()
    assert bill.is_demo is True
    assert bill.restaurant_name == "Indore Spice Kitchen"
    assert len(bill.items) == 3
    assert bill.subtotal == Decimal("1180")
    assert bill.tax == Decimal("118")
    assert bill.service_charge == Decimal("59")
    assert bill.total == Decimal("1357")


def test_all_five_sample_bills_load_and_validate():
    from extractor import SAMPLE_BILLS, load_sample_bill
    assert len(SAMPLE_BILLS) == 5
    for bid, info in SAMPLE_BILLS.items():
        assert info["img_path"].exists(), f"Image missing for {bid}"
        assert info["json_path"].exists(), f"JSON missing for {bid}"
        bill = load_sample_bill(bid)
        assert bill.is_demo is True
        assert len(bill.items) >= 3
        assert bill.subtotal > Decimal("0")
        assert bill.total > Decimal("0")
        assert 2 <= len(info["default_members"]) <= 3

