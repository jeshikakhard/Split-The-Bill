from decimal import Decimal

import pytest

from calculator import allocate_proportional, compute_split, split_equally


def D(v):
    return Decimal(str(v))


# ---------------------------------------------------------------------------
# split_equally
# ---------------------------------------------------------------------------

def test_split_equally_two_people_even():
    shares = split_equally(D("600"), 2)
    assert shares == [D("300.00"), D("300.00")]
    assert sum(shares) == D("600.00")


def test_split_equally_three_people_uneven():
    shares = split_equally(D("100"), 3)
    assert sum(shares) == D("100.00")
    assert len(shares) == 3
    # Each share close to 33.33/33.34
    assert all(D("33.00") <= s <= D("34.00") for s in shares)


# ---------------------------------------------------------------------------
# allocate_proportional (tax / service charge / discount)
# ---------------------------------------------------------------------------

def test_allocate_proportional_matches_spec_example():
    weights = {"Jeshika": D("550"), "Rahul": D("300"), "Priya": D("330")}
    result = allocate_proportional(D("118"), weights)
    assert sum(result.values()) == D("118.00")
    # proportional, not equal split
    assert result["Jeshika"] > result["Rahul"]
    assert result["Priya"] > result["Rahul"]


def test_allocate_proportional_zero_amount():
    weights = {"A": D("10"), "B": D("20")}
    result = allocate_proportional(D("0"), weights)
    assert result == {"A": D("0.00"), "B": D("0.00")}


def test_allocate_proportional_reconciles_exactly():
    # A case prone to rounding drift: weights that don't divide evenly.
    weights = {"A": D("1"), "B": D("1"), "C": D("1")}
    result = allocate_proportional(D("10.00"), weights)
    assert sum(result.values()) == D("10.00")


# ---------------------------------------------------------------------------
# compute_split - end to end scenarios
# ---------------------------------------------------------------------------

DEMO_ITEMS = ["Chicken Biryani", "Coke", "Paneer Pizza"]
DEMO_TOTALS = [D("600"), D("80"), D("500")]
DEMO_ASSIGN = [["Jeshika", "Rahul"], ["Priya"], ["Jeshika", "Priya"]]
DEMO_MEMBERS = ["Jeshika", "Rahul", "Priya"]


def test_one_person_item_allocation():
    result = compute_split(
        item_totals=[D("80")],
        item_names=["Coke"],
        assignments=[["Priya"]],
        members=["Priya", "Jeshika"],
        discount=D("0"),
        tax=D("0"),
        service_charge=D("0"),
        printed_total=D("80"),
    )
    priya = next(p for p in result["people"] if p["name"] == "Priya")
    jeshika = next(p for p in result["people"] if p["name"] == "Jeshika")
    assert priya["final_amount"] == "80.00"
    assert jeshika["final_amount"] == "0.00"


def test_two_person_shared_item():
    result = compute_split(
        item_totals=[D("600")],
        item_names=["Biryani"],
        assignments=[["Jeshika", "Rahul"]],
        members=["Jeshika", "Rahul"],
        discount=D("0"),
        tax=D("0"),
        service_charge=D("0"),
        printed_total=D("600"),
    )
    for p in result["people"]:
        assert p["final_amount"] == "300.00"


def test_three_person_shared_item():
    result = compute_split(
        item_totals=[D("100")],
        item_names=["Pizza"],
        assignments=[["A", "B", "C"]],
        members=["A", "B", "C"],
        discount=D("0"),
        tax=D("0"),
        service_charge=D("0"),
        printed_total=D("100"),
    )
    total = sum(D(p["final_amount"]) for p in result["people"])
    assert total == D("100.00")


def test_demo_bill_matches_spec_numbers():
    result = compute_split(
        item_totals=DEMO_TOTALS,
        item_names=DEMO_ITEMS,
        assignments=DEMO_ASSIGN,
        members=DEMO_MEMBERS,
        discount=D("0"),
        tax=D("118"),
        service_charge=D("59"),
        printed_total=D("1357"),
    )
    by_name = {p["name"]: p for p in result["people"]}
    assert by_name["Jeshika"]["gross_consumption"] == "550.00"
    assert by_name["Rahul"]["gross_consumption"] == "300.00"
    assert by_name["Priya"]["gross_consumption"] == "330.00"
    assert result["bill_total"] == "1357.00"
    assert result["allocated_total"] == "1357.00"
    assert result["difference"] == "0.00"
    assert result["is_reconciled"] is True


def test_proportional_gst_not_equal_split():
    result = compute_split(
        item_totals=DEMO_TOTALS,
        item_names=DEMO_ITEMS,
        assignments=DEMO_ASSIGN,
        members=DEMO_MEMBERS,
        discount=D("0"),
        tax=D("118"),
        service_charge=D("0"),
        printed_total=None,
    )
    by_name = {p["name"]: p for p in result["people"]}
    # NOT 118/3 = 39.33 each - must be proportional
    equal_split = D("118") / 3
    assert D(by_name["Jeshika"]["tax_share"]) != round(equal_split, 2)
    assert D(by_name["Jeshika"]["tax_share"]) > D(by_name["Rahul"]["tax_share"])


def test_proportional_service_charge():
    result = compute_split(
        item_totals=DEMO_TOTALS,
        item_names=DEMO_ITEMS,
        assignments=DEMO_ASSIGN,
        members=DEMO_MEMBERS,
        discount=D("0"),
        tax=D("0"),
        service_charge=D("59"),
        printed_total=None,
    )
    by_name = {p["name"]: p for p in result["people"]}
    assert D(by_name["Priya"]["service_charge_share"]) > D(by_name["Rahul"]["service_charge_share"])


def test_proportional_discount():
    result = compute_split(
        item_totals=DEMO_TOTALS,
        item_names=DEMO_ITEMS,
        assignments=DEMO_ASSIGN,
        members=DEMO_MEMBERS,
        discount=D("118"),
        tax=D("0"),
        service_charge=D("0"),
        printed_total=None,
    )
    by_name = {p["name"]: p for p in result["people"]}
    assert D(by_name["Jeshika"]["discount_share"]) > D(by_name["Rahul"]["discount_share"])
    total_discount = sum(D(p["discount_share"]) for p in result["people"])
    assert total_discount == D("118.00")


def test_decimal_rounding_reconciles_no_residual_lost():
    # Odd total that doesn't divide evenly among 3 people.
    result = compute_split(
        item_totals=[D("10.00")],
        item_names=["Item"],
        assignments=[["A", "B", "C"]],
        members=["A", "B", "C"],
        discount=D("0"),
        tax=D("1.00"),
        service_charge=D("1.00"),
        printed_total=D("12.00"),
    )
    total_final = sum(D(p["final_amount"]) for p in result["people"])
    assert total_final == D("12.00")
    assert result["is_reconciled"] is True


def test_final_total_reconciliation_general():
    result = compute_split(
        item_totals=DEMO_TOTALS,
        item_names=DEMO_ITEMS,
        assignments=DEMO_ASSIGN,
        members=DEMO_MEMBERS,
        discount=D("37"),
        tax=D("118"),
        service_charge=D("59"),
        printed_total=D("1320"),
    )
    allocated = sum(D(p["final_amount"]) for p in result["people"])
    assert str(allocated.quantize(D("0.01"))) == result["allocated_total"]


def test_missing_printed_total_flagged_and_labeled_computed():
    result = compute_split(
        item_totals=DEMO_TOTALS,
        item_names=DEMO_ITEMS,
        assignments=DEMO_ASSIGN,
        members=DEMO_MEMBERS,
        discount=D("0"),
        tax=D("118"),
        service_charge=D("59"),
        printed_total=None,
    )
    assert result["printed_total_available"] is False
    assert any("not available" in w for w in result["warnings"])
    # Falls back to computed total, and is still internally reconciled.
    assert result["bill_total"] == "1357.00"
    assert result["is_reconciled"] is True


def test_incorrect_printed_total_detected():
    result = compute_split(
        item_totals=DEMO_TOTALS,
        item_names=DEMO_ITEMS,
        assignments=DEMO_ASSIGN,
        members=DEMO_MEMBERS,
        discount=D("0"),
        tax=D("118"),
        service_charge=D("59"),
        printed_total=D("2000"),  # deliberately wrong
    )
    assert result["is_reconciled"] is False
    assert D(result["difference"]) != D("0.00")


def test_unassigned_member_gets_zero_not_crash():
    result = compute_split(
        item_totals=[D("100")],
        item_names=["Item"],
        assignments=[["A"]],
        members=["A", "B", "C"],
        discount=D("0"),
        tax=D("0"),
        service_charge=D("0"),
        printed_total=D("100"),
    )
    by_name = {p["name"]: p for p in result["people"]}
    assert by_name["B"]["final_amount"] == "0.00"
    assert by_name["C"]["final_amount"] == "0.00"


def test_live_auto_calculation_reconciles_subtotal_and_grand_total():
    # Simulate user adding 3 items:
    # Item 1: 2 * 300 = 600
    # Item 2: 1 * 80 = 80
    # Item 3: 1 * 500 = 500
    # Item 4 (newly added): 2 * 60 = 120
    items = [
        (D("2"), D("300"), D("600")),
        (D("1"), D("80"), D("80")),
        (D("1"), D("500"), D("500")),
        (D("2"), D("60"), D("120")),
    ]
    # Verify each item total = qty * unit_price
    for qty, unit, total in items:
        assert qty * unit == total

    # Auto-calculated Subtotal = sum of items
    subtotal = sum(t for _, _, t in items)
    assert subtotal == D("1300.00")

    # Taxes & Discounts
    discount = D("100.00")
    tax = D("120.00")
    service_charge = D("60.00")

    # Auto-calculated Grand Total = Subtotal - Discount + Tax + Service
    grand_total = subtotal - discount + tax + service_charge
    assert grand_total == D("1380.00")

    # When fed into compute_split, the split reconciles 100%
    result = compute_split(
        item_totals=[t for _, _, t in items],
        item_names=["Biryani", "Coke", "Pizza", "Garlic Naan"],
        assignments=[["A", "B"], ["C"], ["A", "C"], ["A", "B", "C"]],
        members=["A", "B", "C"],
        discount=discount,
        tax=tax,
        service_charge=service_charge,
        printed_total=grand_total,
    )
    assert result["is_reconciled"] is True
    assert result["difference"] == "0.00"
    assert result["allocated_total"] == "1380.00"

